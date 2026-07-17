"""Consent state-machine tests for digest_recipients (double opt-in + opt-out).

No live Mongo: a tiny in-memory async collection stands in for motor, exercising
the exact operations the module uses (find_one by field query, insert_one that
assigns an _id, update_one by _id). Async coroutines are driven with
`asyncio.run` since the suite has no pytest-asyncio.
"""
import asyncio

import pytest

import digest_recipients as dr


class _FakeColl:
    def __init__(self):
        self.docs = []
        self._n = 0

    def _match(self, doc, query):
        return all(doc.get(k) == v for k, v in query.items())

    async def find_one(self, query):
        return next((d for d in self.docs if self._match(d, query)), None)

    async def insert_one(self, doc):
        self._n += 1
        doc.setdefault("_id", f"id{self._n}")  # mimic pymongo mutating in the _id
        self.docs.append(doc)
        return type("R", (), {"inserted_id": doc["_id"]})

    async def update_one(self, query, update):
        d = await self.find_one(query)
        if d:
            d.update(update.get("$set", {}))
        return None


class _FakeDB:
    def __init__(self):
        self.colls = {}

    def __getitem__(self, name):
        return self.colls.setdefault(name, _FakeColl())


@pytest.fixture(autouse=True)
def fake_db(monkeypatch):
    db = _FakeDB()
    monkeypatch.setattr(dr, "get_database", lambda: db)
    return db


def run(coro):
    return asyncio.run(coro)


def test_ensure_creates_pending_then_is_idempotent():
    rec, created = run(dr.ensure("owner", "Person@Example.com "))
    assert created is True
    assert rec["status"] == dr.PENDING
    assert rec["email"] == "person@example.com"  # normalized
    assert rec["token"]

    # Re-saving the profile must not re-invite or change state.
    rec2, created2 = run(dr.ensure("owner", "person@example.com"))
    assert created2 is False
    assert rec2["status"] == dr.PENDING


def test_confirm_then_status():
    rec, _ = run(dr.ensure("owner", "a@b.com"))
    email = run(dr.confirm(rec["token"]))
    assert email == "a@b.com"
    assert run(dr.get("owner", "a@b.com"))["status"] == dr.CONFIRMED


def test_unsubscribe_wins_over_stale_confirm():
    rec, _ = run(dr.ensure("owner", "a@b.com"))
    run(dr.confirm(rec["token"]))
    assert run(dr.unsubscribe(rec["token"])) == "a@b.com"
    assert run(dr.get("owner", "a@b.com"))["status"] == dr.UNSUBSCRIBED
    # A stale confirm link must not resurrect an opt-out.
    run(dr.confirm(rec["token"]))
    assert run(dr.get("owner", "a@b.com"))["status"] == dr.UNSUBSCRIBED


def test_bad_token_is_harmless():
    assert run(dr.confirm("nope")) is None
    assert run(dr.unsubscribe("nope")) is None


def test_status_for_unknown_pair_is_none():
    assert run(dr.get("owner", "never@invited.com")) is None
