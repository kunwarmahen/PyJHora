"""The newcomer funnel (§76.8): is the first minute working?

Two kinds of record, neither of which holds anything a person said or computed:

* **Daily counts** (`funnel_daily`) — how many times each step happened today:
  the landing page was opened, an anonymous preview was shown, an account was
  created, the welcome flow finished, the "your chart in plain words" page was
  seen, a first question was asked, someone came back after a week. Counts
  only, no user field — like `ai_outbound` (§78).
* **Per-account milestones** (`users.onboarding.*`) — the first time an account
  reached a step. Written once, on the user's own document, so a step is counted
  once per person (the daily count for a milestone step is "people who reached
  it", not page views) and so the headline metric can be measured: **time from
  sign-up to the first personal answer**. They go with the account when it is
  deleted, because they live on it.

Every write is fire-and-forget: a counter must never slow or fail the thing it
counts.
"""
import asyncio
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

COLLECTION = "funnel_daily"

# The steps, in funnel order. Anonymous steps are counted per occurrence; the
# milestone steps once per account (see `milestone`).
ANON_EVENTS = ("landing_view", "preview_seen")
MILESTONES = ("signup", "welcome_done", "payoff_seen", "first_ask", "returned_day7")
EVENTS = ANON_EVENTS + MILESTONES

_pending: set = set()   # strong refs, so a fire-and-forget write isn't GC'd mid-flight


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _spawn(coro) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        return
    task = loop.create_task(coro)
    _pending.add(task)
    task.add_done_callback(_pending.discard)


async def _inc(event: str) -> None:
    try:
        from database import get_database
        day = _now().strftime("%Y-%m-%d")
        await get_database()[COLLECTION].update_one(
            {"_id": f"{day}|{event}"},
            {"$setOnInsert": {"day": day, "event": event}, "$inc": {"count": 1}},
            upsert=True)
    except Exception:
        pass


def record(event: str) -> None:
    """Count one anonymous step. Unknown names are ignored, never stored."""
    if event in EVENTS:
        _spawn(_inc(event))


async def _milestone(username: str, step: str) -> None:
    try:
        from database import get_database
        res = await get_database()["users"].update_one(
            {"username": username, f"onboarding.{step}": {"$exists": False}},
            {"$set": {f"onboarding.{step}": _now().isoformat()}})
        if getattr(res, "modified_count", 0) == 1:
            await _inc(step)
    except Exception:
        pass


def milestone(username: Optional[str], step: str) -> None:
    """Mark the first time `username` reached `step`; later calls do nothing."""
    if username and step in MILESTONES:
        _spawn(_milestone(username, step))


async def check_returned(username: Optional[str]) -> None:
    """Mark `returned_day7` once an account is used a week or more after sign-up.
    Called from the app's on-load profile fetch, so it costs one read per load."""
    if not username:
        return
    try:
        from database import get_database
        doc = await get_database()["users"].find_one(
            {"username": username}, {"created_at": 1, "onboarding.returned_day7": 1})
        if not doc or (doc.get("onboarding") or {}).get("returned_day7"):
            return
        created = _parse(doc.get("created_at"))
        if created and _now() - created >= timedelta(days=7):
            milestone(username, "returned_day7")
    except Exception:
        pass


def _parse(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value:
        try:
            d = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _median_minutes(pairs: List[tuple]) -> Optional[float]:
    gaps = [(b - a).total_seconds() / 60 for a, b in pairs if a and b and b >= a]
    return round(statistics.median(gaps), 1) if gaps else None


async def summary(days: int = 30) -> Dict[str, Any]:
    """Step counts over the last `days` days, plus the medians from sign-up to the
    first personal answer — the plain-words page, and the first question asked —
    for accounts created in that window. Counts and minutes only."""
    from database import get_database
    db = get_database()
    since_day = (_now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    rows = await db[COLLECTION].aggregate([
        {"$match": {"day": {"$gte": since_day}}},
        {"$group": {"_id": "$event", "count": {"$sum": "$count"}}},
    ]).to_list(length=None)
    counts = {r["_id"]: r["count"] for r in rows}

    since = (_now() - timedelta(days=days)).isoformat()
    payoff, ask = [], []
    async for u in db["users"].find({"created_at": {"$gte": since}},
                                    {"created_at": 1, "onboarding": 1}):
        created = _parse(u.get("created_at"))
        ob = u.get("onboarding") or {}
        payoff.append((created, _parse(ob.get("payoff_seen"))))
        ask.append((created, _parse(ob.get("first_ask"))))
    return {
        "days": days,
        "steps": [{"event": e, "count": counts.get(e, 0)} for e in EVENTS],
        "median_minutes_to_payoff": _median_minutes(payoff),
        "median_minutes_to_first_ask": _median_minutes(ask),
    }
