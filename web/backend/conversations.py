"""AI conversation persistence — chat threads tied to a user + profile.

Stored in the `ai_conversations` Mongo collection. Each document holds the full
message list plus metadata so a thread can be revisited, continued (multi-turn),
or deleted. Scoped to the owning user_id on every query.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from bson import ObjectId

from database import get_database

COLLECTION = "ai_conversations"

# How many prior messages to feed back to the model for multi-turn context.
HISTORY_WINDOW = 8


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_conversation(user_id: str, profile_id: Optional[str],
                              title: str,
                              birth_details: Optional[Dict[str, Any]] = None,
                              mode: str = "pass_all",
                              source: str = "astrologer") -> str:
    db = get_database()
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "title": (title or "New conversation").strip()[:80],
        "birth_details": birth_details,
        # How answers in this thread are produced: "pass_all" (default) sends a
        # pre-assembled context block; "tools" lets the model fetch data on demand.
        "mode": mode if mode in ("pass_all", "tools") else "pass_all",
        # Where the thread originated, so the Ask page can label/filter it:
        # "astrologer" (the main Ask page) or "transit" (the Transits-page chat).
        "source": source or "astrologer",
        "messages": [],
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    res = await db[COLLECTION].insert_one(doc)
    return str(res.inserted_id)


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
    cursor = db[COLLECTION].find(query).sort("updated_at", -1).limit(100)
    out = []
    async for c in cursor:
        msgs = c.get("messages", [])
        last_model = next(
            (m.get("model") for m in reversed(msgs) if m.get("role") == "assistant"),
            None,
        )
        out.append({
            "id": str(c["_id"]),
            "profile_id": c.get("profile_id"),
            "title": c.get("title"),
            "mode": c.get("mode", "pass_all"),
            "source": c.get("source", "astrologer"),
            "message_count": len(msgs),
            "last_model": last_model,
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
    return {
        "id": str(c["_id"]),
        "profile_id": c.get("profile_id"),
        "title": c.get("title"),
        "mode": c.get("mode", "pass_all"),
        "source": c.get("source", "astrologer"),
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
