"""What the AI is working on for you — one list across Ask and every reading.

Answers run as server-side jobs (ask_jobs.py for Ask/transit chat, and
detached_http.py for the ~44 JSON reading endpoints), but only the browser tab
that asked knew about one — through its own localStorage. Leave the page,
switch device, or open History, and the question seemed to have vanished: it
isn't saved until it is answered. This module is the shared, server-side
record of each job, so the header's activity pill, History's "In progress"
section and the Ask page can all show it, and a finished one links straight to
its saved result.

* ``begin`` is called by the job modules inside the job's own task, which also
  sets a context variable — so ``note_result``, called from the persistence
  layer (conversations.py) when the answer is saved, knows which job it
  belongs to without any of the 44 handlers passing an id around.
* ``watch`` counts live readers (an SSE follower, a long-poll in flight). A
  result a reader was watching arrive is marked seen at once — nobody needs to
  be told about an answer they just watched appear.
* ``on_finish`` listeners run when a job ends (the push notification hooks in
  here), with ``watched`` telling them whether anyone was looking.

In-process, like the job registries it mirrors (one uvicorn worker).
"""
from __future__ import annotations

import asyncio
import contextvars
import time
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional

KEEP_FINISHED_S = 2 * 60 * 60   # same as the job registries

_current: contextvars.ContextVar[Optional["Activity"]] = contextvars.ContextVar(
    "ai_activity_current", default=None)


class Activity:
    def __init__(self, job_id: str, owner: str, *, kind: str, title: str,
                 route: Optional[str], profile_id: Optional[str],
                 conversation_id: Optional[str] = None):
        self.id = job_id
        self.owner = owner
        self.kind = kind                    # "ask" | "reading"
        self.title = title
        self.route = route
        self.profile_id = profile_id
        self.conversation_id = conversation_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.status = "running"             # running | done | failed | cancelled
        self.result_id: Optional[str] = None
        self.error: Optional[str] = None
        self.seen = False
        self.watchers = 0
        self.finished_mono: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "title": self.title,
                "route": self.route, "profile_id": self.profile_id,
                "conversation_id": self.conversation_id,
                "started_at": self.started_at, "status": self.status,
                "result_id": self.result_id, "error": self.error, "seen": self.seen}


_records: Dict[str, Activity] = {}
_listeners: List[Callable[[Activity, bool], Awaitable[None]]] = []


def on_finish(fn: Callable[[Activity, bool], Awaitable[None]]):
    """Register `async fn(activity, watched)` to run when any job ends."""
    _listeners.append(fn)
    return fn


def _sweep() -> None:
    now = time.monotonic()
    for k, a in list(_records.items()):
        if a.finished_mono is not None and now - a.finished_mono > KEEP_FINISHED_S:
            _records.pop(k, None)


def begin(job_id: str, owner: str, **fields) -> Activity:
    """Record a job and make it the current one for this task's context."""
    _sweep()
    a = Activity(job_id, owner, **fields)
    _records[job_id] = a
    _current.set(a)
    return a


def note_result(result_id: Optional[str], *, title: Optional[str] = None,
                route: Optional[str] = None) -> None:
    """Called where answers are persisted: tie the saved item to the running job
    (if the save happens inside one). A saved reading's own title and page are
    better than what the request could guess, so they win."""
    a = _current.get()
    if a is None or not result_id:
        return
    a.result_id = str(result_id)
    if title:
        a.title = title
    if route:
        a.route = route


def finish(job_id: str, status: str, error: Optional[str] = None) -> None:
    a = _records.get(job_id)
    if a is None or a.status != "running":
        return
    a.status = status
    a.error = error
    a.finished_mono = time.monotonic()
    watched = a.watchers > 0
    if watched:
        a.seen = True
    for fn in list(_listeners):
        # Fire and forget: a listener (push) must never hold up or break a job.
        asyncio.ensure_future(_safe(fn, a, watched))


async def _safe(fn, a: Activity, watched: bool) -> None:
    try:
        await fn(a, watched)
    except Exception as e:  # pragma: no cover - defensive
        print(f"ai_activity listener failed: {e}")


class watch:
    """`with ai_activity.watch(job_id): …` around anything that is showing the
    job to a reader right now."""

    def __init__(self, job_id: str):
        self.a = _records.get(job_id)

    def __enter__(self):
        if self.a:
            self.a.watchers += 1
        return self

    def __exit__(self, *exc):
        if self.a:
            self.a.watchers -= 1
        return False


def mark_seen(job_id: str, owner: str) -> bool:
    a = _records.get(job_id)
    if a is None or a.owner != owner:
        return False
    a.seen = True
    return True


def list_for(owner: str) -> List[Dict[str, Any]]:
    """Running jobs, then finished ones not yet seen — newest first."""
    _sweep()
    mine = [a for a in _records.values() if a.owner == owner
            and (a.status == "running" or not a.seen)]
    mine.sort(key=lambda a: a.started_at, reverse=True)
    mine.sort(key=lambda a: a.status != "running")
    return [a.to_dict() for a in mine]
