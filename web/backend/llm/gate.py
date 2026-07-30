"""Admission control for locally-hosted models.

The problem this solves: the GPU that serves Ollama is the same GPU that runs
training jobs. When training holds the VRAM, an inference request does not fail
fast — Ollama falls back to CPU or blocks, so every reading burns its full 300s
timeout, and a nightly digest over N profiles takes N × 300s to produce nothing.
Meanwhile each concurrent request makes the contention worse.

Two mechanisms, both per *host* (not per process-wide singleton — a user may
point at a different Ollama box than the server default, and one being busy says
nothing about the other):

  * a **semaphore** so at most LOCAL_LLM_CONCURRENCY requests are in flight.
    Serialising is strictly faster than sharing a contended GPU, and callers that
    cannot get a slot within LOCAL_LLM_QUEUE_WAIT are told so instead of hanging.
  * a **circuit breaker**: one capacity failure marks the host out-of-capacity
    for LOCAL_LLM_COOLDOWN, so subsequent callers are refused in microseconds and
    fall through to their fallback chain rather than re-discovering the same
    exhausted GPU one 300s timeout at a time.

Hosted providers pass straight through: their capacity is not ours to protect.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from typing import Dict, Optional, Tuple

from .base import (LLMUnavailable, LOCAL_PROVIDERS, LOCAL_LLM_CONCURRENCY,
                   LOCAL_LLM_COOLDOWN, LOCAL_LLM_GATE_ENABLED,
                   LOCAL_LLM_QUEUE_WAIT, ModelConfig)


class LocalLLMGate:
    """Per-host semaphore + capacity breaker for local model servers."""

    def __init__(self):
        self._sems: Dict[str, asyncio.Semaphore] = {}
        # host -> (blocked_until_monotonic, reason)
        self._blocked: Dict[str, Tuple[float, str]] = {}

    # ---------------------------------------------------------------- #
    # Keys and state
    # ---------------------------------------------------------------- #
    @staticmethod
    def is_local(cfg: ModelConfig) -> bool:
        return cfg is not None and cfg.provider_type in LOCAL_PROVIDERS

    @staticmethod
    def host_key(cfg: ModelConfig) -> str:
        """One key per endpoint. Two providers on the same box still share a GPU,
        but they are configured separately and reported separately, so the key
        includes the base URL rather than only the provider."""
        return f"{cfg.provider_type.value}@{(cfg.base_url or '').rstrip('/')}"

    def _sem(self, key: str) -> asyncio.Semaphore:
        # Created lazily and never inside a lock: asyncio.Semaphore construction
        # cannot yield, so there is no interleaving point between the check and
        # the set on a single event loop.
        sem = self._sems.get(key)
        if sem is None:
            sem = asyncio.Semaphore(LOCAL_LLM_CONCURRENCY)
            self._sems[key] = sem
        return sem

    def blocked_for(self, key: str) -> float:
        """Seconds remaining on this host's cooldown (0.0 when it is available)."""
        until, _reason = self._blocked.get(key, (0.0, ""))
        return max(0.0, until - time.monotonic())

    def block_reason(self, key: str) -> Optional[str]:
        return self._blocked.get(key, (0.0, None))[1] if self.blocked_for(key) else None

    def trip(self, key: str, reason: str) -> None:
        self._blocked[key] = (time.monotonic() + LOCAL_LLM_COOLDOWN, reason)
        print(f"[llm-gate] {key} marked out of capacity for "
              f"{int(LOCAL_LLM_COOLDOWN)}s: {reason[:200]}")

    def clear(self, key: str) -> None:
        if key in self._blocked:
            del self._blocked[key]
            print(f"[llm-gate] {key} has capacity again")

    def status(self, base_url: str, provider: str = "ollama") -> Dict[str, object]:
        """What the Settings/health surfaces report for this endpoint."""
        key = f"{provider}@{(base_url or '').rstrip('/')}"
        remaining = self.blocked_for(key)
        sem = self._sems.get(key)
        return {
            "busy": remaining > 0,
            "retry_after": int(remaining) if remaining else None,
            "reason": self.block_reason(key),
            # Semaphore._value is the count of free slots; absent = never used.
            "in_flight": (LOCAL_LLM_CONCURRENCY - sem._value) if sem else 0,
            "concurrency": LOCAL_LLM_CONCURRENCY,
        }

    # ---------------------------------------------------------------- #
    # The gate itself
    # ---------------------------------------------------------------- #
    @asynccontextmanager
    async def slot(self, cfg: ModelConfig):
        """Hold a slot on `cfg`'s host for the duration of one model call.

        Raises LLMUnavailable *before* the call when the host is in cooldown or
        the queue wait expires. A capacity failure inside the block trips the
        breaker; any clean completion clears it.
        """
        if not LOCAL_LLM_GATE_ENABLED or not self.is_local(cfg):
            yield
            return

        key = self.host_key(cfg)
        remaining = self.blocked_for(key)
        if remaining > 0:
            raise LLMUnavailable(
                f"Error: the local model host is out of capacity (the GPU is in use "
                f"by another workload). Retrying in {int(remaining)}s.",
                kind="capacity", provider=cfg.provider_type.value, model=cfg.model,
                retry_after=int(remaining) + 1)

        sem = self._sem(key)
        try:
            await asyncio.wait_for(sem.acquire(), timeout=LOCAL_LLM_QUEUE_WAIT)
        except asyncio.TimeoutError:
            raise LLMUnavailable(
                f"Error: the local model is busy with another request and did not "
                f"free up within {int(LOCAL_LLM_QUEUE_WAIT)}s.",
                kind="transient", provider=cfg.provider_type.value, model=cfg.model,
                retry_after=int(LOCAL_LLM_QUEUE_WAIT))

        try:
            yield
        except LLMUnavailable as e:
            if e.kind == "capacity":
                # Log what the provider said, not the sentence shown to the user —
                # "requires more system memory (12.1 GiB)" is the diagnostic.
                self.trip(key, e.provider_message)
            raise
        else:
            self.clear(key)
        finally:
            sem.release()


gate = LocalLLMGate()
