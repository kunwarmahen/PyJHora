"""Per-user rate limiting for the AI endpoints.

A lightweight in-process sliding-window limiter — no extra service. It enforces a
per-minute burst limit and a per-day quota per user. Limits are configurable via
env (`AI_RATE_LIMIT_PER_MIN`, `AI_RATE_LIMIT_PER_DAY`).

NOTE: state lives in this process's memory, so it resets on restart and is not
shared across multiple worker processes. That's fine for the current single-worker
deployment; move to Redis if the app is scaled out.
"""
import os
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Tuple

_MINUTE = 60
_DAY = 24 * 60 * 60


def _limit(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Timestamps (epoch seconds) of recent requests, per user.
_hits: Dict[str, Deque[float]] = defaultdict(deque)

# Failed-login timestamps, keyed by a caller identifier (client IP). A separate
# window from the AI limiter — this blunts password brute-forcing.
_login_fails: Dict[str, Deque[float]] = defaultdict(deque)


def login_allowed(key: str) -> Tuple[bool, int]:
    """Report whether a login attempt from `key` (e.g. client IP) is allowed,
    based on recent *failed* attempts. Returns (allowed, retry_after_seconds).
    Does not record anything — call `login_failed`/`login_succeeded` after."""
    window = _limit("LOGIN_RATE_WINDOW_SEC", 900)   # 15 minutes
    max_fails = _limit("LOGIN_RATE_MAX_FAILS", 10)
    now = time.time()
    fails = _login_fails[key]
    while fails and now - fails[0] > window:
        fails.popleft()
    if len(fails) >= max_fails:
        retry = max(1, int(window - (now - fails[0])) + 1)
        return False, retry
    return True, 0


def login_failed(key: str) -> None:
    """Record a failed login attempt for `key`."""
    _login_fails[key].append(time.time())


def login_succeeded(key: str) -> None:
    """Clear the failure counter for `key` after a successful login."""
    _login_fails.pop(key, None)


def check(user_id: str) -> Tuple[bool, int, str]:
    """Record an attempt and report whether it's allowed.

    Returns (allowed, retry_after_seconds, reason).
    """
    per_min = _limit("AI_RATE_LIMIT_PER_MIN", 20)
    per_day = _limit("AI_RATE_LIMIT_PER_DAY", 300)

    now = time.time()
    hits = _hits[user_id]

    # Drop anything older than a day; it can't affect either window.
    while hits and now - hits[0] > _DAY:
        hits.popleft()

    in_last_min = sum(1 for t in hits if now - t <= _MINUTE)
    if in_last_min >= per_min:
        oldest_in_min = next(t for t in hits if now - t <= _MINUTE)
        retry = max(1, int(_MINUTE - (now - oldest_in_min)) + 1)
        return False, retry, (
            f"Rate limit: max {per_min} questions per minute. "
            f"Try again in {retry}s."
        )

    if len(hits) >= per_day:
        retry = max(1, int(_DAY - (now - hits[0])) + 1)
        return False, retry, (
            f"Daily limit reached ({per_day} questions/day). "
            "Try again tomorrow."
        )

    hits.append(now)
    return True, 0, ""


# ── Anonymous endpoints (§76.7) ─────────────────────────────────────────────
# The landing page's "see your chart" preview runs real chart compute for people
# with no account. Two limits, because the per-caller key is only as good as the
# header it comes from: behind nginx + Cloudflare `request.client.host` is the
# proxy, so the caller is taken from CF-Connecting-IP / X-Forwarded-For — which a
# client talking to the origin directly could forge. The global cap is the floor
# that holds whatever the key: anonymous compute can never take the server.
_public_hits: Dict[str, Deque[float]] = defaultdict(deque)
_public_all: Deque[float] = deque()
_HOUR = 60 * 60


def public_caller(request) -> str:
    """Best-effort caller key for an anonymous request."""
    try:
        h = request.headers
        ip = (h.get("cf-connecting-ip")
              or (h.get("x-forwarded-for") or "").split(",")[0].strip()
              or (request.client.host if request.client else ""))
        return ip or "unknown"
    except Exception:
        return "unknown"


def public_check(key: str) -> Tuple[bool, int]:
    """Record an anonymous request from `key`; (allowed, retry_after_seconds)."""
    per_min = _limit("PUBLIC_RATE_LIMIT_PER_MIN", 10)
    per_day = _limit("PUBLIC_RATE_LIMIT_PER_DAY", 100)
    global_per_hour = _limit("PUBLIC_RATE_LIMIT_GLOBAL_PER_HOUR", 2000)
    now = time.time()

    while _public_all and now - _public_all[0] > _HOUR:
        _public_all.popleft()
    if len(_public_all) >= global_per_hour:
        return False, max(1, int(_HOUR - (now - _public_all[0])) + 1)

    hits = _public_hits[key]
    while hits and now - hits[0] > _DAY:
        hits.popleft()
    recent = [t for t in hits if now - t <= _MINUTE]
    if len(recent) >= per_min:
        return False, max(1, int(_MINUTE - (now - recent[0])) + 1)
    if len(hits) >= per_day:
        return False, max(1, int(_DAY - (now - hits[0])) + 1)

    hits.append(now)
    _public_all.append(now)
    return True, 0
