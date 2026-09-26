"""The AI activity list (ai_activity): a question that is still being answered
must be visible somewhere other than the tab that asked it, and a finished one
must link to its saved result. Before this, leaving the page mid-answer made the
question look lost — it isn't saved until it's answered.
"""
import asyncio
import json

import httpx
from fastapi import FastAPI

import ai_activity
import ask_jobs
import detached_http
from auth import create_access_token


def _auth(user):
    return {"Authorization": f"Bearer {create_access_token({'sub': user})}",
            "X-Detach": "1", "X-AI-Page": "/chakras"}


def _frame(obj):
    return f"data: {json.dumps(obj)}\n\n"


class _FakeCollection:
    """Enough of a Mongo collection for conversations.save_reading."""

    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)

        class _R:
            inserted_id = f"reading{len(self.docs)}"
        return _R()


def _reading_app(monkeypatch, gate):
    """A toy AI endpoint that saves its reading through the REAL persistence
    function, the way the 44 handlers do (via deps._save_reading)."""
    import conversations

    coll = _FakeCollection()
    monkeypatch.setattr(conversations, "get_database", lambda: {conversations.COLLECTION: coll})

    async def _no_prune(_user):
        return None
    monkeypatch.setattr(conversations, "prune_history", _no_prune)

    app = FastAPI()

    @app.post("/api/astrology/kota-chakra-analysis")
    async def kota(payload: dict):
        await gate.wait()
        await conversations.save_reading(
            "alice", source="kota_chakra", title="Kota Chakra reading", text="the reading",
            profile_id=payload.get("profile_id"))
        return {"ai_analysis": "the reading"}

    return detached_http.DetachMiddleware(app)


def test_a_running_reading_is_listed_then_links_to_its_saved_result(monkeypatch):
    async def go():
        gate = asyncio.Event()
        app = _reading_app(monkeypatch, gate)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t") as ac:
            r = await ac.post("/api/astrology/kota-chakra-analysis",
                              json={"profile_id": "p1"}, headers=_auth("alice"))
            job_id = r.json()["detached_job"]
            await asyncio.sleep(0)
            running = ai_activity.list_for("alice")
            others = ai_activity.list_for("mallory")
            gate.set()
            await detached_http.get(job_id, "alice").task
            await asyncio.sleep(0)
            ready = ai_activity.list_for("alice")
            ai_activity.mark_seen(job_id, "alice")
            after_seen = ai_activity.list_for("alice")
        return job_id, running, others, ready, after_seen

    job_id, running, others, ready, after_seen = asyncio.run(go())
    mine = [a for a in running if a["id"] == job_id][0]
    assert mine["status"] == "running"
    assert mine["title"] == "Kota chakra reading"      # derived from the path
    assert mine["route"] == "/chakras"                  # from X-AI-Page
    assert mine["profile_id"] == "p1"
    assert not [a for a in others if a["id"] == job_id]
    done = [a for a in ready if a["id"] == job_id][0]
    assert done["status"] == "done" and done["seen"] is False
    assert done["result_id"] == "reading1"              # tied by the persistence hook
    assert done["title"] == "Kota Chakra reading"       # the saved reading's own title
    assert not [a for a in after_seen if a["id"] == job_id]


def test_a_failed_reading_says_why():
    app = FastAPI()

    @app.post("/api/astrology/broken-analysis")
    async def broken():
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Ollama: model not found")

    async def go():
        wrapped = detached_http.DetachMiddleware(app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=wrapped),
                                     base_url="http://t") as ac:
            r = await ac.post("/api/astrology/broken-analysis", json={}, headers=_auth("bob"))
            job_id = r.json()["detached_job"]
            await detached_http.get(job_id, "bob").task
        return [a for a in ai_activity.list_for("bob") if a["id"] == job_id][0]

    a = asyncio.run(go())
    assert a["status"] == "failed" and a["error"] == "Ollama: model not found"


def test_an_answer_watched_as_it_arrived_needs_no_ready_notice():
    seen_by_listener = []

    async def listener(a, watched):
        seen_by_listener.append((a.id, watched))

    ai_activity.on_finish(listener)
    try:
        async def gen(gate):
            await gate.wait()
            yield _frame({"type": "done", "conversation_id": "c1"})

        async def go():
            # Watched: a follower is streaming when the job ends.
            g1 = asyncio.Event()
            watched = ask_jobs.start("carol", gen(g1), activity={
                "title": "Which career suits me?", "route": "/ask-astrologer",
                "profile_id": "p1", "conversation_id": None})
            chunks = []

            async def read():
                async for c in watched.follow(0):
                    chunks.append(c)
            reader = asyncio.create_task(read())
            await asyncio.sleep(0.01)
            g1.set()
            await reader
            # Unwatched: nobody following (the tab was closed).
            g2 = asyncio.Event()
            lonely = ask_jobs.start("carol", gen(g2), activity={
                "title": "And marriage?", "route": "/ask-astrologer",
                "profile_id": "p1", "conversation_id": None})
            await asyncio.sleep(0)
            g2.set()
            await lonely.task
            await asyncio.sleep(0.01)  # listeners are fire-and-forget
            return watched.id, lonely.id, ai_activity.list_for("carol")

        wid, lid, listed = asyncio.run(go())
    finally:
        ai_activity._listeners.remove(listener)

    assert (wid, True) in seen_by_listener and (lid, False) in seen_by_listener
    ids = [a["id"] for a in listed]
    assert wid not in ids                 # watched → already seen
    assert lid in ids                     # waiting for the reader to come back
    assert [a for a in listed if a["id"] == lid][0]["kind"] == "ask"


def test_activity_route_counts_running_and_ready(client):
    import main

    async def go():
        ai_activity.begin("job-r", "test-user", kind="reading", title="Running one",
                          route="/kp", profile_id=None)
        ai_activity.begin("job-d", "test-user", kind="ask", title="Done one",
                          route="/ask-astrologer", profile_id=None)
        ai_activity.finish("job-d", "done")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as ac:
            listed = await ac.get("/api/ai/activity")
            seen = await ac.post("/api/ai/activity/job-d/seen")
            nope = await ac.post("/api/ai/activity/not-a-job/seen")
            after = await ac.get("/api/ai/activity")
        return listed.json(), seen.status_code, nope.status_code, after.json()

    listed, seen, nope, after = asyncio.run(go())
    assert listed["running"] >= 1 and listed["ready"] >= 1
    assert listed["items"][0]["status"] == "running"     # running first
    assert seen == 200 and nope == 404
    assert "job-d" not in [a["id"] for a in after["items"]]
