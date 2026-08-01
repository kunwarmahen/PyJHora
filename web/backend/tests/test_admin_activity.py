"""Audit log + activity feed + runtime config.

These three grew out of one report: the admin console's Audit tab had shown
nothing since the day §44 shipped, even though the deployment had gained users
and conversations since. The log wasn't broken — it only ever recorded moderation
actions, and none had been taken. The fix was to say so, to start recording
security events too, and to add a *derived* activity feed that answers the
question the operator was actually asking.

Kept DB-free like test_admin.py: everything here is either pure logic or driven
through a fake Mongo collection, so the suite stays hermetic.
"""
import admin as admin_service
import runtime_config
from config import settings


# ── Audit categories + filters (pure query construction) ─────────────────────

def test_security_actions_vocabulary_is_closed():
    # The console renders these as a filter dropdown; a call site inventing a new
    # action string would silently create an unfilterable category.
    assert "login" in admin_service.SECURITY_ACTIONS
    assert "login_failed" in admin_service.SECURITY_ACTIONS
    assert len(set(admin_service.SECURITY_ACTIONS)) == len(admin_service.SECURITY_ACTIONS)


def test_retention_days_falls_back_on_garbage(monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_AUDIT_RETENTION_DAYS", "not-a-number")
    assert admin_service._retention_days() == 90
    monkeypatch.setattr(settings, "ADMIN_AUDIT_RETENTION_DAYS", 7)
    assert admin_service._retention_days() == 7


def test_retention_days_never_zero(monkeypatch):
    # A 0-day horizon would delete every row on the next write.
    monkeypatch.setattr(settings, "ADMIN_AUDIT_RETENTION_DAYS", 0)
    assert admin_service._retention_days() >= 1


# ── Fake Mongo, just enough for the audit/activity reads ────────────────────

class FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, key, direction=-1):
        self._docs.sort(key=lambda d: str(d.get(key) or ""), reverse=direction < 0)
        return self

    def limit(self, n):
        self._docs = self._docs[:n]
        return self

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield dict(d)
        return gen()


class FakeCollection:
    def __init__(self, docs=()):
        self.docs = [dict(d) for d in docs]
        self.inserted = []

    def find(self, query=None, projection=None):
        return FakeCursor(self._match(query or {}))

    async def find_one(self, query=None, projection=None, sort=None):
        rows = self._match(query or {})
        if sort:
            key, direction = sort[0]
            rows.sort(key=lambda d: str(d.get(key) or ""), reverse=direction < 0)
        return dict(rows[0]) if rows else None

    async def count_documents(self, query=None):
        return len(self._match(query or {}))

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        self.inserted.append(dict(doc))
        return type("R", (), {"inserted_id": "x"})()

    async def delete_many(self, query):
        keep = [d for d in self.docs if d not in self._match(query)]
        removed = len(self.docs) - len(keep)
        self.docs = keep
        return type("R", (), {"deleted_count": removed})()

    async def update_one(self, query, update, upsert=False):
        return type("R", (), {"matched_count": 0, "modified_count": 0})()

    def _match(self, query):
        out = []
        for d in self.docs:
            if all(self._field_match(d, k, v) for k, v in query.items()):
                out.append(d)
        return out

    @staticmethod
    def _field_match(doc, key, want):
        if key == "$or":
            return any(FakeCollection._field_match(doc, k, v)
                       for clause in want for k, v in clause.items())
        got = doc.get(key)
        if isinstance(want, dict):
            if "$exists" in want:
                return (key in doc) is want["$exists"]
            if "$gte" in want:
                return got is not None and str(got) >= str(want["$gte"])
            if "$lt" in want:
                return got is not None and str(got) < str(want["$lt"])
            if "$regex" in want:
                import re
                return got is not None and re.search(
                    want["$regex"], str(got), re.I) is not None
            if "$ne" in want:
                return got != want["$ne"]
            if "$nin" in want:
                return got not in want["$nin"]
        return got == want


class FakeDB:
    def __init__(self, collections):
        self._c = collections

    def __getitem__(self, name):
        return self._c.setdefault(name, FakeCollection())


def _install_db(monkeypatch, collections):
    db = FakeDB(collections)
    monkeypatch.setattr(admin_service, "_db", lambda: db)
    return db


AUDIT_ROWS = [
    {"_id": 1, "at": "2026-07-18T10:00:00+00:00", "admin": "root",
     "action": "suspend", "target": "bob", "category": "moderation"},
    # A row written before categories existed — must still read as moderation.
    {"_id": 2, "at": "2026-07-18T11:00:00+00:00", "admin": "root",
     "action": "view_content", "target": "carol"},
    {"_id": 3, "at": "2026-08-01T09:00:00+00:00", "admin": "bob",
     "action": "login_failed", "target": None, "category": "security"},
]


def _run(coro):
    import asyncio
    return asyncio.run(coro)


def test_audit_moderation_filter_includes_uncategorised_rows(monkeypatch):
    _install_db(monkeypatch, {"admin_audit": FakeCollection(AUDIT_ROWS)})
    rows = _run(admin_service.list_audit(category=admin_service.MODERATION))
    actions = {r["action"] for r in rows}
    # The legacy row (no `category` field) is the whole point of this test.
    assert actions == {"suspend", "view_content"}
    assert all(r["category"] == "moderation" for r in rows)


def test_audit_security_filter(monkeypatch):
    _install_db(monkeypatch, {"admin_audit": FakeCollection(AUDIT_ROWS)})
    rows = _run(admin_service.list_audit(category=admin_service.SECURITY))
    assert [r["action"] for r in rows] == ["login_failed"]


def test_audit_actor_and_action_filters(monkeypatch):
    _install_db(monkeypatch, {"admin_audit": FakeCollection(AUDIT_ROWS)})
    assert len(_run(admin_service.list_audit(actor="bob"))) == 1
    assert len(_run(admin_service.list_audit(action="suspend"))) == 1
    assert len(_run(admin_service.list_audit(target="car"))) == 1  # substring, case-insensitive


def test_audit_summary_counts_both_categories(monkeypatch):
    _install_db(monkeypatch, {"admin_audit": FakeCollection(AUDIT_ROWS)})
    s = _run(admin_service.audit_summary())
    assert s["total"] == 3
    assert s["security"] == 1
    assert s["moderation"] == 2
    assert s["newest_at"] == "2026-08-01T09:00:00+00:00"


def test_security_event_is_written_with_its_category(monkeypatch):
    col = FakeCollection()
    _install_db(monkeypatch, {"admin_audit": col})
    monkeypatch.setattr(admin_service, "_last_prune_at", 9e18)  # skip the prune
    _run(admin_service.security_event("login", actor="bob", ip="1.2.3.4"))
    assert col.inserted[0]["category"] == admin_service.SECURITY
    assert col.inserted[0]["admin"] == "bob"
    assert col.inserted[0]["ip"] == "1.2.3.4"


def test_moderation_audit_keeps_its_category(monkeypatch):
    col = FakeCollection()
    _install_db(monkeypatch, {"admin_audit": col})
    monkeypatch.setattr(admin_service, "_last_prune_at", 9e18)
    _run(admin_service.audit("root", "suspend", target="bob"))
    assert col.inserted[0]["category"] == admin_service.MODERATION


def test_audit_write_survives_a_broken_collection(monkeypatch):
    # An audit write must never be able to fail the operation it records — a
    # login has to succeed even if the log is unwritable.
    class Broken(FakeCollection):
        async def insert_one(self, doc):
            raise RuntimeError("mongo is down")

    _install_db(monkeypatch, {"admin_audit": Broken()})
    _run(admin_service.security_event("login", actor="bob"))  # must not raise


# ── The derived activity feed ───────────────────────────────────────────────

def test_activity_feed_merges_sources_newest_first(monkeypatch):
    _install_db(monkeypatch, {
        "users": FakeCollection([
            {"username": "bob", "created_at": "2026-07-01T00:00:00+00:00",
             "auth_provider": "google"}]),
        "ai_conversations": FakeCollection([
            {"user_id": "bob", "updated_at": "2026-08-01T12:00:00+00:00",
             "kind": "chat", "title": "About my dasha"}]),
        "digest_readings": FakeCollection([
            {"user_id": "bob", "created_at": "2026-07-20T06:00:00+00:00",
             "cadence": "daily", "subject": "Bob"}]),
        "admin_audit": FakeCollection([]),
    })
    rows = _run(admin_service.activity_feed())
    assert [r["kind"] for r in rows] == ["ai", "digest", "signup"]
    assert rows[0]["summary"].startswith("chat · About my dasha")
    assert "google account registered" in rows[-1]["summary"]


def test_activity_feed_covers_data_written_before_any_logging(monkeypatch):
    # The reason the feed is derived rather than logged: it has to answer for the
    # users and conversations that already existed when this was built.
    _install_db(monkeypatch, {
        "users": FakeCollection([
            {"username": f"u{i}", "created_at": f"2026-06-{i:02d}T00:00:00+00:00"}
            for i in range(1, 7)]),
        "admin_audit": FakeCollection([]),
    })
    rows = _run(admin_service.activity_feed())
    assert len([r for r in rows if r["kind"] == "signup"]) == 6


def test_activity_feed_kind_filter(monkeypatch):
    _install_db(monkeypatch, {
        "users": FakeCollection([{"username": "bob", "created_at": "2026-07-01T00:00:00"}]),
        "ai_conversations": FakeCollection([
            {"user_id": "bob", "updated_at": "2026-08-01T00:00:00", "title": "x"}]),
    })
    rows = _run(admin_service.activity_feed(kinds=["signup"]))
    assert {r["kind"] for r in rows} == {"signup"}


def test_activity_feed_username_filter(monkeypatch):
    _install_db(monkeypatch, {
        "users": FakeCollection([
            {"username": "bob", "created_at": "2026-07-01T00:00:00"},
            {"username": "carol", "created_at": "2026-07-02T00:00:00"}]),
    })
    rows = _run(admin_service.activity_feed(kinds=["signup"], username="bob"))
    assert [r["user"] for r in rows] == ["bob"]


def test_activity_feed_survives_a_missing_collection(monkeypatch):
    class Broken(FakeCollection):
        def find(self, query=None, projection=None):
            raise RuntimeError("no such collection")

    _install_db(monkeypatch, {
        "users": FakeCollection([{"username": "bob", "created_at": "2026-07-01T00:00:00"}]),
        "quiz_sessions": Broken(),
    })
    rows = _run(admin_service.activity_feed())
    assert any(r["kind"] == "signup" for r in rows)


def test_activity_summaries_carry_no_user_content():
    # The feed is readable without ADMIN_CONTENT_ACCESS, so a summary must never
    # quote what someone wrote — only titles, kinds and counts.
    journal = next(s for s in admin_service._ACTIVITY_SOURCES if s["kind"] == "journal")
    summary = journal["summary"]({"text": "a private entry", "mood": "anxious"})
    assert "private" not in summary
    assert summary == "journal entry saved"


def test_activity_normalises_datetime_and_string_timestamps():
    from datetime import datetime, timezone
    as_dt = admin_service._iso(datetime(2026, 8, 1, tzinfo=timezone.utc))
    as_str = admin_service._iso("2026-08-01T00:00:00+00:00")
    assert as_dt.startswith("2026-08-01")
    assert as_str.startswith("2026-08-01")
    assert admin_service._iso(None) is None


# ── Runtime config ──────────────────────────────────────────────────────────

def test_runtime_defaults_come_from_env(monkeypatch):
    monkeypatch.setattr(settings, "DIGEST_SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "DIGEST_SCHEDULER_INTERVAL_MINUTES", 10)
    monkeypatch.setattr(settings, "DIGEST_AI_MAX_DEFERRALS", 3)
    d = runtime_config.defaults()
    assert d["digest_scheduler_enabled"] is True
    assert d["digest_scheduler_interval_minutes"] == 10
    # The delay knob is derived from the old count × interval, so an existing
    # deployment keeps exactly the patience it already had.
    assert d["digest_ai_max_delay_minutes"] == 30


def test_default_max_delay_matches_the_shipped_defaults(monkeypatch):
    monkeypatch.setattr(settings, "DIGEST_SCHEDULER_INTERVAL_MINUTES", 15)
    monkeypatch.setattr(settings, "DIGEST_AI_MAX_DEFERRALS", 6)
    assert runtime_config._default_max_delay_minutes() == 90


def test_interval_is_clamped_below_an_hour():
    coerce = runtime_config.FIELDS["digest_scheduler_interval_minutes"][1]
    # Above 59 the scheduler could skip a target hour entirely; 0 would spin.
    assert coerce(120) == 59
    assert coerce(0) == 1


def test_max_delay_is_clamped():
    coerce = runtime_config.FIELDS["digest_ai_max_delay_minutes"][1]
    assert coerce(-5) == 0
    assert coerce(99999) == 720


def test_max_deferrals_rounds_up_so_the_delay_is_honoured_in_full():
    # 50 minutes of patience at a 15-minute tick is 4 attempts, not 3 — rounding
    # down would quietly deliver less waiting than the operator configured.
    assert runtime_config.max_deferrals(
        {"digest_scheduler_interval_minutes": 15,
         "digest_ai_max_delay_minutes": 50}) == 4
    assert runtime_config.max_deferrals(
        {"digest_scheduler_interval_minutes": 15,
         "digest_ai_max_delay_minutes": 0}) == 0
    assert runtime_config.max_deferrals(
        {"digest_scheduler_interval_minutes": 15,
         "digest_ai_max_delay_minutes": 90}) == 6


def test_config_read_falls_back_to_defaults_when_db_is_down(monkeypatch):
    runtime_config.invalidate()

    def boom():
        raise RuntimeError("no database")

    monkeypatch.setattr(runtime_config, "get_database", boom)
    values = _run(runtime_config.get())
    assert values == runtime_config.defaults()
    runtime_config.invalidate()
