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

  • `admin_audit` holds two *categories* of row. "moderation" is what an admin
    did (suspend, delete, break-glass content view). "security" is what the
    deployment did on its own — registrations, logins, failed logins, password
    resets, API tokens. They share one collection (and one retention policy) but
    the console filters them apart, because "who did what to whom" and "what has
    been happening" are different questions. Rows written before this split
    carry no category and are read as moderation, which is what they were.

  • The **activity feed** is deliberately NOT a log: it is derived on read from
    the collections that already exist (users, conversations, journal, quiz,
    shares, digests). That means it works retroactively over data recorded long
    before any of this was written, and costs nothing to keep.

  • This module owns the map of which collections hold per-user data and which
    field keys them, so counts and cascade-delete stay correct as collections
    are added.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

from config import settings


# ── Which collections hold per-user data, and the field that keys them ───────
# The value stored in that field is always the username string. Keep this in
# sync when a new per-user collection is introduced — cascade-delete and the
# per-user counts both read from here.
USER_COLLECTIONS: Dict[str, str] = {
    "saved_profiles": "user_id",
    "charts": "user_id",
    "ai_conversations": "user_id",
    "journal_entries": "user_id",
    "ai_tool_traces": "user_id",
    "user_settings": "user_id",
    "push_subscriptions": "user_id",
    "quiz_sessions": "user_id",
    "shared_charts": "user_id",
    "digest_recipients": "user_id",
    "digest_signals": "user_id",
    "digest_readings": "user_id",
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
    "digest_readings",
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

MODERATION = "moderation"
SECURITY = "security"

# Security actions the deployment records about itself. Listed here (rather than
# accepted as free text) so the console can offer a real filter dropdown and so a
# typo at a call site shows up as an unknown action instead of a silent new
# category. Keep the vocabulary small — one entry per thing worth answering
# "when did this last happen?" about.
SECURITY_ACTIONS = [
    "register",
    "login",
    "login_failed",
    "login_blocked",       # rate-limited before the password was even checked
    "login_suspended",     # correct password, but the account is suspended
    "google_signin",
    "logout_all",
    "password_changed",
    "password_reset_requested",
    "password_reset_completed",
    "email_changed",
    "api_token_created",
    "api_token_revoked",
    "account_self_deleted",
    "admin_console_opened",
]

# Never let the audit collection grow without bound — logins alone would do it.
_last_prune_at = 0.0
_PRUNE_EVERY_SECONDS = 3600


def _retention_days() -> int:
    try:
        return max(1, int(settings.ADMIN_AUDIT_RETENTION_DAYS))
    except (TypeError, ValueError):
        return 90


async def _prune_audit() -> int:
    """Drop audit rows past the retention horizon. `at` is an ISO-8601 UTC string,
    so a plain string range compare is a correct (and index-friendly) date compare.
    Rate-limited to once an hour — this is called from the write path."""
    global _last_prune_at
    now = time.monotonic()
    if now - _last_prune_at < _PRUNE_EVERY_SECONDS:
        return 0
    _last_prune_at = now
    cutoff = (datetime.now(timezone.utc) - timedelta(days=_retention_days())).isoformat()
    try:
        res = await _db()[AUDIT_COLLECTION].delete_many({"at": {"$lt": cutoff}})
        return res.deleted_count
    except Exception as e:
        print(f"[admin.audit] prune failed: {e}")
        return 0


async def _write_audit(category: str, actor: Optional[str], action: str,
                       target: Optional[str], detail: Optional[str],
                       ip: Optional[str]) -> None:
    try:
        await _db()[AUDIT_COLLECTION].insert_one({
            "category": category,
            # Historically named `admin`; for a security row it is the account the
            # event is about (or None for an anonymous attempt). Kept under the old
            # key so rows written before the split still read back the same way.
            "admin": actor,
            "action": action,
            "target": target,
            "detail": detail,
            "ip": ip,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        await _prune_audit()
    except Exception as e:  # auditing must never break the operation it records
        print(f"[admin.audit] failed to record {action}: {e}")


async def audit(admin: str, action: str, target: Optional[str] = None,
                detail: Optional[str] = None, ip: Optional[str] = None) -> None:
    """Record a moderation action — something an admin did through the console."""
    await _write_audit(MODERATION, admin, action, target, detail, ip)


async def security_event(action: str, actor: Optional[str] = None,
                         target: Optional[str] = None,
                         detail: Optional[str] = None,
                         ip: Optional[str] = None) -> None:
    """Record a security event the deployment generated about itself (a login, a
    reset, a token). Best-effort and never raises: an audit write must not be able
    to fail a login. Call sites pass no request body or content — only who, what,
    and from where."""
    await _write_audit(SECURITY, actor, action, target, detail, ip)


async def list_audit(limit: int = 200, category: Optional[str] = None,
                     action: Optional[str] = None, actor: Optional[str] = None,
                     target: Optional[str] = None,
                     since_days: Optional[int] = None) -> List[Dict[str, Any]]:
    """Audit rows newest-first, with optional filters. `category=moderation` also
    matches the pre-split rows that carry no category field at all."""
    q: Dict[str, Any] = {}
    if category == MODERATION:
        q["$or"] = [{"category": MODERATION}, {"category": {"$exists": False}}]
    elif category:
        q["category"] = category
    if action:
        q["action"] = action
    if actor:
        q["admin"] = actor
    if target:
        import re
        q["target"] = {"$regex": re.escape(target), "$options": "i"}
    if since_days:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=int(since_days))).isoformat()
        q["at"] = {"$gte": cutoff}
    rows = []
    async for doc in _db()[AUDIT_COLLECTION].find(q).sort("at", -1).limit(limit):
        doc["_id"] = str(doc.get("_id", ""))
        doc.setdefault("category", MODERATION)
        rows.append(doc)
    return rows


async def audit_summary() -> Dict[str, Any]:
    """What the audit log actually holds, so the console can explain an empty or
    quiet log instead of leaving the operator to guess it's broken."""
    db = _db()
    out: Dict[str, Any] = {"retention_days": _retention_days()}
    try:
        out["total"] = await db[AUDIT_COLLECTION].count_documents({})
        out["security"] = await db[AUDIT_COLLECTION].count_documents({"category": SECURITY})
        out["moderation"] = out["total"] - out["security"]
        newest = await db[AUDIT_COLLECTION].find_one({}, sort=[("at", -1)])
        out["newest_at"] = (newest or {}).get("at")
    except Exception:
        out.update({"total": 0, "security": 0, "moderation": 0, "newest_at": None})
    return out


# ── Activity feed (derived, not logged) ──────────────────────────────────────
# One reverse-chronological stream of what the deployment has actually been
# doing, assembled on read from the collections that already hold the data. It
# therefore covers everything that ever happened, including the long stretch
# before any event logging existed — which is the whole point of building it this
# way rather than starting a new log and waiting.

def _iso(value: Any) -> Optional[str]:
    """Normalise a stored timestamp to an ISO string. Collections are inconsistent
    here by history: most store ISO strings, journal_entries stores datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat() if value.tzinfo else \
            value.replace(tzinfo=timezone.utc).isoformat()
    return str(value)


def _clip(text: Any, n: int = 90) -> str:
    s = str(text or "").strip().replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")


# Each activity kind: the collection, the field that dates it, the user field, and
# how to summarise a row. Summaries are metadata only — a title, a label, a count.
# Never the body of a reading, a journal entry, or any birth data: this feed is
# visible to an admin *without* ADMIN_CONTENT_ACCESS.
_ACTIVITY_SOURCES = [
    {"kind": "signup", "collection": "users", "ts": "created_at", "user": "username",
     "summary": lambda d: f"{d.get('auth_provider') or 'password'} account registered"},
    {"kind": "ai", "collection": "ai_conversations", "ts": "updated_at", "user": "user_id",
     "summary": lambda d: f"{d.get('kind') or 'reading'} · {_clip(d.get('title'), 60)}"},
    {"kind": "digest", "collection": "digest_readings", "ts": "created_at", "user": "user_id",
     "summary": lambda d: f"{d.get('cadence') or 'daily'} digest for {_clip(d.get('subject'), 40)}"},
    {"kind": "journal", "collection": "journal_entries", "ts": "created_at", "user": "user_id",
     "summary": lambda d: "journal entry saved"},
    {"kind": "quiz", "collection": "quiz_sessions", "ts": "created_at", "user": "user_id",
     "summary": lambda d: "quiz · " + (_clip(", ".join(d.get("topics") or []), 40)
                                       or str(d.get("level") or "session"))},
    {"kind": "share", "collection": "shared_charts", "ts": "created_at", "user": "user_id",
     "summary": lambda d: "chart shared by link"},
    {"kind": "profile", "collection": "saved_profiles", "ts": "created_at", "user": "user_id",
     "summary": lambda d: "birth profile saved"},
]

ACTIVITY_KINDS = [s["kind"] for s in _ACTIVITY_SOURCES] + ["audit"]


async def activity_feed(limit: int = 200, kinds: Optional[List[str]] = None,
                        username: Optional[str] = None) -> List[Dict[str, Any]]:
    """The merged newest-first activity stream. Each source is queried for its own
    newest `limit` rows and the merge is trimmed back to `limit`, so one very busy
    source can't starve the others out of the window."""
    db = _db()
    wanted = set(kinds) if kinds else None
    rows: List[Dict[str, Any]] = []

    for src in _ACTIVITY_SOURCES:
        if wanted is not None and src["kind"] not in wanted:
            continue
        q = {src["user"]: username} if username else {}
        try:
            cursor = db[src["collection"]].find(q).sort(src["ts"], -1).limit(limit)
            async for doc in cursor:
                at = _iso(doc.get(src["ts"]))
                if not at:
                    # Undatable row — accounts predating `created_at`, mostly. Left
                    # out rather than given a made-up timestamp, so the signup count
                    # here can legitimately read lower than the Overview total.
                    continue
                rows.append({
                    "at": at,
                    "kind": src["kind"],
                    "user": doc.get(src["user"]),
                    "summary": src["summary"](doc),
                })
        except Exception as e:
            print(f"[admin.activity] {src['collection']} skipped: {e}")

    # The audit log joins the same stream — a suspension or a failed login belongs
    # in "what has been happening" as much as a saved reading does.
    if wanted is None or "audit" in wanted:
        try:
            q = {"admin": username} if username else {}
            async for doc in db[AUDIT_COLLECTION].find(q).sort("at", -1).limit(limit):
                rows.append({
                    "at": doc.get("at"),
                    "kind": "audit",
                    "user": doc.get("admin"),
                    "summary": (f"{doc.get('category') or MODERATION} · {doc.get('action')}"
                                + (f" → {doc['target']}" if doc.get("target") else "")),
                })
        except Exception as e:
            print(f"[admin.activity] audit skipped: {e}")

    rows.sort(key=lambda r: r["at"] or "", reverse=True)
    return rows[:limit]
