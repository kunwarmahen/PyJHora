"""Detached AI requests — a JSON AI endpoint that outlives the request asking for it.

The ~45 "AI reading" endpoints (`*-analysis`, predict, quiz, rectification…) are
plain request→JSON calls. Behind the NAS's Cloudflare Tunnel a response that
takes longer than ~100 s never arrives (Cloudflare answers 524 and hangs up) and
a local thinking model routinely takes longer than that; on a phone, iOS killing
the tab kills the request too. Ask got its own streaming answer to this
(ask_jobs.py); this module is the same idea for everything else, done once at
the HTTP layer so no handler changes:

* A request carrying ``X-Detach: 1`` to an allow-listed AI path is run to
  completion in a background task against the app itself (the body replayed,
  the response captured), and answered at once with
  ``202 {"detached_job": <id>}``.
* ``GET /api/ai/jobs/{id}`` long-polls it: waits up to ``POLL_WAIT_S`` (well
  under the proxy's idle limit) and answers ``202 {"status": "running"}``, or —
  once done — the handler's own status, content type and body, verbatim. The
  client then sees exactly what the original request would have returned.
* ``DELETE /api/ai/jobs/{id}`` cancels it.

Auth: a request is detached only when its bearer token already decodes; anything
else passes through untouched so the usual 401 → refresh → retry flow still
works. The job belongs to that token's user; nobody else can see it.

In-process on purpose (one uvicorn worker), like ask_jobs.
"""
from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
from typing import Dict, List, Optional, Tuple

import ai_activity
from auth import decode_token

DETACH_HEADER = b"x-detach"
# The page the reader was on, so a finished job can link back to it.
PAGE_HEADER = b"x-ai-page"
POLL_WAIT_S = 25.0
KEEP_FINISHED_S = 2 * 60 * 60
MAX_AGE_S = 6 * 60 * 60

# Only endpoints that call the model. The life report has its own job system
# (life-report/start + /job), and Ask streams through ask_jobs.
DETACHABLE = re.compile(
    r"^/api/astrology/("
    r"[a-z0-9-]+-analysis"
    r"|predict|ask"
    r"|quiz/generate|quiz/grade"
    r"|rectify-birth-time/(chat|explain|events/explain)"
    r"|life-report/chapter"
    r")$"
)


class HttpJob:
    def __init__(self, owner: str, path: str):
        self.id = secrets.token_urlsafe(12)
        self.owner = owner
        self.path = path
        self.created = time.monotonic()
        self.finished_at: Optional[float] = None
        self.status: int = 0
        self.headers: List[Tuple[bytes, bytes]] = []
        self.body = bytearray()
        self.task: Optional[asyncio.Task] = None
        self.finished = asyncio.Event()

    @property
    def done(self) -> bool:
        return self.finished.is_set()

    def content_type(self) -> str:
        for k, v in self.headers:
            if k.lower() == b"content-type":
                return v.decode("latin-1")
        return "application/json"


_jobs: Dict[str, HttpJob] = {}


def _sweep() -> None:
    now = time.monotonic()
    for jid, job in list(_jobs.items()):
        if (job.finished_at is not None and now - job.finished_at > KEEP_FINISHED_S) \
                or now - job.created > MAX_AGE_S:
            if job.task and not job.task.done():
                job.task.cancel()
            _jobs.pop(jid, None)


def get(job_id: str, owner: str) -> Optional[HttpJob]:
    _sweep()
    job = _jobs.get(job_id)
    return job if job and job.owner == owner else None


def cancel(job_id: str, owner: str) -> bool:
    job = get(job_id, owner)
    if not job:
        return False
    if job.task and not job.task.done():
        job.task.cancel()
    return True


async def wait(job: HttpJob, timeout: float = None) -> bool:
    """True once the job is done; False if still running after `timeout`."""
    try:
        await asyncio.wait_for(job.finished.wait(), timeout=POLL_WAIT_S if timeout is None else timeout)
        return True
    except asyncio.TimeoutError:
        return False


def _bearer_user(scope) -> Optional[str]:
    for k, v in scope.get("headers", []):
        if k == b"authorization":
            val = v.decode("latin-1")
            if val.lower().startswith("bearer "):
                return decode_token(val[7:].strip())
    return None


def _wants_detach(scope) -> bool:
    return any(k == DETACH_HEADER and v.strip() in (b"1", b"true")
               for k, v in scope.get("headers", []))


_NAMED = {"predict": "Prediction", "ask": "Question", "quiz/generate": "Learn quiz",
          "quiz/grade": "Quiz grading", "life-report/chapter": "Life report chapter"}


def _activity_fields(scope, body: bytes) -> dict:
    """What the activity list shows for this request until the saved reading
    supplies its own title (conversations.save_reading → note_result)."""
    try:
        data = json.loads(body or b"{}")
    except ValueError:
        data = {}
    data = data if isinstance(data, dict) else {}
    tail = scope["path"].split("/api/astrology/", 1)[-1]
    if data.get("question"):
        title = str(data["question"]).strip()[:160]
    elif tail in _NAMED:
        title = _NAMED[tail]
    elif tail.startswith("rectify-birth-time"):
        title = "Birth-time rectification"
    else:
        title = tail.removesuffix("-analysis").replace("-", " ").capitalize() + " reading"
    page = next((v.decode("latin-1") for k, v in scope.get("headers", []) if k == PAGE_HEADER), "")
    # A same-site path only — this becomes a link in the reader's own UI.
    route = page if page.startswith("/") and not page.startswith("//") and len(page) < 200 else None
    pid = data.get("profile_id")
    return {"title": title, "route": route,
            "profile_id": pid if isinstance(pid, str) else None}


async def _json(send, status: int, payload: bytes) -> None:
    await send({"type": "http.response.start", "status": status,
                "headers": [(b"content-type", b"application/json"),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": payload})


class DetachMiddleware:
    """Pure ASGI, so the captured response is byte-for-byte what the handler sent."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] != "http" or scope.get("method") != "POST"
                or not DETACHABLE.match(scope.get("path", "")) or not _wants_detach(scope)):
            return await self.app(scope, receive, send)
        owner = _bearer_user(scope)
        if not owner:
            return await self.app(scope, receive, send)

        # Read the whole body now — the client may be gone before the handler runs.
        chunks = []
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            chunks.append(msg.get("body", b""))
            if not msg.get("more_body"):
                break
        body = b"".join(chunks)

        _sweep()
        job = HttpJob(owner, scope["path"])
        _jobs[job.id] = job
        # Handlers never see X-Detach — it is a transport detail of this layer.
        inner_scope = dict(scope)
        inner_scope["headers"] = [(k, v) for k, v in scope["headers"] if k != DETACH_HEADER]
        never = asyncio.Event()
        sent_body = False

        async def replay():
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            await never.wait()  # nobody ever disconnects from a detached run
            return {"type": "http.disconnect"}

        async def capture(message):
            if message["type"] == "http.response.start":
                job.status = message["status"]
                job.headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                job.body.extend(message.get("body", b""))

        fields = _activity_fields(scope, body)

        async def run():
            # Inside the job's task: the activity becomes this context's current
            # one, so the reading the handler saves is tied back to it.
            ai_activity.begin(job.id, owner, kind="reading", **fields)
            outcome = "done"
            try:
                await self.app(inner_scope, replay, capture)
            except asyncio.CancelledError:
                outcome = "cancelled"
                job.status, job.headers = 499, [(b"content-type", b"application/json")]
                job.body = bytearray(b'{"detail": "Cancelled"}')
                raise
            except Exception as e:  # FastAPI normally turns these into 500s itself
                job.status, job.headers = 500, [(b"content-type", b"application/json")]
                job.body = bytearray(json.dumps({"detail": str(e)}).encode())
            finally:
                job.finished_at = time.monotonic()
                job.finished.set()
                error = None
                if outcome == "done" and not 200 <= job.status < 300:
                    outcome = "failed"
                    try:
                        error = str(json.loads(bytes(job.body)).get("detail"))
                    except Exception:
                        error = f"HTTP {job.status}"
                ai_activity.finish(job.id, outcome, error)

        job.task = asyncio.create_task(run())
        await _json(send, 202, json.dumps({"detached_job": job.id}).encode())
