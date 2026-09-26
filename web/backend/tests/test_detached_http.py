"""Detached AI requests (detached_http): a slow AI endpoint answers 202 + job id
at once, runs to completion with nobody connected, and the poll returns the
handler's own response verbatim. Pins the fix for Cloudflare's ~100 s cut (524)
and iOS killing the tab on the ~45 JSON "AI reading" endpoints."""
import asyncio
import json

import httpx
from fastapi import FastAPI, HTTPException

import detached_http
from auth import create_access_token


def _toy_app(gate: asyncio.Event, calls: list):
    app = FastAPI()

    @app.post("/api/astrology/slow-analysis")
    async def slow(payload: dict):
        calls.append(payload)
        await gate.wait()
        return {"ai_analysis": f"reading for {payload['name']}"}

    @app.post("/api/astrology/broken-analysis")
    async def broken():
        raise HTTPException(status_code=429, detail="Rate limit reached")

    @app.post("/api/astrology/birth-chart")
    async def compute():
        return {"compute": True}

    return detached_http.DetachMiddleware(app)


def _auth(user="alice"):
    return {"Authorization": f"Bearer {create_access_token({'sub': user})}", "X-Detach": "1"}


def test_slow_ai_call_detaches_and_finishes_without_a_listener():
    async def go():
        gate, calls = asyncio.Event(), []
        app = _toy_app(gate, calls)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t") as ac:
            r = await ac.post("/api/astrology/slow-analysis", json={"name": "Mahen"},
                              headers=_auth())
            job_id = r.json()["detached_job"]
            job = detached_http.get(job_id, "alice")
            running = await detached_http.wait(job, timeout=0.05)
            gate.set()
            finished = await detached_http.wait(job, timeout=1)
        return r, job, running, finished, calls

    r, job, running, finished, calls = asyncio.run(go())
    assert r.status_code == 202
    assert calls == [{"name": "Mahen"}]           # body replayed intact
    assert running is False and finished is True
    assert job.status == 200
    assert json.loads(bytes(job.body)) == {"ai_analysis": "reading for Mahen"}
    assert detached_http.get(job.id, "mallory") is None


def test_errors_come_back_as_the_handlers_own_status():
    async def go():
        app = _toy_app(asyncio.Event(), [])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t") as ac:
            r = await ac.post("/api/astrology/broken-analysis", json={}, headers=_auth())
            job = detached_http.get(r.json()["detached_job"], "alice")
            await detached_http.wait(job, timeout=1)
        return job

    job = asyncio.run(go())
    assert job.status == 429
    assert json.loads(bytes(job.body))["detail"] == "Rate limit reached"


def test_passes_through_without_header_bad_token_or_non_ai_path():
    async def go():
        gate = asyncio.Event()
        gate.set()
        app = _toy_app(gate, [])
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://t") as ac:
            plain = await ac.post("/api/astrology/slow-analysis", json={"name": "x"})
            bad = await ac.post("/api/astrology/slow-analysis", json={"name": "x"},
                                headers={"Authorization": "Bearer nope", "X-Detach": "1"})
            compute = await ac.post("/api/astrology/birth-chart", json={}, headers=_auth())
        return plain, bad, compute

    plain, bad, compute = asyncio.run(go())
    assert plain.status_code == 200 and "ai_analysis" in plain.json()
    # an expired/invalid token must reach the handler so the 401→refresh flow works
    assert bad.status_code == 200
    assert compute.json() == {"compute": True}


def test_every_route_that_calls_the_model_is_detachable():
    """The allow-list must keep up with new AI endpoints: any POST handler whose
    source calls the model (llm_service.<method>(…)) has to be detachable, or a
    slow reading on it dies at Cloudflare's ~100 s again."""
    import inspect
    import re

    import main

    # Endpoints that already survive a dropped connection their own way.
    OWN_JOB_SYSTEM = {"/api/astrology/ask/stream",        # ask_jobs.py
                      "/api/astrology/life-report/start"}  # life_report.py jobs
    calls_model = re.compile(r"llm_service\.(?!LIFE_REPORT_CHAPTERS|_render_context_block)\w+\(")
    ai_paths = []
    for r in main.app.routes:
        if "POST" not in (getattr(r, "methods", None) or ()) or r.path in OWN_JOB_SYSTEM:
            continue
        try:
            src = inspect.getsource(r.endpoint)
        except (OSError, TypeError):
            continue
        if calls_model.search(src):
            ai_paths.append(r.path)
    assert len(ai_paths) >= 40
    assert [p for p in ai_paths if not detached_http.DETACHABLE.match(p)] == []

    # …and the browser must ask for detaching on the same paths
    # (frontend/src/services/api.js DETACHABLE_AI).
    import os
    api_js = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src",
                          "services", "api.js")
    with open(api_js) as f:
        m = re.search(r"const DETACHABLE_AI =\s*/(.+)/;", f.read())
    assert m, "DETACHABLE_AI not found in api.js"
    js = re.compile(m.group(1).replace("\\/", "/"))
    assert [p for p in ai_paths if not js.match(p)] == []


def test_poll_route_returns_running_then_the_result(client, monkeypatch):
    import main

    monkeypatch.setattr(detached_http, "POLL_WAIT_S", 0.05)

    async def go():
        job = detached_http.HttpJob("test-user", "/api/astrology/x-analysis")
        detached_http._jobs[job.id] = job
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
                                     base_url="http://test") as ac:
            running = await ac.get(f"/api/ai/jobs/{job.id}")
            job.status = 200
            job.headers = [(b"content-type", b"application/json")]
            job.body = bytearray(b'{"ai_analysis": "done"}')
            job.finished.set()
            done = await ac.get(f"/api/ai/jobs/{job.id}")
            missing = await ac.get("/api/ai/jobs/nope")
        return running, done, missing

    running, done, missing = asyncio.run(go())
    assert running.status_code == 202 and running.json() == {"status": "running"}
    assert done.status_code == 200 and done.json() == {"ai_analysis": "done"}
    assert missing.status_code == 404
