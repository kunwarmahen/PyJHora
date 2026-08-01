"""In-process daily-digest scheduler.

An opt-in asyncio background task (enabled with `DIGEST_SCHEDULER_ENABLED=true`,
or from the admin console at runtime) that wakes every tick interval and, for
each user who has
the daily digest enabled, delivers it once per day at *or after* their preferred
local hour — local meaning **where the user is now** (their current location's
zone, DST-aware), falling back to the target birth profile's fixed offset when
they haven't set one. "At or after"
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

**Pacing is runtime-editable.** The enable switch, the tick interval and how late
a digest may be while waiting for a busy LLM all come from `runtime_config` (env
defaults, Mongo overrides) and are re-read on every tick — so an admin can retune
delivery from the console without a redeploy. That is also why the loop task runs
unconditionally and checks the switch each pass, rather than being spawned only
when the env var is set.
"""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import settings
from database import get_database
import digest
import notifications
import runtime_config
import timezones
import user_settings

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


async def _user_local_now(user_id: str, prefs: dict) -> datetime:
    """The wall-clock time it is *for this user*, which is what "is it 7am yet?"
    has to be asked of.

    Their **current location** wins: someone born in India and living in the US
    wants the 7am digest at 7am where they are, not 7am IST (which is 8:30pm the
    previous evening for them — the bug this exists to fix). Zone-based, so it's
    DST-correct year round.

    Falling back to the birth profile's fixed offset when no current location is
    set preserves the old behaviour exactly, which stays right for the many users
    who still live where they were born.
    """
    loc = await user_settings.get_current_location(user_id)
    if loc:
        local = timezones.local_now(loc.get("timezone"))
        if local is not None:
            return local
    return _local_now(await _profile_tz(user_id, prefs))


# Each cadence: the prefs switch that enables it, the "is it due now?" gate
# (given the user's local datetime + prefs), the claim field that guarantees
# once-per-window delivery, and how to derive that window's claim key.
#
# Daily and monthly are calendar-scheduled (a date / a day-of-month). The
# **fortnightly** cadence is different: the *paksha boundary is the schedule*.
# Its claim key is the current paksha's start date, so the key only changes when
# a new Shukla/Krishna fortnight opens — which makes the send fire exactly once
# per paksha, with no day-picker needed (only an hour).
_CADENCES = [
    {
        "cadence": "daily",
        "switch": "daily_digest",
        "due": lambda local, p: local.hour >= int(p.get("hour", 7)),
        "claim_field": "last_sent_date",
        "claim_key": lambda local: local.strftime("%Y-%m-%d"),
    },
    {
        "cadence": "fortnightly",
        "switch": "fortnightly",
        # Any day, at/after the chosen hour — the paksha claim key does the gating.
        "due": lambda local, p: local.hour >= int(p.get("fortnightly_hour", 7)),
        "claim_field": "last_sent_fortnightly",
        "claim_key": None,  # resolved per-user from the running paksha (see below)
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


async def _paksha_claim_key(user_id: str, prefs: dict, local) -> Optional[str]:
    """The running paksha's start date, used as the fortnightly claim key. Derived
    from the pacing profile's place (a paksha is a sky event, so any of the user's
    places gives the same fortnight to within a few hours)."""
    from astrology import AstrologyCompute
    import swisseph as swe

    profiles = await digest.resolve_profiles(user_id, prefs)
    if not profiles:
        return None
    bd = (profiles[0].get("birth_details") or {})
    try:
        from jhora.panchanga import drik
        place = drik.Place(bd.get("place", ""), bd.get("latitude") or 13.0827,
                           bd.get("longitude") or 80.2707,
                           float(bd.get("timezone") or 0.0))
        jd = swe.julday(local.year, local.month, local.day, 12.0)
        w = AstrologyCompute._paksha_window(jd, place)
        from jhora import utils
        sy, sm, sd, _ = utils.jd_to_gregorian(w["start_jd"])
        return f"{w['paksha']}-{sy:04d}-{sm:02d}-{sd:02d}"
    except Exception as e:
        print(f"[scheduler] paksha claim-key failed for {user_id}: {e}")
        return None


def _defer_field(claim_field: str) -> str:
    return f"{claim_field}_defer"


def _deferrals_so_far(settings_doc: dict, claim_field: str, claim_key: str) -> int:
    """How many times this *same* window has already been put off. Keyed by the
    claim key so yesterday's deferrals never count against today."""
    rec = ((settings_doc.get("notifications") or {}).get(_defer_field(claim_field))
           or {})
    return int(rec.get("count") or 0) if rec.get("key") == claim_key else 0


async def _defer(db, user_id: str, claim_field: str, claim_key: str,
                 settings_doc: dict, deferrals: int) -> None:
    """Give the claim back so a later tick retries this window.

    Releasing the claim is the whole mechanism: the tick already won it, and
    without a rollback the "at or after the preferred hour" rule would treat the
    window as served and the user would simply never get this digest. Restoring
    the *previous* value (rather than clearing the field) keeps the older windows
    it stands for still-claimed."""
    prev = (settings_doc.get("notifications") or {}).get(claim_field)
    update = {"$set": {f"notifications.{_defer_field(claim_field)}":
                       {"key": claim_key, "count": deferrals + 1}}}
    if prev is None:
        update["$unset"] = {f"notifications.{claim_field}": ""}
    else:
        update["$set"][f"notifications.{claim_field}"] = prev
    await db[notifications.SETTINGS_COLLECTION].update_one({"user_id": user_id}, update)


async def _clear_deferrals(db, user_id: str, claim_field: str) -> None:
    await db[notifications.SETTINGS_COLLECTION].update_one(
        {"user_id": user_id},
        {"$unset": {f"notifications.{_defer_field(claim_field)}": ""}})


async def _run_cadence(db, spec: dict, max_deferrals: int) -> int:
    """One pass over users who enabled `spec`'s cadence. Returns how many sent.

    "At or after" the preferred hour (rather than only during the exact hour)
    means a missed window — the process was down during that hour — still gets
    the user their reading later that day. The atomic per-window claim keeps this
    idempotent across ticks and across workers.

    `max_deferrals` is the tick-budget derived from the configured maximum
    delivery delay; it is passed in so every cadence in a tick uses one
    consistent reading of the runtime config."""
    sent_count = 0
    cursor = db[notifications.SETTINGS_COLLECTION].find(
        {f"notifications.{spec['switch']}": True})
    async for doc in cursor:
        user_id = doc.get("user_id")
        if not user_id:
            continue
        prefs = {**notifications.DEFAULT_PREFS, **(doc.get("notifications") or {})}
        try:
            local = await _user_local_now(user_id, prefs)
            if not spec["due"](local, prefs):
                continue
            claim_field = spec["claim_field"]
            if spec["claim_key"] is None:  # fortnightly → key off the running paksha
                claim_key = await _paksha_claim_key(user_id, prefs, local)
                if not claim_key:
                    continue
            else:
                claim_key = spec["claim_key"](local)

            # Atomically claim this window's slot — only the winner sends.
            claimed = await db[notifications.SETTINGS_COLLECTION].find_one_and_update(
                {"user_id": user_id,
                 f"notifications.{claim_field}": {"$ne": claim_key}},
                {"$set": {f"notifications.{claim_field}": claim_key}},
            )
            if not claimed:
                continue  # already sent this window (this worker or another)

            deferrals = _deferrals_so_far(claimed, claim_field, claim_key)
            result = await digest.send_digest_for_user(
                user_id, prefs, spec["cadence"],
                allow_defer=deferrals < max_deferrals)
            if result.get("status") == "deferred":
                await _defer(db, user_id, claim_field, claim_key, claimed, deferrals)
                print(f"[scheduler] {spec['cadence']} digest for {user_id} deferred "
                      f"({result.get('reason')}); attempt {deferrals + 1} of "
                      f"{max_deferrals}")
            elif result.get("status") == "ok":
                await _clear_deferrals(db, user_id, claim_field)
                sent_count += 1
            else:
                await _clear_deferrals(db, user_id, claim_field)
                print(f"[scheduler] {spec['cadence']} digest for {user_id} "
                      f"not sent: {result.get('reason')}")
        except Exception as e:  # never let one user break the loop
            print(f"[scheduler] {spec['cadence']} error for {user_id}: {e}")
    return sent_count


async def _tick(max_deferrals: Optional[int] = None) -> int:
    """One pass over all digest-enabled users, across every cadence
    (daily/weekly/monthly). Returns how many digests were sent."""
    db = get_database()
    if max_deferrals is None:
        max_deferrals = runtime_config.max_deferrals(await runtime_config.get())
    sent_count = 0
    for spec in _CADENCES:
        try:
            sent_count += await _run_cadence(db, spec, max_deferrals)
        except Exception as e:
            print(f"[scheduler] {spec['cadence']} pass failed: {e}")
    return sent_count


async def _loop() -> None:
    """Tick forever, re-reading the runtime config each pass.

    Both the switch and the interval are read per-iteration on purpose: an admin
    who turns the scheduler on, or shortens the tick, should see it take effect
    within one cycle rather than at the next deploy. When the scheduler is off the
    loop idles at the configured interval and touches nothing."""
    announced = None
    while True:
        try:
            cfg = await runtime_config.get()
        except Exception as e:
            print(f"[scheduler] config read failed, using defaults: {e}")
            cfg = runtime_config.defaults()
        enabled = bool(cfg.get("digest_scheduler_enabled"))
        interval_min = max(1, int(cfg.get("digest_scheduler_interval_minutes") or 15))
        state = (enabled, interval_min)
        if state != announced:
            announced = state
            print(f"[scheduler] digest scheduler {'running' if enabled else 'idle'} "
                  f"(every {interval_min} min, patience "
                  f"{cfg.get('digest_ai_max_delay_minutes')} min)")
        if enabled:
            try:
                await _tick(runtime_config.max_deferrals(cfg))
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"[scheduler] tick failed: {e}")
        try:
            await asyncio.sleep(interval_min * 60)
        except asyncio.CancelledError:
            raise


def start() -> None:
    """Start the background scheduler task. Safe to call once at startup.

    The task starts regardless of the enable switch — the switch is runtime-
    editable, so the loop has to be alive to notice it being turned on. An idle
    loop costs one sleeping coroutine."""
    global _task
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
