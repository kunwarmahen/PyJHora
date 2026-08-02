"""Delivered digests, kept as reopenable readings.

A digest that arrives by email at 7am used to exist nowhere in the app: the
scheduler computed it, handed it to the mailer, and dropped it. Only a digest
generated *in* the app (from the Daily Digest page) was saved. So the reading a
user actually reads every morning was the one reading they could never look back
at. This module closes that: every delivered digest, for every profile it
covered, is stored and shows up in the unified history.

**Why its own collection rather than `ai_conversations`.** Digests arrive on a
schedule, one per profile per cadence — three profiles on a daily send is ~90
items a month. Dropped into the shared history pile they would push every chat
and every other reading past the `AI_HISTORY_MAX` cap within weeks, and the
user's Ask-Astrologer threads would silently disappear because they subscribed to
a digest. Separate storage means separate retention: `DIGEST_HISTORY_MAX` bounds
digests only, and nothing a digest does can evict anything a user wrote.

They still read as one list. Ids are prefixed `dg_`, and the conversation
endpoints fall through to this module for a prefixed id, so the existing history
UI — open, restore-on-page, delete — works on a digest without knowing it is one.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

from config import settings
from database import get_database

COLLECTION = "digest_readings"

# Prefix that marks a history id as living here rather than in ai_conversations.
ID_PREFIX = "dg_"

# Cadence → how the history item is labelled and where clicking it lands. Mirrors
# the `SOURCE_META` entries in conversations.py for the in-app equivalents, so a
# scheduled digest and an in-app one look and behave identically in the list.
CADENCE_META = {
    "daily": {"label": "Daily digest", "route": "/daily-digest", "source": "daily_digest"},
    "fortnightly": {"label": "Fortnightly digest", "route": "/fortnightly-digest",
                    "source": "fortnightly_digest"},
    "monthly": {"label": "Monthly digest", "route": "/monthly-digest",
                "source": "monthly_digest"},
}


def _meta(cadence: str) -> Dict[str, str]:
    return CADENCE_META.get(cadence or "daily", CADENCE_META["daily"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def history_max() -> int:
    try:
        return max(1, int(settings.DIGEST_HISTORY_MAX))
    except (TypeError, ValueError):
        return 120


def is_digest_id(item_id: str) -> bool:
    return bool(item_id) and str(item_id).startswith(ID_PREFIX)


def _oid(item_id: str) -> Optional[ObjectId]:
    try:
        return ObjectId(str(item_id)[len(ID_PREFIX):])
    except Exception:
        return None


def render_text(block: Dict[str, Any]) -> str:
    """The stored reading body for one profile's section.

    The AI narrative when there is one; otherwise the highlights written out as
    prose-ish lines. A digest whose narrative failed is still worth keeping — it
    is what the user was actually sent, and a history that quietly omits the
    thinner days would misrepresent what they received."""
    parts: List[str] = []
    if block.get("narrative"):
        parts.append(block["narrative"].strip())
    if block.get("changes"):
        parts.append("**Since your last digest**\n"
                     + "\n".join(f"- {c}" for c in block["changes"]))
    if block.get("supports"):
        parts.append("**Working in your favour**\n"
                     + "\n".join(f"- {c['text']}" for c in block["supports"]))
    if block.get("cautions"):
        parts.append("**Take care with**\n"
                     + "\n".join(f"- {c['text']}" for c in block["cautions"]))
    highlights = block.get("highlights") or []
    if highlights:
        parts.append("**Highlights**\n" + "\n".join(f"- {h}" for h in highlights))
    return "\n\n".join(parts).strip()


async def save(user_id: str, *, cadence: str, block: Dict[str, Any],
               profile_id: Optional[str], subject: str,
               delivered: Optional[Dict[str, Any]] = None,
               provider: Optional[str] = None,
               model: Optional[str] = None,
               birth_details: Optional[Dict[str, Any]] = None,
               context: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Persist one profile's delivered digest section. Best-effort: a storage
    failure must never stop (or unsend) a delivery, so callers get None and a log
    line rather than an exception."""
    body = render_text(block)
    if not body:
        return None
    meta = _meta(cadence)
    try:
        db = get_database()
        doc = {
            "user_id": user_id,
            "profile_id": profile_id or None,
            "cadence": cadence,
            "subject": subject,
            "date": block.get("date"),
            "title": f"{meta['label']} — {block.get('date') or ''}".strip(" —"),
            "narrative": block.get("narrative"),
            "text": body,
            "highlights": block.get("highlights") or [],
            "cautions": block.get("cautions") or [],
            "supports": block.get("supports") or [],
            "changes": block.get("changes") or [],
            "sky": block.get("sky") or [],
            "personal": block.get("personal") or [],
            "birth_details": birth_details,
            "context": context or None,
            "delivered": delivered or {},
            "provider": provider,
            "model": model,
            "created_at": _now_iso(),
        }
        res = await db[COLLECTION].insert_one(doc)
        await prune(user_id)
        return ID_PREFIX + str(res.inserted_id)
    except Exception as e:
        print(f"[digest_history] save failed for {user_id}: {e}")
        return None


async def prune(user_id: str) -> None:
    """Enforce `DIGEST_HISTORY_MAX` for one user. Bounded independently of the AI
    history cap — that separation is the reason this collection exists."""
    cap = history_max()
    db = get_database()
    keep = [d["_id"] async for d in
            db[COLLECTION].find({"user_id": user_id}, {"_id": 1})
            .sort("created_at", -1).limit(cap)]
    if len(keep) < cap:
        return
    await db[COLLECTION].delete_many({"user_id": user_id, "_id": {"$nin": keep}})


def _list_item(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Shaped exactly like a `conversations.list_conversations` row so the history
    page can render a digest without special-casing it."""
    meta = _meta(doc.get("cadence"))
    preview = (doc.get("narrative") or doc.get("text") or "")
    return {
        "id": ID_PREFIX + str(doc["_id"]),
        "profile_id": doc.get("profile_id"),
        "title": doc.get("title") or meta["label"],
        "mode": "pass_all",
        "source": meta["source"],
        "kind": "digest",
        "route": meta["route"],
        "label": meta["label"],
        "message_count": 1,
        "last_model": doc.get("model"),
        "preview": preview.strip()[:160],
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("created_at"),
        # Only a digest carries these; the list uses them for the delivery badge.
        "cadence": doc.get("cadence"),
        "delivered": doc.get("delivered") or {},
    }


async def list_for_user(user_id: str, profile_id: Optional[str] = None,
                        cadence: Optional[str] = None,
                        limit: Optional[int] = None) -> List[Dict[str, Any]]:
    db = get_database()
    q: Dict[str, Any] = {"user_id": user_id}
    if profile_id:
        q["profile_id"] = profile_id
    if cadence:
        q["cadence"] = cadence
    cursor = db[COLLECTION].find(q).sort("created_at", -1).limit(limit or history_max())
    return [_list_item(doc) async for doc in cursor]


async def get(user_id: str, item_id: str) -> Optional[Dict[str, Any]]:
    oid = _oid(item_id)
    if oid is None:
        return None
    return await get_database()[COLLECTION].find_one({"_id": oid, "user_id": user_id})


async def delete(user_id: str, item_id: str) -> bool:
    oid = _oid(item_id)
    if oid is None:
        return False
    res = await get_database()[COLLECTION].delete_one({"_id": oid, "user_id": user_id})
    return res.deleted_count > 0


def serialize(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The single-item shape the reading-restore path expects: a one-turn thread
    whose assistant message is the digest. Lets `useRestoreReading` reopen a
    delivered digest on its page with no client-side branching."""
    if not doc:
        return None
    meta = _meta(doc.get("cadence"))
    ts = doc.get("created_at")
    return {
        "id": ID_PREFIX + str(doc["_id"]),
        "profile_id": doc.get("profile_id"),
        "title": doc.get("title") or meta["label"],
        "mode": "pass_all",
        "source": meta["source"],
        "kind": "digest",
        "route": meta["route"],
        "label": meta["label"],
        "context": doc.get("context"),
        "birth_details": doc.get("birth_details"),
        "messages": [
            {"role": "user", "content": doc.get("title") or meta["label"], "ts": ts},
            {"role": "assistant", "content": doc.get("text") or "", "ts": ts,
             "provider": doc.get("provider"), "model": doc.get("model")},
        ],
        "created_at": ts,
        "updated_at": ts,
        "delivered": doc.get("delivered") or {},
        "cadence": doc.get("cadence"),
    }
