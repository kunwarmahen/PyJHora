"""Password-reset tokens — short-lived, single-use, stored hashed.

Mirrors the `refresh_tokens` design: the raw token is a random URL-safe string
returned only once (embedded in the emailed link); only its SHA-256 hash is
stored in the `password_reset_tokens` collection, so a database leak can't be
used to reset anyone's password. A token is consumed (marked used) the moment a
successful reset happens, and it expires after `PASSWORD_RESET_TTL_MINUTES`.

Keyed by `username` (the app's user id, same as auth's JWT `sub`).
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from config import settings
from database import get_database

COLLECTION = "password_reset_tokens"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


async def issue(username: str) -> str:
    """Create a reset token for `username`. Any earlier unused tokens for the
    same user are invalidated first (only the newest link should work). Returns
    the raw token (the only time it is available in the clear)."""
    now = datetime.now(timezone.utc)
    coll = get_database()[COLLECTION]
    await coll.update_many(
        {"username": username, "used": False}, {"$set": {"used": True}}
    )
    token = secrets.token_urlsafe(48)
    await coll.insert_one({
        "username": username,
        "token_hash": _hash(token),
        "created_at": now,
        "expires_at": now + timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES),
        "used": False,
    })
    return token


async def consume(token: str) -> Optional[str]:
    """Validate + single-use consume a token. Returns the owning username if the
    token exists, is unused and unexpired (and atomically marks it used), else
    None."""
    if not token:
        return None
    coll = get_database()[COLLECTION]
    doc = await coll.find_one({"token_hash": _hash(token)})
    if not doc or doc.get("used"):
        return None
    exp = _aware(doc.get("expires_at"))
    if exp and exp < datetime.now(timezone.utc):
        return None
    res = await coll.update_one(
        {"_id": doc["_id"], "used": False}, {"$set": {"used": True}}
    )
    if res.modified_count != 1:
        # Lost a race — another request consumed it first.
        return None
    return doc.get("username")
