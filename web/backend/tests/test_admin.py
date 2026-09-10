"""Admin console tests (§44).

Covers the security-critical, DB-free core: the ADMIN_USERNAMES allowlist
parsing + identity resolution, the content-access toggle, and the route gate
(a non-admin gets 404, not 403, so the console's existence isn't confirmed).

The data endpoints themselves (stats/users/…) touch Mongo and are exercised in
the deployment, not here — these tests deliberately keep to the paths that
short-circuit before any DB access so they stay hermetic like the other smoke
tests (no live Mongo).
"""
import admin as admin_service
from config import settings


# ── Allowlist parsing + identity ─────────────────────────────────────────────

def test_admin_identities_parsing(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", " Alice, bob@x.com ,, ")
    assert admin_service.admin_identities() == {"alice", "bob@x.com"}


def test_admin_identities_empty(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "")
    assert admin_service.admin_identities() == set()


def test_is_admin_by_username(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "alice")
    assert admin_service.is_admin_user("Alice") is True
    assert admin_service.is_admin_user("mallory") is False


def test_is_admin_by_email_in_doc(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "boss@x.com")
    # Username isn't listed, but the account's email is → admin.
    assert admin_service.is_admin_user("randomuser", {"email": "boss@x.com"}) is True
    assert admin_service.is_admin_user("randomuser", {"email": "other@x.com"}) is False


def test_is_admin_by_reconciled_flag(monkeypatch):
    # Even with an empty env list, a doc already carrying is_admin=True is honoured.
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "")
    assert admin_service.is_admin_user("u", {"is_admin": True}) is True
    assert admin_service.is_admin_user("u", {"is_admin": False}) is False


def test_content_access_toggle(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_CONTENT_ACCESS", False)
    assert admin_service.content_access_enabled() is False
    monkeypatch.setattr(settings, "ADMIN_CONTENT_ACCESS", True)
    assert admin_service.content_access_enabled() is True


def test_user_collections_cover_count_collections():
    # Every headline count collection must have a keying field, or cascade-delete
    # and the per-user counts would silently miss it.
    for name in admin_service.COUNT_COLLECTIONS:
        assert name in admin_service.USER_COLLECTIONS


# ── Route gate (no Mongo needed on these paths) ──────────────────────────────
# The shared `client` fixture overrides get_current_user → "test-user".

def test_me_reports_non_admin(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "")
    r = client.get("/api/admin/me")
    assert r.status_code == 200, r.text
    assert r.json()["is_admin"] is False


def test_me_reports_admin(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "test-user")
    r = client.get("/api/admin/me")
    assert r.status_code == 200, r.text
    assert r.json()["is_admin"] is True


def test_gate_hides_console_from_non_admin(client, monkeypatch):
    # A logged-in NON-admin probing a gated route must get 404, not 403 — the
    # console's existence isn't confirmed.
    monkeypatch.setattr(settings, "ADMIN_USERNAMES", "")
    r = client.get("/api/admin/stats")
    assert r.status_code == 404, r.text


# ── Every per-user collection is cascade-deleted ────────────────────────────

def test_every_per_user_collection_is_registered_for_deletion():
    """Cascade-delete is driven by `USER_COLLECTIONS`, so a module that stores
    rows about one person and is not listed there leaves that person's data
    behind after their account is deleted — silently, and only discoverable by
    reading every module.

    This walks the backend's own `COLLECTION` constants instead of trusting a
    hand-kept list, so a module added next year fails here rather than leaking.
    Anything genuinely not per-user goes in the allowlist below, with a reason.
    """
    import importlib
    import os
    import pkgutil

    # Collections that deliberately hold no per-user rows.
    NOT_PER_USER = {
        "app_config",            # one document: the deployment's runtime settings
        "admin_audit",           # security/moderation events, pruned on their own horizon
        "claim_check_stats",     # daily counters for the whole deployment, not per user
    }

    backend = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    unregistered = []
    for mod in pkgutil.iter_modules([backend]):
        if mod.ispkg or mod.name in ("main", "scripts_purge_empty"):
            continue
        try:
            m = importlib.import_module(mod.name)
        except Exception:
            continue  # optional deps / import-time side effects are not our business
        for attr in dir(m):
            if not attr.endswith("COLLECTION"):
                continue
            name = getattr(m, attr)
            if not isinstance(name, str) or not name:
                continue
            if name in NOT_PER_USER or name in admin_service.USER_COLLECTIONS:
                continue
            unregistered.append(f"{mod.name}.{attr} = {name!r}")
    assert not unregistered, (
        "per-user collections missing from admin.USER_COLLECTIONS (they would "
        "survive a cascade delete): " + ", ".join(sorted(unregistered)))
