"""AI conversation persistence — chat threads tied to a user + profile.

Stored in the `ai_conversations` Mongo collection. Each document holds the full
message list plus metadata so a thread can be revisited, continued (multi-turn),
or deleted. Scoped to the owning user_id on every query.
"""
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from bson import ObjectId

from database import get_database

COLLECTION = "ai_conversations"

# How many prior messages to feed back to the model for multi-turn context.
HISTORY_WINDOW = 8


def history_max() -> int:
    """Max history items kept/returned per user. Configurable via `AI_HISTORY_MAX`
    (default 100). Older items beyond the cap are pruned on write."""
    try:
        return max(1, int(os.getenv("AI_HISTORY_MAX", "100")))
    except (TypeError, ValueError):
        return 100


# Registry of every AI "source" → how the unified history UI labels it, which page
# to deep-link back to, and whether it is a multi-turn "chat" or a single-shot
# "reading". `kind` lets the History page group/badge items; `route` is where a
# click navigates (the page then restores its inputs from the stored `context`).
SOURCE_META: Dict[str, Dict[str, str]] = {
    "astrologer":       {"label": "Ask Astrologer",     "route": "/ask-astrologer",    "kind": "chat"},
    "transit":          {"label": "Transit chat",       "route": "/transit",           "kind": "chat"},
    "varshaphal":       {"label": "Annual (Varshaphal)","route": "/varshaphal",        "kind": "reading"},
    "muhurta":          {"label": "Muhurta",            "route": "/muhurta",           "kind": "reading"},
    "prashna":          {"label": "Prashna",            "route": "/prashna",           "kind": "reading"},
    "remedies":         {"label": "Remedies",           "route": "/remedies",          "kind": "reading"},
    "bhrigu":           {"label": "Bhrigu markers",     "route": "/bhrigu-markers",    "kind": "reading"},
    "daily_digest":       {"label": "Daily digest",       "route": "/daily-digest",       "kind": "reading"},
    "fortnightly_digest": {"label": "Fortnightly digest", "route": "/fortnightly-digest", "kind": "reading"},
    "monthly_digest":     {"label": "Monthly digest",     "route": "/monthly-digest",     "kind": "reading"},
    # Tithi Pravesha moved off /varshaphal onto its own page (which also carries the
    # shorter rungs). Readings saved before the move reopen there too — the page
    # restores the rung from the saved context, defaulting to annual when absent,
    # which is exactly what those older readings were.
    "tithi_pravesha":     {"label": "Tithi Pravesha",     "route": "/tithi-pravesha",     "kind": "reading"},
    "sensitive_points": {"label": "Sensitive points",   "route": "/sensitive-points",  "kind": "reading"},
    "celestial":        {"label": "Vedic clock",        "route": "/vedic-clock",       "kind": "reading"},
    "almanac":          {"label": "Almanac",            "route": "/almanac",           "kind": "reading"},
    "panchapakshi":     {"label": "Pancha Pakshi",      "route": "/pancha-pakshi",     "kind": "reading"},
    "sarvatobhadra":    {"label": "Sarvatobhadra",      "route": "/sarvatobhadra",     "kind": "reading"},
    "compatibility":    {"label": "Compatibility",      "route": "/compatibility",     "kind": "reading"},
    "compare":          {"label": "Compare charts",     "route": "/compare",           "kind": "reading"},
    "rectification":    {"label": "Rectification",      "route": "/rectify",           "kind": "reading"},
    "quiz":             {"label": "Learn quiz",         "route": "/learn",             "kind": "reading"},
    "prediction":       {"label": "Prediction",         "route": "/predictions",       "kind": "reading"},
    "kp":               {"label": "KP system",          "route": "/kp",                "kind": "reading"},
    "kp_horary":        {"label": "KP horary",          "route": "/kp",                "kind": "reading"},
    "jaimini":          {"label": "Jaimini",            "route": "/jaimini",           "kind": "reading"},
    "now_chart":        {"label": "Chart of the moment","route": "/now",               "kind": "reading"},
    "nakshatra_profile": {"label": "Nakshatra profile",  "route": "/nakshatra",         "kind": "reading"},
    "gochara_phala":     {"label": "Gochara-phala",       "route": "/gochara",           "kind": "reading"},
    "life_report":       {"label": "Life Report",          "route": "/life-report",       "kind": "reading"},
}


def source_meta(source: Optional[str]) -> Dict[str, str]:
    return SOURCE_META.get(source or "astrologer",
                           {"label": (source or "AI"), "route": "/ask-astrologer",
                            "kind": "reading"})


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_conversation(user_id: str, profile_id: Optional[str],
                              title: str,
                              birth_details: Optional[Dict[str, Any]] = None,
                              mode: str = "pass_all",
                              source: str = "astrologer",
                              context: Optional[Dict[str, Any]] = None) -> str:
    db = get_database()
    meta = source_meta(source)
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "title": (title or "New conversation").strip()[:80],
        "birth_details": birth_details,
        # How answers in this thread are produced: "pass_all" (default) sends a
        # pre-assembled context block; "tools" lets the model fetch data on demand.
        "mode": mode if mode in ("pass_all", "tools") else "pass_all",
        # Where the thread originated, so the unified history can label/filter it.
        "source": source or "astrologer",
        # "chat" (multi-turn) or "reading" (single-shot analysis) — set from the registry.
        "kind": meta["kind"],
        # The page to deep-link back to when this item is opened from history.
        "route": meta["route"],
        # Inputs needed to restore that page to exactly this reading (tool params,
        # date/year/place/…). Snapshot: the page reuses these instead of guessing.
        "context": context or None,
        "messages": [],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    res = await db[COLLECTION].insert_one(doc)
    await prune_history(user_id)
    return str(res.inserted_id)


async def save_reading(user_id: str, *, source: str, title: str, text: str,
                       context: Optional[Dict[str, Any]] = None,
                       profile_id: Optional[str] = None,
                       birth_details: Optional[Dict[str, Any]] = None,
                       model: Optional[str] = None,
                       provider: Optional[str] = None,
                       request_label: Optional[str] = None) -> Optional[str]:
    """Persist a single-shot AI reading as a one-turn history item so it shows up
    in the unified history and can be reopened on its source page. Best-effort:
    never raise into the request path (callers wrap in try/except too)."""
    if not text:
        return None
    db = get_database()
    meta = source_meta(source)
    now = _now_iso()
    user_msg = {"role": "user", "content": (request_label or title or "Reading"), "ts": now}
    ai_msg = {"role": "assistant", "content": text, "ts": now,
              "provider": provider, "model": model}
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "title": (title or meta["label"]).strip()[:80],
        "birth_details": birth_details,
        "mode": "pass_all",
        "source": source,
        "kind": "reading",
        "route": meta["route"],
        "context": context or None,
        "messages": [user_msg, ai_msg],
        "created_at": now,
        "updated_at": now,
    }
    res = await db[COLLECTION].insert_one(doc)
    await prune_history(user_id)
    return str(res.inserted_id)


async def prune_history(user_id: str) -> None:
    """Enforce the per-user retention cap (`AI_HISTORY_MAX`): keep the newest N
    items, delete the rest. Pile-up model — every reading is its own item."""
    cap = history_max()
    db = get_database()
    # Ids of the newest `cap` items; anything older is removed.
    keep = [c["_id"] async for c in
            db[COLLECTION].find({"user_id": user_id}, {"_id": 1})
            .sort("updated_at", -1).limit(cap)]
    if len(keep) < cap:
        return
    await db[COLLECTION].delete_many(
        {"user_id": user_id, "_id": {"$nin": keep}})


async def get_conversation(user_id: str, conv_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(conv_id)
    except Exception:
        return None
    return await db[COLLECTION].find_one({"_id": oid, "user_id": user_id})


async def append_messages(user_id: str, conv_id: str,
                          messages: List[Dict[str, Any]]) -> None:
    db = get_database()
    try:
        oid = ObjectId(conv_id)
    except Exception:
        return
    await db[COLLECTION].update_one(
        {"_id": oid, "user_id": user_id},
        {"$push": {"messages": {"$each": messages}},
         "$set": {"updated_at": _now_iso()}},
    )


async def replace_last_assistant(user_id: str, conv_id: str,
                                 assistant_msg: Dict[str, Any]) -> None:
    """Swap the conversation's final assistant message (used for 'Regenerate' so
    the saved thread isn't polluted with a duplicate question/answer pair)."""
    db = get_database()
    try:
        oid = ObjectId(conv_id)
    except Exception:
        return
    conv = await db[COLLECTION].find_one({"_id": oid, "user_id": user_id})
    if not conv:
        return
    msgs = conv.get("messages", [])
    for i in range(len(msgs) - 1, -1, -1):
        if msgs[i].get("role") == "assistant":
            msgs[i] = assistant_msg
            break
    else:
        msgs.append(assistant_msg)
    await db[COLLECTION].update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"messages": msgs, "updated_at": _now_iso()}},
    )


async def set_feedback(user_id: str, conv_id: str, message_index: int,
                       rating: Optional[str]) -> bool:
    """Store thumbs up/down (or clear it) on one assistant message by index."""
    db = get_database()
    try:
        oid = ObjectId(conv_id)
    except Exception:
        return False
    conv = await db[COLLECTION].find_one({"_id": oid, "user_id": user_id})
    if not conv:
        return False
    msgs = conv.get("messages", [])
    if not (0 <= message_index < len(msgs)):
        return False
    if rating in (None, ""):
        msgs[message_index].pop("feedback", None)
    else:
        msgs[message_index]["feedback"] = rating
    await db[COLLECTION].update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {"messages": msgs, "updated_at": _now_iso()}},
    )
    return True


async def list_conversations(user_id: str,
                             profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_database()
    query: Dict[str, Any] = {"user_id": user_id}
    if profile_id:
        query["profile_id"] = profile_id
    cursor = db[COLLECTION].find(query).sort("updated_at", -1).limit(history_max())
    out = []
    async for c in cursor:
        msgs = c.get("messages", [])
        last_model = next(
            (m.get("model") for m in reversed(msgs) if m.get("role") == "assistant"),
            None,
        )
        # A short preview of the reading/last answer for the history list.
        last_answer = next(
            (m.get("content") for m in reversed(msgs) if m.get("role") == "assistant"),
            "",
        ) or ""
        source = c.get("source", "astrologer")
        meta = source_meta(source)
        out.append({
            "id": str(c["_id"]),
            "profile_id": c.get("profile_id"),
            "title": c.get("title"),
            "mode": c.get("mode", "pass_all"),
            "source": source,
            "kind": c.get("kind", meta["kind"]),
            "route": c.get("route", meta["route"]),
            "label": meta["label"],
            "message_count": len(msgs),
            "last_model": last_model,
            "preview": last_answer[:160],
            "created_at": c.get("created_at"),
            "updated_at": c.get("updated_at"),
        })
    return out


async def delete_conversation(user_id: str, conv_id: str) -> bool:
    db = get_database()
    try:
        oid = ObjectId(conv_id)
    except Exception:
        return False
    res = await db[COLLECTION].delete_one({"_id": oid, "user_id": user_id})
    return res.deleted_count > 0


def serialize_conversation(c: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not c:
        return None
    source = c.get("source", "astrologer")
    meta = source_meta(source)
    return {
        "id": str(c["_id"]),
        "profile_id": c.get("profile_id"),
        "title": c.get("title"),
        "mode": c.get("mode", "pass_all"),
        "source": source,
        "kind": c.get("kind", meta["kind"]),
        "route": c.get("route", meta["route"]),
        "label": meta["label"],
        "context": c.get("context"),
        "birth_details": c.get("birth_details"),
        "messages": c.get("messages", []),
        "created_at": c.get("created_at"),
        "updated_at": c.get("updated_at"),
    }


def history_for_model(conv: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Last HISTORY_WINDOW turns as plain {role, content} for the LLM."""
    if not conv:
        return []
    msgs = conv.get("messages", [])[-HISTORY_WINDOW:]
    return [{"role": m["role"], "content": m["content"]}
            for m in msgs if m.get("role") in ("user", "assistant") and m.get("content")]
