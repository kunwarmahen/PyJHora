"""Every answer the reader was shown must survive a refresh — no database.

The bug: an Ask AI thread would list under its question and open as "This
conversation is empty", even though the answer had streamed in perfectly.

`_save_turn` created the thread, then wrote the full tool trace, then appended
the messages. The engine keys several maps by house *number* — `get_transits`
returns `arudhas.significations.AL` keyed by int — and BSON documents may only
have string keys, so pymongo raised InvalidDocument on the trace write. The SSE
route's `except Exception: print(...)` swallowed it, leaving behind exactly what
the user saw: a conversation with a title and no messages in it.

These tests pin the ordering (the answer is written first, and on its own), the
coercion (engine-shaped data is storable at all), and the rule that a blank
answer is never persisted.
"""
import asyncio
from types import SimpleNamespace

import bson
import pytest

import conversations as convo
import deps
import tool_traces
from database import bson_safe
from llm.base import ModelConfig, ProviderType


# --------------------------------------------------------------------------- #
# Coercion
# --------------------------------------------------------------------------- #
def test_house_numbered_keys_are_rejected_by_mongo_as_they_come():
    """The premise of the whole fix — without this the rest is theatre."""
    engine_shaped = {"arudhas": {"significations": {"AL": {1: "self", 2: "wealth"}}}}
    with pytest.raises(Exception):
        bson.encode(engine_shaped)


def test_bson_safe_makes_engine_output_storable():
    safe = bson_safe({"arudhas": {"significations": {"AL": {1: "self"}}},
                      "pair": (3, 4), "when": None, "ok": True})
    bson.encode(safe)  # must not raise
    assert safe["arudhas"]["significations"]["AL"] == {"1": "self"}
    assert safe["pair"] == [3, 4]
    # Booleans stay booleans rather than becoming "True".
    assert safe["ok"] is True and safe["when"] is None


def test_bson_safe_stringifies_what_bson_cannot_encode():
    class Degrees:
        def __repr__(self):  # pragma: no cover - exercised via str()
            return "27N50"

    assert bson_safe({"lat": Degrees()})["lat"] == "27N50"


# --------------------------------------------------------------------------- #
# Ordering: the answer first, the trace after
# --------------------------------------------------------------------------- #
class _Recorder:
    """Stands in for the conversations/tool_traces modules."""

    def __init__(self):
        self.calls = []

    def _record(self, name):
        async def _fn(*a, **kw):
            self.calls.append((name, a, kw))
            return "conv1" if name == "create_conversation" else None
        return _fn


def _request(**kw):
    base = dict(conversation_id=None, profile_id="p1", question="Will I travel?",
                birth_details=SimpleNamespace(model_dump=lambda: {"dob": "1976-06-04"}),
                source="astrologer", regenerate=False)
    base.update(kw)
    return SimpleNamespace(**base)


def _cfg():
    return ModelConfig(ProviderType.OLLAMA, "gemma4:26b", "http://localhost:11434", None)


def _save(monkeypatch, *, answer="Jupiter favours it.", trace=None, request=None,
          trace_raises=False):
    rec = _Recorder()
    for fn in ("create_conversation", "append_messages", "replace_last_assistant"):
        monkeypatch.setattr(convo, fn, rec._record(fn))

    async def _save_trace(*a, **kw):
        rec.calls.append(("save_trace", a, kw))
        if trace_raises:
            raise bson.errors.InvalidDocument("documents must have only string keys")

    monkeypatch.setattr(tool_traces, "save_trace", _save_trace)
    conv_id = asyncio.run(deps._save_turn(
        "u1", request or _request(), _cfg(), {}, answer,
        elapsed_ms=12, mode="tools", tool_trace=trace))
    return rec, conv_id


def test_a_new_thread_is_created_with_its_messages_already_in_it(monkeypatch):
    """One insert, not create-then-append: nothing can interrupt between the two
    halves if there is only one half."""
    rec, conv_id = _save(monkeypatch)

    assert conv_id == "conv1"
    assert [c[0] for c in rec.calls] == ["create_conversation"]
    msgs = rec.calls[0][2]["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "Will I travel?"
    assert msgs[1]["content"] == "Jupiter favours it."


def test_the_trace_is_written_after_the_answer_never_before(monkeypatch):
    trace = [{"name": "get_transits", "args": {}, "ok": True,
              "result": {"significations": {1: "self"}}}]
    rec, _ = _save(monkeypatch, trace=trace)

    assert [c[0] for c in rec.calls] == ["create_conversation", "save_trace"]


def test_an_unstorable_trace_no_longer_costs_the_reader_the_answer(monkeypatch):
    """The reported failure, reproduced end to end: the trace write blows up and
    the conversation still comes back with both messages in it."""
    trace = [{"name": "get_transits", "args": {}, "ok": True,
              "result": {"significations": {1: "self"}}}]
    rec, conv_id = _save(monkeypatch, trace=trace, trace_raises=True)

    assert conv_id == "conv1"
    created = rec.calls[0]
    assert created[0] == "create_conversation"
    assert len(created[2]["messages"]) == 2


def test_a_follow_up_turn_appends_to_the_existing_thread(monkeypatch):
    rec, conv_id = _save(monkeypatch, request=_request(conversation_id="c9"))
    assert conv_id == "c9"
    assert [c[0] for c in rec.calls] == ["append_messages"]


def test_regenerate_replaces_the_answer_rather_than_adding_a_turn(monkeypatch):
    rec, _ = _save(monkeypatch, request=_request(conversation_id="c9", regenerate=True))
    assert [c[0] for c in rec.calls] == ["replace_last_assistant"]


@pytest.mark.parametrize("answer", ["", "   ", None])
def test_a_blank_answer_is_never_written(monkeypatch, answer):
    """An item whose question is there and whose answer is empty is worse than no
    item at all — and on a regenerate, blank would overwrite a good answer."""
    rec, conv_id = _save(monkeypatch, answer=answer,
                         request=_request(conversation_id="c9", regenerate=True))
    assert rec.calls == []
    assert conv_id == "c9"


# --------------------------------------------------------------------------- #
# The trace store itself
# --------------------------------------------------------------------------- #
class _FakeCollection:
    def __init__(self):
        self.written = None

    async def update_one(self, flt, update, upsert=False):
        self.written = update["$set"]


def _fake_db(monkeypatch):
    col = _FakeCollection()
    monkeypatch.setattr(tool_traces, "get_database", lambda: {tool_traces.COLLECTION: col})
    return col


def test_a_saved_trace_is_coerced_into_something_mongo_accepts(monkeypatch):
    col = _fake_db(monkeypatch)
    asyncio.run(tool_traces.save_trace(
        "u1", "c1", "t1",
        [{"name": "get_transits", "result": {"significations": {1: "self"}}}]))

    bson.encode({"doc": col.written})  # must not raise
    assert col.written["results"][0]["result"]["significations"] == {"1": "self"}


def test_an_oversized_trace_is_dropped_not_raised(monkeypatch):
    """Mongo's 16MB ceiling is not worth failing an answer over."""
    col = _fake_db(monkeypatch)
    huge = [{"name": "get_ephemeris", "result": {"rows": ["x" * 1000] * 9000}}]
    asyncio.run(tool_traces.save_trace("u1", "c1", "t1", huge))

    assert "too large" in col.written["results"][0]["result"]["note"]
    assert col.written["results"][0]["name"] == "get_ephemeris"
