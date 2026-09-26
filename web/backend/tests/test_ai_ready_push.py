""""Your answer is ready" push (ai_ready_push): sent only for an answer that
finished with nobody watching and stayed unseen, only to someone who turned
push on, and it opens the saved answer under the right profile."""
import asyncio

import pytest

import ai_activity
import ai_ready_push
import notifications


@pytest.fixture
def sent(monkeypatch):
    box = {"prefs": {"push": True, "ai_ready": True}, "sent": []}

    async def get_prefs(_user):
        return {**notifications.DEFAULT_PREFS, **box["prefs"]}

    async def send_push(user, payload):
        box["sent"].append((user, payload))
        return 1

    monkeypatch.setattr(notifications, "get_prefs", get_prefs)
    monkeypatch.setattr(notifications, "send_push", send_push)
    monkeypatch.setattr(ai_ready_push, "GRACE_S", 0.01)
    return box


def _activity(status="done", kind="reading", **kw):
    a = ai_activity.Activity("j1", "alice", kind=kind, title=kw.get("title", "Kota Chakra"),
                             route=kw.get("route", "/chakras"), profile_id=kw.get("pid", "p1"))
    a.status = status
    a.result_id = kw.get("result_id", "r1")
    return a


def _run(a, watched=False, mark_seen_during_grace=False):
    async def go():
        task = asyncio.create_task(ai_ready_push.notify_when_ready(a, watched))
        if mark_seen_during_grace:
            await asyncio.sleep(0)
            a.seen = True
        await task
    asyncio.run(go())


def test_unwatched_answer_is_pushed_with_a_link_to_it(sent):
    _run(_activity())
    assert sent["sent"] == [("alice", {
        "title": "Your reading is ready", "body": "Kota Chakra",
        "url": "/chakras?reading=r1&profile=p1"})]


def test_an_ask_answer_says_answer(sent):
    _run(_activity(kind="ask", title="Which career suits me?", route="/ask-astrologer"))
    assert sent["sent"][0][1]["title"] == "Your answer is ready"


@pytest.mark.parametrize("case", ["watched", "seen_during_grace", "push_off",
                                  "ai_ready_off", "cancelled"])
def test_no_push_when_it_would_be_noise_or_unwanted(sent, case):
    a = _activity(status="cancelled" if case == "cancelled" else "done")
    if case == "push_off":
        sent["prefs"]["push"] = False
    if case == "ai_ready_off":
        sent["prefs"]["ai_ready"] = False
    _run(a, watched=case == "watched", mark_seen_during_grace=case == "seen_during_grace")
    assert sent["sent"] == []


def test_a_failure_is_reported_too(sent):
    _run(_activity(status="failed"))
    assert sent["sent"][0][1]["title"] == "An answer didn't finish"
    assert sent["sent"][0][1]["url"] == "/chakras?profile=p1"


def test_long_titles_are_trimmed():
    payload = ai_ready_push.build_payload(_activity(title="x" * 300))
    assert len(payload["body"]) <= 120


def test_the_listener_is_registered():
    assert ai_ready_push.notify_when_ready in ai_activity._listeners


def test_ai_ready_pref_defaults_on():
    assert notifications.DEFAULT_PREFS["ai_ready"] is True
