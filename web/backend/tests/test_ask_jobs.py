"""Detached Ask generations (ask_jobs): an answer survives its connection.

The failure these pin: a thinking model silent for >100 s behind Cloudflare, or
iOS killing a backgrounded tab, cut the SSE socket — and with it the generator,
so the answer was lost and the reader saw "network error".
"""
import asyncio
import json

import ask_jobs


def _frame(obj):
    return f"data: {json.dumps(obj)}\n\n"


def _events(chunks):
    """Parse followed SSE text into [(seq, event)], skipping heartbeat comments."""
    out = []
    for block in "".join(chunks).split("\n\n"):
        if not block or block.startswith(":"):
            continue
        lines = dict(line.split(": ", 1) for line in block.split("\n"))
        out.append((int(lines["id"]), json.loads(lines["data"])))
    return out


async def _gen(n, gate=None, delay=0.0):
    for i in range(n):
        if gate is not None and i == 1:
            await gate.wait()
        if delay:
            await asyncio.sleep(delay)
        yield _frame({"type": "token", "text": f"t{i}"})
    yield _frame({"type": "done"})


def test_generation_finishes_with_nobody_following():
    async def go():
        job = ask_jobs.start("alice", _gen(3))
        await job.task
        return job

    job = asyncio.run(go())
    assert job.done
    # job frame + 3 tokens + done
    assert len(job.frames) == 5


def test_reattach_replays_only_what_was_missed():
    async def go():
        gate = asyncio.Event()
        job = ask_jobs.start("alice", _gen(3, gate=gate))
        # First reader takes the job frame + first token, then "drops".
        first = []
        async for chunk in job.follow(0):
            first.append(chunk)
            if len(_events(first)) == 2:
                break
        gate.set()
        await job.task
        last_seq = _events(first)[-1][0]
        again = [c async for c in job.follow(last_seq)]
        return first, again

    first, again = asyncio.run(go())
    ev1 = _events(first)
    assert ev1[0][1] == {"type": "job", "job_id": ev1[0][1]["job_id"]}
    assert ev1[1][1]["text"] == "t0"
    ev2 = _events(again)
    assert [e["text"] for _, e in ev2 if e["type"] == "token"] == ["t1", "t2"]
    assert ev2[-1][1]["type"] == "done"
    # sequence numbers continue, no gap, no repeat
    assert [s for s, _ in ev1 + ev2] == list(range(1, 6))


def test_silence_is_filled_with_heartbeats(monkeypatch):
    monkeypatch.setattr(ask_jobs, "HEARTBEAT_S", 0.02)

    async def go():
        job = ask_jobs.start("alice", _gen(1, delay=0.1))
        return [c async for c in job.follow(0)]

    chunks = asyncio.run(go())
    assert any(c.startswith(": ping") for c in chunks)
    assert _events(chunks)[-1][1]["type"] == "done"


def test_cancel_stops_the_model_and_says_so():
    async def go():
        gate = asyncio.Event()  # never set: the generation hangs until cancelled
        job = ask_jobs.start("alice", _gen(3, gate=gate))
        await asyncio.sleep(0)
        assert not ask_jobs.cancel(job.id, "mallory")
        assert ask_jobs.cancel(job.id, "alice")
        try:
            await job.task
        except asyncio.CancelledError:
            pass
        return job

    job = asyncio.run(go())
    assert job.done
    assert json.loads(job.frames[-1][len("data: "):])["type"] == "cancelled"


def test_a_job_is_invisible_to_other_users():
    async def go():
        job = ask_jobs.start("alice", _gen(1))
        await job.task
        return job

    job = asyncio.run(go())
    assert ask_jobs.get(job.id, "alice") is job
    assert ask_jobs.get(job.id, "mallory") is None


def test_resume_and_cancel_routes_through_the_app(client):
    """The HTTP surface: re-attach replays from `after`, other users get 404,
    DELETE stops the model. One event loop, so the job task survives between
    requests (the shared client runs each request on its own loop)."""
    import httpx
    import main

    async def go():
        gate = asyncio.Event()
        job = ask_jobs.start("test-user", _gen(2, gate=gate))
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            gate.set()
            await job.task
            r = await ac.get(f"/api/astrology/ask/jobs/{job.id}", params={"after": 1})
            missing = await ac.get("/api/astrology/ask/jobs/nope")
            stranger = ask_jobs.start("someone-else", _gen(1))
            await stranger.task
            other = await ac.get(f"/api/astrology/ask/jobs/{stranger.id}")
            hang = asyncio.Event()
            live = ask_jobs.start("test-user", _gen(3, gate=hang))
            await asyncio.sleep(0)
            d = await ac.delete(f"/api/astrology/ask/jobs/{live.id}")
            try:
                await live.task
            except asyncio.CancelledError:
                pass
        return r, missing, other, d, live

    r, missing, other, d, live = asyncio.run(go())
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    ev = _events([r.text])
    assert ev[0][0] == 2 and [e["type"] for _, e in ev] == ["token", "token", "done"]
    assert missing.status_code == 404
    assert other.status_code == 404
    assert d.status_code == 200 and live.done
