"""Which model providers our requests went to, by day (§78).

The admin console's answer to "how much of our users' data goes to Gemini?":
every request that leaves `LLMService` is counted here by provider and by
whether it stayed on a self-hosted model. `redacted` counts the external calls
that had birth details held back (llm/privacy.py) — the gap between it and
`external` is users who opted in to sharing.

Counts only — no user, no content. Recorded as a detached Mongo `$inc` so a
slow or absent database never delays or fails a reading.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

COLLECTION = "ai_outbound"

_pending: set = set()   # strong refs, so a fire-and-forget insert isn't GC'd mid-flight


async def _inc(day: str, provider: str, external: bool, redacted: bool) -> None:
    try:
        from database import get_database
        await get_database()[COLLECTION].update_one(
            {"_id": f"{day}|{provider}"},
            {"$setOnInsert": {"day": day, "provider": provider},
             "$inc": {"calls": 1,
                      "external": 1 if external else 0,
                      "redacted": 1 if redacted else 0}},
            upsert=True)
    except Exception:
        pass    # a counter must never cost a reading


def record(cfg: Any, *, redacted: bool) -> None:
    """Count one request leaving on `cfg`. Safe to call from anywhere."""
    from llm.privacy import is_self_hosted
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    provider = getattr(getattr(cfg, "provider_type", None), "value", None) or "unknown"
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    task = loop.create_task(_inc(day, provider, not is_self_hosted(cfg), redacted))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def summary(days: int = 30) -> List[Dict[str, Any]]:
    """Per-provider totals over the last `days` days, busiest first."""
    from database import get_database
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    rows = await get_database()[COLLECTION].aggregate([
        {"$match": {"day": {"$gte": since}}},
        {"$group": {"_id": "$provider",
                    "calls": {"$sum": "$calls"},
                    "external": {"$sum": "$external"},
                    "redacted": {"$sum": "$redacted"}}},
        {"$sort": {"calls": -1}},
    ]).to_list(length=None)
    return [{"provider": r["_id"], "calls": r["calls"],
             "external": r["external"], "redacted": r["redacted"]} for r in rows]
