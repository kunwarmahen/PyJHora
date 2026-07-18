"""Admin console backend (§44).

A deployer-only superuser surface for operating the deployment: see every
registered account, aggregate usage, drill into (gated) content, and moderate
(suspend / delete). Design decisions that matter:

  • ADMIN_USERNAMES (env) is the SOURCE OF TRUTH for who is an admin. The app
    never expects an operator to open Mongo (it's pod-internal) — you grant
    admin by editing the deploy secret. `reconcile_admins()` mirrors that env
    list onto the `is_admin` flag at startup so removing someone from the env
    revokes them on the next deploy. `is_admin_user()` also checks the env list
    live, so a freshly-registered admin works before the next reconcile.

  • Content drill-down (a user's real readings/chats/journal/birth data) is
    gated behind ADMIN_CONTENT_ACCESS — OFF by default. Metadata + counts are
    always available; private content is "break glass" only. Every content view
    and every moderation action is written to the `admin_audit` collection.

  • This module owns the map of which collections hold per-user data and which
    field keys them, so counts and cascade-delete stay correct as collections
    are added.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from config import settings


# ── Which collections hold per-user data, and the field that keys them ───────
# The value stored in that field is always the username string. Keep this in
# sync when a new per-user collection is introduced — cascade-delete and the
# per-user counts both read from here.
USER_COLLECTIONS: Dict[str, str] = {
    "saved_profiles": "user_id",
    "ai_conversations": "user_id",
    "journal_entries": "user_id",
    "ai_tool_traces": "user_id",
    "user_settings": "user_id",
    "push_subscriptions": "user_id",
    "quiz_sessions": "user_id",
    "shared_charts": "user_id",
    "digest_recipients": "user_id",
    "digest_signals": "user_id",
    "api_tokens": "username",
    "refresh_tokens": "username",
    "password_reset_tokens": "username",
}

# The subset we surface as headline per-user counts in the console (the churny
# token/settings collections are noise in the UI, though they're still deleted).
COUNT_COLLECTIONS = [
    "saved_profiles",
    "ai_conversations",
    "journal_entries",
    "ai_tool_traces",
    "quiz_sessions",
    "shared_charts",
]

AUDIT_COLLECTION = "admin_audit"


def _db():
    from database import database
    if database is None:
        raise RuntimeError("Database not connected")
    return database


# ── Admin identity ───────────────────────────────────────────────────────────

def admin_identities() -> set:
    """The lower-cased set of admin usernames/emails from the env allowlist."""
    raw = settings.ADMIN_USERNAMES or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def is_admin_user(username: str, user_doc: Optional[dict] = None) -> bool:
    """True if `username` is an admin. The env allowlist is authoritative (matches
    by username OR email); the DB `is_admin` flag is a reconciled convenience and
    also honoured so a promoted account keeps working between deploys."""
    ids = admin_identities()
    uname = (username or "").strip().lower()
    if uname and uname in ids:
        return True
    if user_doc:
        if user_doc.get("is_admin"):
            return True
        if (user_doc.get("email") or "").strip().lower() in ids:
            return True
    return False


async def reconcile_admins() -> Dict[str, int]:
    """Mirror ADMIN_USERNAMES onto the `is_admin` flag. Runs at startup: grants the
    flag to every matching account and revokes it from any account no longer
    listed. Returns {granted, revoked} counts. No-op-safe if the DB is down."""
    try:
        users = _db()["users"]
    except RuntimeError:
        return {"granted": 0, "revoked": 0}
    ids = admin_identities()
    granted = revoked = 0
    async for u in users.find({}, {"username": 1, "email": 1, "is_admin": 1}):
        uname = (u.get("username") or "").strip().lower()
        email = (u.get("email") or "").strip().lower()
        should = bool(uname in ids or (email and email in ids))
        has = bool(u.get("is_admin"))
        if should and not has:
            await users.update_one({"_id": u["_id"]}, {"$set": {"is_admin": True}})
            granted += 1
        elif has and not should:
            await users.update_one({"_id": u["_id"]}, {"$set": {"is_admin": False}})
            revoked += 1
    return {"granted": granted, "revoked": revoked}


def content_access_enabled() -> bool:
    return bool(settings.ADMIN_CONTENT_ACCESS)


# ── Suspension enforcement (called from the auth routes) ─────────────────────

async def assert_not_suspended(username: str) -> None:
    """Raise 403 if the account is suspended. Called on login and refresh so a
    moderator's suspend takes effect within one access-token lifetime."""
    from fastapi import HTTPException
    doc = await _db()["users"].find_one({"username": username}, {"suspended": 1})
    if doc and doc.get("suspended"):
        raise HTTPException(status_code=403, detail="This account has been suspended.")


# ── Aggregates ───────────────────────────────────────────────────────────────

async def global_stats() -> Dict[str, Any]:
    """Deployment-wide totals for the console overview."""
    db = _db()
    users = db["users"]
    total_users = await users.count_documents({})
    suspended = await users.count_documents({"suspended": True})
    admins = await users.count_documents({"is_admin": True})
    google = await users.count_documents({"auth_provider": "google"})
    now = datetime.now(timezone.utc)
    # New users in the last 7 / 30 days. created_at is stored as an ISO string in
    # some rows and a datetime in others; a string range compare works for ISO.
    def _iso_days_ago(n):
        from datetime import timedelta
        return (now - timedelta(days=n)).isoformat()
    new_7d = await users.count_documents({"created_at": {"$gte": _iso_days_ago(7)}})
    new_30d = await users.count_documents({"created_at": {"$gte": _iso_days_ago(30)}})
    collections = {}
    for name in COUNT_COLLECTIONS:
        try:
            collections[name] = await db[name].count_documents({})
        except Exception:
            collections[name] = 0
    return {
        "total_users": total_users,
        "suspended": suspended,
        "admins": admins,
        "google_accounts": google,
        "new_users_7d": new_7d,
        "new_users_30d": new_30d,
        "content_access_enabled": content_access_enabled(),
        "collections": collections,
    }


async def _counts_for(username: str) -> Dict[str, int]:
    db = _db()
    out = {}
    for name in COUNT_COLLECTIONS:
        field = USER_COLLECTIONS[name]
        try:
            out[name] = await db[name].count_documents({field: username})
        except Exception:
            out[name] = 0
    return out


async def list_users(query: str = "", limit: int = 200) -> List[Dict[str, Any]]:
    """All accounts (metadata + headline counts), newest first. `query` filters by
    username/email substring. Never returns password hashes or tokens."""
    db = _db()
    mongo_q: Dict[str, Any] = {}
    if query:
        import re
        rx = {"$regex": re.escape(query), "$options": "i"}
        mongo_q = {"$or": [{"username": rx}, {"email": rx}, {"name": rx}]}
    rows: List[Dict[str, Any]] = []
    cursor = db["users"].find(mongo_q).sort("created_at", -1).limit(limit)
    async for u in cursor:
        username = u.get("username")
        rows.append({
            "username": username,
            "email": u.get("email"),
            "name": u.get("name"),
            "created_at": u.get("created_at"),
            "auth_provider": u.get("auth_provider") or "password",
            "is_admin": bool(u.get("is_admin")) or is_admin_user(username, u),
            "suspended": bool(u.get("suspended")),
            "counts": await _counts_for(username),
        })
    return rows


async def user_detail(username: str) -> Optional[Dict[str, Any]]:
    db = _db()
    u = await db["users"].find_one({"username": username})
    if not u:
        return None
    return {
        "username": username,
        "email": u.get("email"),
        "name": u.get("name"),
        "created_at": u.get("created_at"),
        "auth_provider": u.get("auth_provider") or "password",
        "has_password": bool(u.get("hashed_password")),
        "is_admin": bool(u.get("is_admin")) or is_admin_user(username, u),
        "suspended": bool(u.get("suspended")),
        "counts": await _counts_for(username),
    }


# ── Content drill-down (gated) ───────────────────────────────────────────────

async def user_content(username: str, kind: str, limit: int = 100) -> List[Dict[str, Any]]:
    """A page of a user's actual content. Caller MUST have already checked
    content_access_enabled() and audit-logged the access. `kind` is one of the
    COUNT_COLLECTIONS names. ObjectIds are stringified for JSON."""
    if kind not in USER_COLLECTIONS:
        return []
    db = _db()
    field = USER_COLLECTIONS[kind]
    rows = []
    async for doc in db[kind].find({field: username}).limit(limit):
        doc["_id"] = str(doc.get("_id", ""))
        rows.append(doc)
    return rows


# ── Moderation ───────────────────────────────────────────────────────────────

async def set_suspended(username: str, suspended: bool) -> bool:
    res = await _db()["users"].update_one(
        {"username": username}, {"$set": {"suspended": bool(suspended)}})
    return res.matched_count > 0


async def delete_user(username: str) -> Dict[str, int]:
    """Cascade-delete an account and every trace of it across all per-user
    collections. Returns per-collection deleted counts."""
    db = _db()
    deleted: Dict[str, int] = {}
    for name, field in USER_COLLECTIONS.items():
        try:
            res = await db[name].delete_many({field: username})
            deleted[name] = res.deleted_count
        except Exception:
            deleted[name] = 0
    res = await db["users"].delete_one({"username": username})
    deleted["users"] = res.deleted_count
    return deleted


# ── Audit log ────────────────────────────────────────────────────────────────

async def audit(admin: str, action: str, target: Optional[str] = None,
                detail: Optional[str] = None, ip: Optional[str] = None) -> None:
    try:
        await _db()[AUDIT_COLLECTION].insert_one({
            "admin": admin,
            "action": action,
            "target": target,
            "detail": detail,
            "ip": ip,
            "at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:  # auditing must never break the operation it records
        print(f"[admin.audit] failed to record {action}: {e}")


async def list_audit(limit: int = 200) -> List[Dict[str, Any]]:
    rows = []
    async for doc in _db()[AUDIT_COLLECTION].find({}).sort("at", -1).limit(limit):
        doc["_id"] = str(doc.get("_id", ""))
        rows.append(doc)
    return rows
