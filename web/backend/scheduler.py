"""In-process daily-digest scheduler.

An opt-in asyncio background task (enabled with `DIGEST_SCHEDULER_ENABLED=true`)
that wakes every `DIGEST_SCHEDULER_INTERVAL_MINUTES` and, for each user who has
the daily digest enabled, delivers it once per day at *or after* their preferred
local hour (interpreted in the target birth profile's timezone). "At or after"
(rather than only during the exact hour) means the digest still goes out if the
process was down or restarting during the target hour — the user gets it later
that day instead of missing the day entirely.

**Once-per-day + multi-worker safety.** Before sending, a tick atomically
*claims* the user for today's local date via a conditional
`find_one_and_update` on `user_settings` (`notifications.last_sent_date != today`
→ set it). Only the worker/tick that wins the claim sends, so running several
uvicorn workers — or several ticks within the target hour — never double-sends.
If a send fails after claiming, the user simply gets the next day's digest
(better than risking duplicates).

This needs no external cron; a deployer can instead leave it disabled and point
their own scheduler at `POST /api/notifications/digest/send` per user. In a
multi-worker deployment either is fine — the DB claim makes the in-process
scheduler idempotent across workers.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import settings
from database import get_database
import digest
import notifications

_task: Optional[asyncio.Task] = None


def _local_now(tz_offset: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=tz_offset or 0)


async def _profile_tz(user_id: str, prefs: dict) -> float:
    # Pace the send off the first profile in the user's chosen set (falling back
    # to their primary profile). With several profiles across timezones we can
    # only pick one clock; the first selected one is the least surprising.
    profiles = await digest.resolve_profiles(user_id, prefs)
    profile = profiles[0] if profiles else None
    if not profile:
        return 0.0
    tz = (profile.get("birth_details") or {}).get("timezone")
    try:
        return float(tz) if tz is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


async def _tick() -> int:
    """One pass over all digest-enabled users. Returns how many were sent."""
    db = get_database()
    sent_count = 0
    cursor = db[notifications.SETTINGS_COLLECTION].find(
        {"notifications.daily_digest": True})
    async for doc in cursor:
        user_id = doc.get("user_id")
        if not user_id:
            continue
        prefs = {**notifications.DEFAULT_PREFS, **(doc.get("notifications") or {})}
        try:
            tz = await _profile_tz(user_id, prefs)
            local = _local_now(tz)
            # Deliver at *or after* the preferred hour (once per day). Using ">="
            # rather than an exact-hour match means a missed window — the process
            # was down or restarting during that single hour — still gets the
            # user their digest later the same day instead of skipping it.
            if local.hour < int(prefs.get("hour", 7)):
                continue
            local_date = local.strftime("%Y-%m-%d")

            # Atomically claim today's slot — only the winner proceeds to send.
            claimed = await db[notifications.SETTINGS_COLLECTION].find_one_and_update(
                {"user_id": user_id,
                 "notifications.last_sent_date": {"$ne": local_date}},
                {"$set": {"notifications.last_sent_date": local_date}},
            )
            if not claimed:
                continue  # already sent today (this worker or another)

            result = await digest.send_digest_for_user(user_id, prefs)
            if result.get("status") == "ok":
                sent_count += 1
            else:
                print(f"[scheduler] digest for {user_id} not sent: {result.get('reason')}")
        except Exception as e:  # never let one user break the loop
            print(f"[scheduler] error for {user_id}: {e}")
    return sent_count


async def _loop() -> None:
    interval = max(1, int(settings.DIGEST_SCHEDULER_INTERVAL_MINUTES)) * 60
    print(f"[scheduler] daily-digest scheduler started (every "
          f"{settings.DIGEST_SCHEDULER_INTERVAL_MINUTES} min)")
    while True:
        try:
            await _tick()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[scheduler] tick failed: {e}")
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            raise


def start() -> None:
    """Start the background scheduler if enabled. Safe to call once at startup."""
    global _task
    if not settings.DIGEST_SCHEDULER_ENABLED:
        return
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop())


async def stop() -> None:
    """Cancel the scheduler task on shutdown."""
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
