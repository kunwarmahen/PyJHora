"""Lazy storage for smart-lookup tool traces.

The conversation document keeps only the *light* trace on each assistant message
(tool name + args + ok + a `trace_id`), so listing and opening threads stays fast.
The *full* tool results — which can be sizable — live here in a separate
`ai_tool_traces` collection, fetched only when the user expands "Behind the
scenes" on a reopened answer. Scoped to the owning user_id on every query.

A trace is keyed by an opaque `trace_id` (generated per saved answer), which is
robust to message-index shifts and to "regenerate" replacing an answer in place.
"""
import bson
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from database import bson_safe, get_database

COLLECTION = "ai_tool_traces"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# A trace is a debugging aid, not the answer. Past this much BSON it is dropped
# rather than risking Mongo's 16MB document limit on the way in.
MAX_TRACE_BYTES = 8_000_000


async def save_trace(user_id: str, conversation_id: str, trace_id: str,
                     results: List[Dict[str, Any]]) -> None:
    """Persist the full per-call results for one answer. Upserts on trace_id so a
    regenerate that reuses the id overwrites cleanly.

    Tool results come straight from the engine and are *not* BSON-shaped — several
    are keyed by house number, which Mongo refuses outright — so they are coerced
    on the way in (`bson_safe`) and dropped if outsized. Neither is worth failing
    the write for: the caller is storing a real answer alongside this.
    """
    if not (trace_id and results):
        return
    safe = bson_safe(results)
    try:
        if len(bson.encode({"r": safe})) > MAX_TRACE_BYTES:
            safe = [{"name": (e or {}).get("name"),
                     "result": {"note": "Trace omitted — too large to store."}}
                    for e in results]
    except Exception:
        # Un-encodable even after coercion: keep the shape, lose the detail.
        safe = [{"name": (e or {}).get("name"),
                 "result": {"note": "Trace omitted — could not be stored."}}
                for e in results]
    db = get_database()
    await db[COLLECTION].update_one(
        {"trace_id": trace_id, "user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "conversation_id": conversation_id,
            "trace_id": trace_id,
            "results": safe,
            "updated_at": _now_iso(),
        }},
        upsert=True,
    )


async def get_trace(user_id: str, trace_id: str) -> Optional[Dict[str, Any]]:
    """Return {"trace_id", "results": [...]} for one answer, or None."""
    db = get_database()
    doc = await db[COLLECTION].find_one(
        {"trace_id": trace_id, "user_id": user_id},
        {"_id": 0, "trace_id": 1, "results": 1},
    )
    return doc


async def delete_for_conversation(user_id: str, conversation_id: str) -> None:
    """Clean up all traces when a conversation is deleted."""
    db = get_database()
    await db[COLLECTION].delete_many(
        {"user_id": user_id, "conversation_id": conversation_id})
