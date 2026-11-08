"""API tokens — long-lived, per-user credentials for the public API + MCP (§2.3).

Unlike the short-lived access JWT (browser sessions) and the refresh token
(silent re-auth), an API token is a **user-managed** credential created under
Settings → API access and pasted into a script or an MCP client (Claude Desktop).
It authenticates the token-authed, read-only `/api/v1/*` surface.

Design (mirrors `refresh_tokens.py`):
- The token is an opaque random string with a `jyd_` prefix so it's recognisable
  in logs/config; only the **SHA-256 hash** is stored (a DB leak exposes no usable
  token). The raw value is shown to the user exactly once, at creation.
- Each row carries a human `label`, `created_at`, and `last_used_at` (bumped on
  use, best-effort) so the user can tell their tokens apart and revoke a stale one.
- Each token carries a **profile scope** (which saved profiles an MCP client /
  script may see and run tools on). `profile_ids: None` — the default — means
  *every* profile, including ones created after the token; a list pins it to
  exactly those ids. Enforced in `routes/v1.py`, nowhere else (the scope only
  narrows the public API; a session JWT is never scoped).
- Everything is keyed by `username` (the value auth uses as the JWT `sub` and the
  rest of the app treats as the user id).
"""
import hashlib
import secrets
from datetime import datetime, timezone
from typing import List, Optional

from bson import ObjectId

from database import get_database

COLLECTION = "api_tokens"
TOKEN_PREFIX = "jyd_"
# Cap per user so a runaway script can't create unbounded rows.
MAX_TOKENS_PER_USER = 20


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _preview(token: str) -> str:
    """A non-secret hint shown in the list UI, e.g. 'jyd_…a1b2'."""
    return f"{TOKEN_PREFIX}…{token[-4:]}"


def _clean_scope(profile_ids: Optional[List[str]]) -> Optional[List[str]]:
    """None stays None (all profiles, now and future); a list is de-duplicated."""
    if profile_ids is None:
        return None
    return list(dict.fromkeys(str(p) for p in profile_ids if p))


def profile_allowed(scope: Optional[List[str]], profile_id: Optional[str]) -> bool:
    """Whether a token with `scope` may touch `profile_id`. None = every profile."""
    return scope is None or (profile_id is not None and str(profile_id) in scope)


async def issue(username: str, label: str = "",
                profile_ids: Optional[List[str]] = None) -> Optional[str]:
    """Create a new API token for `username`. Returns the raw token (only time
    it's ever available in the clear), or None if the per-user cap is hit.
    `profile_ids=None` scopes it to all profiles, including future ones."""
    coll = get_database()[COLLECTION]
    count = await coll.count_documents({"username": username, "revoked": False})
    if count >= MAX_TOKENS_PER_USER:
        return None
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    await coll.insert_one({
        "username": username,
        "token_hash": _hash(token),
        "label": (label or "").strip()[:80] or "API token",
        "preview": _preview(token),
        "created_at": now,
        "last_used_at": None,
        "revoked": False,
        "profile_ids": _clean_scope(profile_ids),
    })
    return token


async def verify(token: str) -> Optional[str]:
    """Return the owning username if the token is live (exists, not revoked),
    else None. Bumps `last_used_at` best-effort."""
    info = await verify_scoped(token)
    return info["username"] if info else None


async def verify_scoped(token: str) -> Optional[dict]:
    """Like `verify`, but returns `{"username", "profile_ids"}` so the caller can
    enforce the token's profile scope. Tokens minted before scoping existed have
    no field and read as None — all profiles, which is what they always had."""
    if not token or not token.startswith(TOKEN_PREFIX):
        return None
    coll = get_database()[COLLECTION]
    doc = await coll.find_one({"token_hash": _hash(token)})
    if not doc or doc.get("revoked"):
        return None
    # Best-effort usage stamp; never let a write failure break auth.
    try:
        await coll.update_one(
            {"_id": doc["_id"]},
            {"$set": {"last_used_at": datetime.now(timezone.utc)}},
        )
    except Exception:
        pass
    return {"username": doc.get("username"),
            "profile_ids": _clean_scope(doc.get("profile_ids"))}


async def list_tokens(username: str) -> List[dict]:
    """The user's live tokens as safe metadata (never the hash or raw token)."""
    coll = get_database()[COLLECTION]
    docs = await coll.find(
        {"username": username, "revoked": False}
    ).sort("created_at", -1).to_list(MAX_TOKENS_PER_USER)
    return [{
        "id": str(d["_id"]),
        "label": d.get("label", "API token"),
        "preview": d.get("preview", ""),
        "created_at": d.get("created_at"),
        "last_used_at": d.get("last_used_at"),
        "profile_ids": _clean_scope(d.get("profile_ids")),
    } for d in docs]


async def set_scope(username: str, token_id: str,
                    profile_ids: Optional[List[str]]) -> bool:
    """Change which profiles a live token may see (None = all, incl. future)."""
    try:
        oid = ObjectId(token_id)
    except Exception:
        return False
    res = await get_database()[COLLECTION].update_one(
        {"_id": oid, "username": username, "revoked": False},
        {"$set": {"profile_ids": _clean_scope(profile_ids)}},
    )
    return res.matched_count == 1


async def revoke(username: str, token_id: str) -> bool:
    """Revoke one token by id (scoped to the owner). Returns True if a live token
    was revoked."""
    try:
        oid = ObjectId(token_id)
    except Exception:
        return False
    res = await get_database()[COLLECTION].update_one(
        {"_id": oid, "username": username, "revoked": False},
        {"$set": {"revoked": True}},
    )
    return res.modified_count == 1


async def revoke_all(username: str) -> None:
    """Revoke every API token for a user (e.g. on account deletion)."""
    await get_database()[COLLECTION].update_many(
        {"username": username, "revoked": False}, {"$set": {"revoked": True}}
    )
