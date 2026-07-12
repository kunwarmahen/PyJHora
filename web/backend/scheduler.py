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


# Each cadence: the prefs switch that enables it, the "is it due now?" gate
# (given the user's local datetime + prefs), the claim field that guarantees
# once-per-window delivery, and how to derive that window's claim key.
_CADENCES = [
    {
        "cadence": "daily",
        "switch": "daily_digest",
        "due": lambda local, p: local.hour >= int(p.get("hour", 7)),
        "claim_field": "last_sent_date",
        "claim_key": lambda local: local.strftime("%Y-%m-%d"),
    },
    {
        "cadence": "weekly",
        "switch": "weekly",
        # On the chosen weekday (0=Mon..6=Sun), at/after the chosen hour.
        "due": lambda local, p: (local.weekday() == int(p.get("weekly_dow", 6))
                                 and local.hour >= int(p.get("weekly_hour", 7))),
        "claim_field": "last_sent_weekly",
        "claim_key": lambda local: local.strftime("%G-W%V"),  # ISO year-week
    },
    {
        "cadence": "monthly",
        "switch": "monthly",
        # On the chosen day-of-month (1-28), at/after the chosen hour.
        "due": lambda local, p: (local.day == int(p.get("monthly_dom", 1))
                                 and local.hour >= int(p.get("monthly_hour", 7))),
        "claim_field": "last_sent_monthly",
        "claim_key": lambda local: local.strftime("%Y-%m"),
    },
]


async def _run_cadence(db, spec: dict) -> int:
    """One pass over users who enabled `spec`'s cadence. Returns how many sent.

    "At or after" the preferred hour (rather than only during the exact hour)
    means a missed window — the process was down during that hour — still gets
    the user their reading later that day. The atomic per-window claim keeps this
    idempotent across ticks and across workers."""
    sent_count = 0
    cursor = db[notifications.SETTINGS_COLLECTION].find(
        {f"notifications.{spec['switch']}": True})
    async for doc in cursor:
        user_id = doc.get("user_id")
        if not user_id:
            continue
        prefs = {**notifications.DEFAULT_PREFS, **(doc.get("notifications") or {})}
        try:
            tz = await _profile_tz(user_id, prefs)
            local = _local_now(tz)
            if not spec["due"](local, prefs):
                continue
            claim_field = spec["claim_field"]
            claim_key = spec["claim_key"](local)

            # Atomically claim this window's slot — only the winner sends.
            claimed = await db[notifications.SETTINGS_COLLECTION].find_one_and_update(
                {"user_id": user_id,
                 f"notifications.{claim_field}": {"$ne": claim_key}},
                {"$set": {f"notifications.{claim_field}": claim_key}},
            )
            if not claimed:
                continue  # already sent this window (this worker or another)

            result = await digest.send_digest_for_user(user_id, prefs, spec["cadence"])
            if result.get("status") == "ok":
                sent_count += 1
            else:
                print(f"[scheduler] {spec['cadence']} digest for {user_id} "
                      f"not sent: {result.get('reason')}")
        except Exception as e:  # never let one user break the loop
            print(f"[scheduler] {spec['cadence']} error for {user_id}: {e}")
    return sent_count


async def _tick() -> int:
    """One pass over all digest-enabled users, across every cadence
    (daily/weekly/monthly). Returns how many digests were sent."""
    db = get_database()
    sent_count = 0
    for spec in _CADENCES:
        try:
            sent_count += await _run_cadence(db, spec)
        except Exception as e:
            print(f"[scheduler] {spec['cadence']} pass failed: {e}")
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
