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
                              birth_details: Optional[Dict[str, Any]] = None) -> str:
    db = get_database()
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "title": (title or "New conversation").strip()[:80],
        "birth_details": birth_details,
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
