"""Consent + unsubscribe for digest recipients who are not the account owner.

When an owner sets a saved profile's ``notify_email`` to an address other than
their own account email, that person is a *recipient* who must opt in before we
send them anything (double opt-in), and every message we do send carries a
one-click unsubscribe. Consent is tracked per ``(owner, email)`` in the
``digest_recipients`` collection, so several profiles that share one address
share one consent record.

Status:
* ``pending``      — invited, not yet confirmed. No digests are sent.
* ``confirmed``    — opted in. Digests flow.
* ``unsubscribed`` — opted out. No digests, and we never silently re-invite.

The link token is a low-sensitivity capability (it only lets someone confirm or
drop a digest, never reach chart data), so — unlike a password-reset token — it
is stored in the clear and is long-lived: an unsubscribe link printed in an old
email must keep working. The confirm and unsubscribe links carry the same token;
the endpoint path decides the action.
"""
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from database import get_database

COLLECTION = "digest_recipients"

# The three states an (owner, email) consent record can be in.
PENDING = "pending"
CONFIRMED = "confirmed"
UNSUBSCRIBED = "unsubscribed"


def normalize(email: Optional[str]) -> str:
    return (email or "").strip().lower()


async def get(owner_id: str, email: str) -> Optional[Dict[str, Any]]:
    """The consent record for (owner, email), or None if the pair was never invited."""
    email = normalize(email)
    if not email:
        return None
    return await get_database()[COLLECTION].find_one(
        {"user_id": owner_id, "email": email})


async def ensure(owner_id: str, email: str) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Guarantee a consent record exists for (owner, email).

    Returns ``(record, created)``. When the pair is brand new the record is
    created ``pending`` and ``created`` is True, so the caller knows to send the
    confirmation email. When a record already exists — in *any* state — nothing
    changes and ``created`` is False: a standing decision (including an opt-out)
    is never overwritten by re-saving the profile."""
    email = normalize(email)
    if not email:
        return None, False
    coll = get_database()[COLLECTION]
    existing = await coll.find_one({"user_id": owner_id, "email": email})
    if existing:
        return existing, False
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": owner_id,
        "email": email,
        "status": PENDING,
        "token": secrets.token_urlsafe(32),
        "created_at": now,
        "updated_at": now,
    }
    await coll.insert_one(doc)
    return doc, True


async def _by_token(token: str) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    return await get_database()[COLLECTION].find_one({"token": token})


async def confirm(token: str) -> Optional[str]:
    """Opt in via a confirmation link. Returns the email on success (or when the
    link is stale but valid), or None for an unknown token. An address that has
    already unsubscribed is **not** reactivated by a stale confirm link — its
    opt-out stands."""
    doc = await _by_token(token)
    if not doc:
        return None
    if doc.get("status") != UNSUBSCRIBED:
        await _mark(doc, CONFIRMED)
    return doc.get("email")


async def unsubscribe(token: str) -> Optional[str]:
    """Opt out via an unsubscribe link. Returns the email on success, or None for
    an unknown token. Idempotent."""
    doc = await _by_token(token)
    if not doc:
        return None
    await _mark(doc, UNSUBSCRIBED)
    return doc.get("email")


async def _mark(doc: Dict[str, Any], new_status: str) -> None:
    now = datetime.now(timezone.utc)
    await get_database()[COLLECTION].update_one(
        {"_id": doc["_id"]},
        {"$set": {"status": new_status, "updated_at": now, f"{new_status}_at": now}},
    )
