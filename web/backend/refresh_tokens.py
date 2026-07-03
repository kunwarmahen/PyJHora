"""Refresh tokens — long-lived, revocable credentials for silent re-auth.

The access token (a short-lived JWT) is what every API call carries; it expires
after `ACCESS_TOKEN_EXPIRE_MINUTES`. Rather than log the user out then, the
frontend calls `/api/auth/refresh` with a refresh token to mint a new access
token. Refresh tokens are opaque random strings stored **hashed** (SHA-256) in
the `refresh_tokens` collection so a database leak doesn't expose usable tokens,
and each row can be **revoked** (logout, password change) or **rotated** (a new
token is issued and the old one revoked on every refresh, so a stolen token is
single-use).

Everything is keyed by `username` (the same value auth uses as the JWT `sub` and
that the rest of the app treats as the user id).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from database import get_database

COLLECTION = "refresh_tokens"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Mongo may hand back naive datetimes; treat them as UTC for comparison."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def issue(username: str, days: int) -> str:
    """Create a new refresh token for `username`, valid for `days`. Returns the
    raw token (only time it's ever available in the clear)."""
    token = secrets.token_urlsafe(48)
    now = datetime.now(timezone.utc)
    await get_database()[COLLECTION].insert_one({
        "username": username,
        "token_hash": _hash(token),
        "ttl_days": int(days),
        "created_at": now,
        "expires_at": now + timedelta(days=int(days)),
        "revoked": False,
    })
    return token


async def _valid_doc(token: str) -> Optional[dict]:
    doc = await get_database()[COLLECTION].find_one({"token_hash": _hash(token)})
    if not doc or doc.get("revoked"):
        return None
    exp = _aware(doc.get("expires_at"))
    if exp and exp < datetime.now(timezone.utc):
        return None
    return doc


async def verify(token: str) -> Optional[str]:
    """Return the owning username if the token is live (exists, not revoked, not
    expired), else None."""
    doc = await _valid_doc(token)
    return doc.get("username") if doc else None


async def revoke(token: str) -> None:
    await get_database()[COLLECTION].update_one(
        {"token_hash": _hash(token)}, {"$set": {"revoked": True}}
    )


async def revoke_all(username: str) -> None:
    """Revoke every refresh token for a user (e.g. on password change)."""
    await get_database()[COLLECTION].update_many(
        {"username": username, "revoked": False}, {"$set": {"revoked": True}}
    )


async def rotate(token: str) -> Tuple[Optional[str], Optional[str]]:
    """Validate `token`, revoke it, and issue a replacement with the same TTL.
    Returns (username, new_token) or (None, None) if the token isn't valid."""
    doc = await _valid_doc(token)
    if not doc:
        return None, None
    username = doc["username"]
    days = doc.get("ttl_days", 30)
    await revoke(token)
    new_token = await issue(username, days)
    return username, new_token
