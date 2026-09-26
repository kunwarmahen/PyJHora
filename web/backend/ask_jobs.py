"""Detached Ask generations — an answer outlives the connection that asked for it.

A streamed answer used to live inside the HTTP response: the moment the socket
went away the generator was cancelled and the reading was lost. Two ordinary
things cut that socket:

* **An idle proxy.** Cloudflare drops a proxied connection that carries no bytes
  for ~100 s. A local thinking model (qwen3 at 64k context, a follow-up question
  carrying the whole thread) routinely sits longer than that before its first
  token — and the tool loop's rounds are not streamed at all — so the reader saw
  "network error" while the GPU was still working.
* **A phone.** iOS suspends or kills a backgrounded Safari tab; the fetch dies
  with it.

So the generation runs as its own task and buffers its SSE frames here; a
response only *follows* a job. Following emits an SSE comment every
``HEARTBEAT_S`` of silence (comments are invisible to the client's parser but
are bytes on the wire, which is all the proxy wants), and a reader who lost the
connection re-attaches with ``after=<last seq>`` and gets exactly the frames it
missed. The job's final step still persists the turn, so an answer finished
while nobody was watching is in the conversation history either way.

In-process on purpose: the backend runs one uvicorn worker, and a job is a
few-minute object — a restart loses in-flight jobs, which the client handles by
falling back to the saved conversation.
"""
from __future__ import annotations

import asyncio
import secrets
import time
from typing import AsyncIterator, Dict, List, Optional

HEARTBEAT_S = 15.0
# How long a finished job stays replayable — long enough for a phone to be
# unlocked hours later... within reason; the saved conversation covers the rest.
KEEP_FINISHED_S = 2 * 60 * 60
# Hard ceiling on a job's life, finished or not.
MAX_AGE_S = 6 * 60 * 60


class AskJob:
    def __init__(self, owner: str):
        self.id = secrets.token_urlsafe(12)
        self.owner = owner
        self.frames: List[str] = []   # whole SSE frames ("data: …\n\n"), seq = index + 1
        self.done = False
        self.created = time.monotonic()
        self.finished_at: Optional[float] = None
        self.task: Optional[asyncio.Task] = None
        self._changed = asyncio.Event()

    def _push(self, frame: str) -> None:
        self.frames.append(frame)
        self._changed.set()

    def _finish(self) -> None:
        self.done = True
        self.finished_at = time.monotonic()
        self._changed.set()

    async def follow(self, after: int = 0) -> AsyncIterator[str]:
        """SSE text for frames after seq `after`, then live ones, with heartbeats.
        Ends when the job is done and everything has been sent."""
        seq = max(0, after)
        while True:
            while seq < len(self.frames):
                frame = self.frames[seq]
                seq += 1
                yield f"id: {seq}\n{frame}"
            if self.done:
                return
            self._changed.clear()
            if seq < len(self.frames):  # a frame landed between the send loop and clear()
                continue
            try:
                await asyncio.wait_for(self._changed.wait(), timeout=HEARTBEAT_S)
            except asyncio.TimeoutError:
                yield ": ping\n\n"


_jobs: Dict[str, AskJob] = {}


def _sweep() -> None:
    now = time.monotonic()
    for jid, job in list(_jobs.items()):
        stale_finished = job.finished_at is not None and now - job.finished_at > KEEP_FINISHED_S
        if stale_finished or now - job.created > MAX_AGE_S:
            if job.task and not job.task.done():
                job.task.cancel()
            _jobs.pop(jid, None)


def start(owner: str, frames: AsyncIterator[str]) -> AskJob:
    """Run `frames` (an async iterator of complete SSE frames) to completion in
    the background, independent of any reader. The first frame every follower
    sees is `{"type":"job","job_id":…}` so it can re-attach later."""
    import json

    _sweep()
    job = AskJob(owner)
    _jobs[job.id] = job
    def frame(obj) -> str:
        return f"data: {json.dumps(obj)}\n\n"

    job._push(frame({"type": "job", "job_id": job.id}))

    async def run():
        try:
            async for f in frames:
                job._push(f)
        except asyncio.CancelledError:
            job._push(frame({"type": "cancelled"}))
            raise
        except Exception as e:  # the generator's own errors are already frames; this is the backstop
            job._push(frame({"type": "error", "message": str(e)}))
        finally:
            job._finish()

    job.task = asyncio.create_task(run())
    return job


def get(job_id: str, owner: str) -> Optional[AskJob]:
    """The job, only for the user who started it (anyone else: as if it didn't exist)."""
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
