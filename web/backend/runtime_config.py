"""Runtime-editable deployment settings.

A small set of operational knobs that a deployer needs to *tune*, not just set
once — currently the digest scheduler's pacing. They live in a single Mongo
document so an admin can change them from the console and have the next
scheduler tick honour them, with no redeploy and no pod shell.

Design:

  • **Env is the default, Mongo is the override.** Every field falls back to its
    `settings.*` value, so a deployment that never opens the console behaves
    exactly as it did before this module existed, and clearing an override in the
    console genuinely returns the field to the deployed default.

  • **Lateness is expressed in minutes, not attempts.** The scheduler's patience
    used to be `DIGEST_AI_MAX_DEFERRALS` — a retry *count*, whose meaning silently
    depended on the tick interval (6 deferrals at a 15-minute tick is an hour and
    a half of a digest not arriving, which is not what "6" looks like). The knob
    is now `digest_ai_max_delay_minutes` and the retry count is derived from it,
    so what an operator sets is the thing they actually care about: how late a
    digest may be before it goes out without its narrative.

  • **Reads are cached** for a few seconds. The scheduler asks on every tick and
    every user; hitting Mongo for each would be silly, and a knob taking a few
    seconds to bite is fine.
"""
import math
import time
from typing import Any, Dict, Optional

from config import settings
from database import get_database

COLLECTION = "app_config"
DOC_ID = "runtime"

_CACHE_TTL_SECONDS = 5.0
_cache: Optional[Dict[str, Any]] = None
_cache_at = 0.0


def _default_max_delay_minutes() -> int:
    """The deployed default for digest patience, in minutes. Derived from the old
    deferral-count env vars so an existing deployment keeps its exact behaviour
    (6 × 15 = 90 minutes) without anyone having to set a new variable."""
    try:
        return max(0, int(settings.DIGEST_AI_MAX_DEFERRALS)
                   * max(1, int(settings.DIGEST_SCHEDULER_INTERVAL_MINUTES)))
    except (TypeError, ValueError):
        return 90


# name → (default factory, coercer). The coercer both casts and clamps, so a bad
# value from the API or a hand-edited document can never put the scheduler into a
# nonsensical state (a 0-minute tick would spin; a 90-minute one would miss hours).
def _clamp_int(lo: int, hi: int):
    def _coerce(v):
        return max(lo, min(hi, int(v)))
    return _coerce


FIELDS = {
    # Master switch. Env sets the default; the console can flip it either way at
    # runtime, which is why the scheduler task always runs and checks this rather
    # than being spawned conditionally.
    "digest_scheduler_enabled": (
        lambda: bool(settings.DIGEST_SCHEDULER_ENABLED), bool),
    # Must stay under 60 so every target hour is caught by at least one tick.
    "digest_scheduler_interval_minutes": (
        lambda: max(1, int(settings.DIGEST_SCHEDULER_INTERVAL_MINUTES)),
        _clamp_int(1, 59)),
    # How late a digest may be while waiting for a busy LLM. 0 disables waiting
    # entirely: the digest goes out immediately with its rule-based highlights.
    "digest_ai_max_delay_minutes": (
        _default_max_delay_minutes, _clamp_int(0, 720)),
}


def defaults() -> Dict[str, Any]:
    return {name: factory() for name, (factory, _) in FIELDS.items()}


def _coerce(name: str, value: Any) -> Any:
    _, coercer = FIELDS[name]
    return coercer(value)


async def get() -> Dict[str, Any]:
    """Effective settings: env defaults with any stored overrides applied."""
    global _cache, _cache_at
    now = time.monotonic()
    if _cache is not None and now - _cache_at < _CACHE_TTL_SECONDS:
        return dict(_cache)
    values = defaults()
    try:
        doc = await get_database()[COLLECTION].find_one({"_id": DOC_ID})
    except Exception as e:  # DB down — the deployed defaults still work
        print(f"[runtime_config] read failed, using defaults: {e}")
        doc = None
    for name in FIELDS:
        if doc and name in doc:
            try:
                values[name] = _coerce(name, doc[name])
            except (TypeError, ValueError):
                pass
    _cache, _cache_at = dict(values), now
    return values


def invalidate() -> None:
    global _cache, _cache_at
    _cache, _cache_at = None, 0.0


async def set_values(updates: Dict[str, Any]) -> Dict[str, Any]:
    """Apply overrides (unknown keys ignored). A value of None clears the override
    and returns that field to its deployed default. Returns the new effective
    settings."""
    to_set: Dict[str, Any] = {}
    to_unset: Dict[str, Any] = {}
    for name, value in (updates or {}).items():
        if name not in FIELDS:
            continue
        if value is None:
            to_unset[name] = ""
        else:
            try:
                to_set[name] = _coerce(name, value)
            except (TypeError, ValueError):
                continue
    update: Dict[str, Any] = {}
    if to_set:
        update["$set"] = to_set
    if to_unset:
        update["$unset"] = to_unset
    if update:
        await get_database()[COLLECTION].update_one({"_id": DOC_ID}, update, upsert=True)
    invalidate()
    return await get()


async def overrides() -> Dict[str, Any]:
    """Only the fields explicitly overridden in Mongo — so the console can show
    what has been changed away from the deployed default."""
    try:
        doc = await get_database()[COLLECTION].find_one({"_id": DOC_ID})
    except Exception:
        return {}
    return {k: v for k, v in (doc or {}).items() if k in FIELDS}


def max_deferrals(cfg: Dict[str, Any]) -> int:
    """How many ticks of patience `digest_ai_max_delay_minutes` buys at the
    configured interval. Rounded up so the configured delay is honoured in full
    rather than truncated away by an awkward interval."""
    interval = max(1, int(cfg.get("digest_scheduler_interval_minutes") or 1))
    delay = max(0, int(cfg.get("digest_ai_max_delay_minutes") or 0))
    return int(math.ceil(delay / interval))
