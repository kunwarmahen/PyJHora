"""Graceful degradation when the model can't answer — no network, no database.

The bug behind this suite: the GPU that serves Ollama also runs training jobs,
and when training held the VRAM every AI surface failed in the worst possible
way. Provider adapters report failure by *returning* a string starting with
"Error", nothing checked for it, so:

  * `analyze_daily_digest` returned "Error from Ollama (gemma4): 500 - ..." and
    that text was emailed as the digest narrative and saved into AI history as a
    reading;
  * `digest._profile_block`'s `except Exception → fall back to highlights` — the
    graceful path, already written — could never fire, because failure was a
    perfectly ordinary return value;
  * every one of N profiles in a nightly run waited out its own 300s timeout
    against the same exhausted GPU.

These tests pin the *class* of that bug (no adapter's error text may become an
answer) rather than the three call sites that first showed it.
"""
import asyncio

import pytest

import digest
import scheduler
from llm.base import (LLMUnavailable, ModelConfig, ProviderType,
                      classify_error_text, classify_failure)
from llm.gate import LocalLLMGate
from llm_service import llm_service


@pytest.fixture(autouse=True)
def _clean_gate(monkeypatch):
    """A fresh gate per test — the real one is a process-wide singleton, so a
    tripped breaker would otherwise leak into the next test."""
    fresh = LocalLLMGate()
    monkeypatch.setattr("llm_service.gate", fresh)
    monkeypatch.setattr("llm.providers.ollama.gate", fresh)
    return fresh


def _cfg(provider="ollama", model="gemma4:12b", base_url="http://localhost:11434",
         **kw):
    return ModelConfig(ProviderType(provider), model, base_url, kw.pop("api_key", None),
                       **kw)


# --------------------------------------------------------------------------- #
# Classification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("text,expected", [
    # What Ollama actually says when another process owns the VRAM.
    ('Error from Ollama (gemma4:12b): 500 - {"error":"model requires more '
     'system memory (12.1 GiB) than is available (3.4 GiB)"}', "capacity"),
    ("Error calling Ollama: CUDA error: out of memory", "capacity"),
    ("Error from model: 500 - failed to allocate buffer on device", "capacity"),
    # Plain outage / blip.
    ("Error: Cannot connect to Ollama. Ensure it is running.", "transient"),
    ("Error from Gemini (gemini-2.0-flash): 429 - rate limited", "transient"),
    # The operator must change something; retrying is pointless.
    ("Error: no API key for this provider. Add one in Settings.", "config"),
    ("Error: no model specified for this provider.", "config"),
    # Not an error at all — the most important case, since a misfire here would
    # turn a real reading into a 503.
    ("The Sun is in Leo, and the chart shows an error-free Raja yoga.", None),
    ("", None),
    (None, None),
])
def test_error_text_is_classified(text, expected):
    assert classify_error_text(text) == expected


def test_a_reading_that_merely_mentions_errors_is_not_one():
    """`classify_error_text` requires the "Error" *prefix* the adapters emit;
    prose is never reclassified as a failure."""
    prose = "Saturn's transit brings errors of judgement and out of memory of them."
    assert classify_error_text(prose) is None
    # ...whereas an exception message, which carries no prefix, still classifies.
    assert classify_failure("CUDA out of memory") == "capacity"


@pytest.mark.parametrize("kind,status,retryable", [
    ("capacity", 503, True),
    ("transient", 503, True),
    ("config", 400, False),
    ("fatal", 502, False),
])
def test_status_and_retryability_follow_the_kind(kind, status, retryable):
    e = LLMUnavailable("Error: x", kind=kind)
    assert e.status_code == status and e.retryable is retryable


def test_llm_unavailable_is_an_http_exception():
    """~50 route handlers already do `except HTTPException: raise` before their
    catch-all 500. Subclassing is what makes the right status reach the client
    without editing any of them — if this ever stops being true, every AI route
    silently reverts to reporting "500 Internal Server Error"."""
    from fastapi import HTTPException
    assert issubclass(LLMUnavailable, HTTPException)


# --------------------------------------------------------------------------- #
# The class of bug: an adapter's error string must never become an answer
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("adapter,provider", [
    ("_call_ollama", "ollama"),
    ("_call_openai_style", "openai"),
    ("_call_gemini", "gemini"),
])
def test_no_adapter_error_string_is_returned_as_an_answer(monkeypatch, adapter,
                                                          provider):
    async def _err(*a, **k):
        return "Error from provider: 500 - something went wrong"

    monkeypatch.setattr(llm_service, adapter, _err)
    cfg = _cfg(provider, model="m", api_key="k")
    cfg.fallbacks = []
    with pytest.raises(LLMUnavailable):
        asyncio.run(llm_service._complete("prompt", cfg))


def test_a_successful_completion_is_returned_untouched(monkeypatch):
    async def _ok(*a, **k):
        return "Jupiter aspects the 5th."

    monkeypatch.setattr(llm_service, "_call_ollama", _ok)
    assert asyncio.run(llm_service._complete("p", _cfg())) == "Jupiter aspects the 5th."


def test_a_raised_provider_error_is_normalised_too(monkeypatch):
    """Some adapters raise instead of returning; both must arrive as the same
    exception type, or callers need two error paths and will forget one."""
    async def _boom(*a, **k):
        raise RuntimeError("Ollama: 500 - unable to load model")

    monkeypatch.setattr(llm_service, "_call_ollama", _boom)
    with pytest.raises(LLMUnavailable) as ei:
        asyncio.run(llm_service._complete("p", _cfg()))
    assert ei.value.kind == "capacity"


# --------------------------------------------------------------------------- #
# The gate: serialisation + capacity breaker
# --------------------------------------------------------------------------- #
def test_a_capacity_failure_reads_as_english_but_keeps_the_provider_text():
    """"model requires more system memory (12.1 GiB)" is true and unreadable. The
    user gets a sentence; the log keeps what the provider actually said."""
    raw = ('Error from Ollama (gemma4:12b): 500 - {"error":"model requires more '
           'system memory"}')
    e = LLMUnavailable.from_error_text(raw, _cfg())
    assert e.kind == "capacity"
    assert "busy with another workload" in e.detail
    assert e.provider_message == raw
    # Everything else is passed through verbatim — no invented wording.
    other = LLMUnavailable.from_error_text("Error: Cannot connect to Ollama.", _cfg())
    assert other.detail == "Error: Cannot connect to Ollama."


def test_capacity_failure_trips_the_breaker_and_the_next_caller_fails_fast(
        monkeypatch, _clean_gate):
    calls = {"n": 0}

    async def _oom(*a, **k):
        calls["n"] += 1
        return "Error from Ollama: 500 - model requires more system memory"

    monkeypatch.setattr(llm_service, "_call_ollama", _oom)
    cfg = _cfg()

    with pytest.raises(LLMUnavailable):
        asyncio.run(llm_service._complete("p", cfg))
    assert calls["n"] == 1

    # Second caller must not reach the provider at all: that is the whole point —
    # 20 digest profiles used to each wait out their own 300s timeout.
    with pytest.raises(LLMUnavailable) as ei:
        asyncio.run(llm_service._complete("p", cfg))
    assert calls["n"] == 1
    assert ei.value.kind == "capacity"
    assert ei.value.retry_after and ei.value.retry_after > 0


def test_a_transient_failure_does_not_trip_the_breaker(monkeypatch, _clean_gate):
    async def _down(*a, **k):
        return "Error: Cannot connect to Ollama."

    monkeypatch.setattr(llm_service, "_call_ollama", _down)
    with pytest.raises(LLMUnavailable):
        asyncio.run(llm_service._complete("p", _cfg()))
    assert _clean_gate.blocked_for(_clean_gate.host_key(_cfg())) == 0


def test_success_clears_the_breaker(monkeypatch, _clean_gate):
    cfg = _cfg()
    key = _clean_gate.host_key(cfg)
    _clean_gate.trip(key, "Error: out of memory")
    assert _clean_gate.blocked_for(key) > 0

    async def _ok(*a, **k):
        return "answer"

    monkeypatch.setattr(llm_service, "_call_ollama", _ok)
    monkeypatch.setattr("llm.gate.LOCAL_LLM_COOLDOWN", 0.0)
    _clean_gate.clear(key)
    assert asyncio.run(llm_service._complete("p", cfg)) == "answer"
    assert _clean_gate.blocked_for(key) == 0


def test_local_calls_are_serialised(monkeypatch, _clean_gate):
    """Two readings sharing a contended GPU are slower than the same two run back
    to back — and far likelier to OOM. Concurrency is 1 by default."""
    live = {"now": 0, "max": 0}

    async def _slow(*a, **k):
        live["now"] += 1
        live["max"] = max(live["max"], live["now"])
        await asyncio.sleep(0.02)
        live["now"] -= 1
        return "answer"

    monkeypatch.setattr(llm_service, "_call_ollama", _slow)

    async def _both():
        return await asyncio.gather(*[llm_service._complete("p", _cfg())
                                      for _ in range(4)])

    assert asyncio.run(_both()) == ["answer"] * 4
    assert live["max"] == 1


def test_hosted_providers_are_not_gated(monkeypatch, _clean_gate):
    """A hosted API's capacity is not ours to protect — serialising it would just
    make the cloud fallback as slow as the busy GPU it is standing in for."""
    live = {"now": 0, "max": 0}

    async def _slow(*a, **k):
        live["now"] += 1
        live["max"] = max(live["max"], live["now"])
        await asyncio.sleep(0.02)
        live["now"] -= 1
        return "answer"

    monkeypatch.setattr(llm_service, "_call_gemini", _slow)

    async def _both():
        cfgs = [_cfg("gemini", model="g", base_url=None, api_key="k")
                for _ in range(3)]
        return await asyncio.gather(*[llm_service._complete("p", c) for c in cfgs])

    asyncio.run(_both())
    assert live["max"] == 3


def test_a_queue_that_never_frees_up_fails_instead_of_hanging(monkeypatch,
                                                              _clean_gate):
    monkeypatch.setattr("llm.gate.LOCAL_LLM_QUEUE_WAIT", 0.05)

    async def _slow(*a, **k):
        await asyncio.sleep(0.6)
        return "answer"

    monkeypatch.setattr(llm_service, "_call_ollama", _slow)

    async def _race():
        first = asyncio.create_task(llm_service._complete("p", _cfg()))
        await asyncio.sleep(0.01)
        try:
            return await llm_service._complete("p", _cfg())
        finally:
            first.cancel()

    with pytest.raises(LLMUnavailable) as ei:
        asyncio.run(_race())
    assert ei.value.kind == "transient"


# --------------------------------------------------------------------------- #
# The fallback chain
# --------------------------------------------------------------------------- #
def test_a_busy_gpu_falls_back_to_the_next_config(monkeypatch, _clean_gate):
    async def _oom(*a, **k):
        return "Error from Ollama: 500 - CUDA out of memory"

    async def _cloud(*a, **k):
        return "answered by the cloud"

    monkeypatch.setattr(llm_service, "_call_ollama", _oom)
    monkeypatch.setattr(llm_service, "_call_gemini", _cloud)

    cfg = _cfg()
    cfg.fallbacks = [_cfg("gemini", model="gemini-2.0-flash", base_url=None,
                          api_key="k")]
    assert asyncio.run(llm_service._complete("p", cfg)) == "answered by the cloud"


def test_a_config_error_is_reported_not_papered_over(monkeypatch, _clean_gate):
    """A wrong API key must surface. Falling back would leave the user's real
    problem invisible while quietly answering from a model they didn't choose."""
    async def _nokey(*a, **k):
        return "Error: no API key for this provider."

    async def _local(*a, **k):
        return "answered locally"

    monkeypatch.setattr(llm_service, "_call_gemini", _nokey)
    monkeypatch.setattr(llm_service, "_call_ollama", _local)

    cfg = _cfg("gemini", model="g", base_url=None, api_key="bad")
    cfg.fallbacks = [_cfg()]
    with pytest.raises(LLMUnavailable) as ei:
        asyncio.run(llm_service._complete("p", cfg))
    assert ei.value.kind == "config" and ei.value.status_code == 400


def test_the_last_link_failing_raises_rather_than_returning_text(monkeypatch,
                                                                 _clean_gate):
    async def _oom(*a, **k):
        return "Error from Ollama: 500 - out of memory"

    monkeypatch.setattr(llm_service, "_call_ollama", _oom)
    monkeypatch.setattr(llm_service, "_call_gemini", _oom)
    cfg = _cfg()
    cfg.fallbacks = [_cfg("gemini", model="g", base_url=None, api_key="k")]
    with pytest.raises(LLMUnavailable):
        asyncio.run(llm_service._complete("p", cfg))


def test_local_primary_only_offers_cloud_providers_that_have_a_key(monkeypatch):
    monkeypatch.setattr(llm_service, "gemini_api_key", "", raising=False)
    monkeypatch.setattr(llm_service, "openai_api_key", "", raising=False)
    monkeypatch.setattr(llm_service, "openrouter_api_key", "", raising=False)

    cfg = _cfg()
    assert llm_service.build_fallbacks(cfg, {}) == []

    chain = llm_service.build_fallbacks(cfg, {"gemini": "user-key"})
    assert [c.provider_type for c in chain] == [ProviderType.GEMINI]
    assert chain[0].api_key == "user-key"


def test_a_cloud_primary_falls_back_to_the_local_model(monkeypatch):
    cfg = _cfg("gemini", model="g", base_url=None, api_key="k")
    cfg.max_tokens = 1024
    chain = llm_service.build_fallbacks(cfg, {})
    assert [c.provider_type for c in chain] == [ProviderType.OLLAMA]
    # The output cap is the user's setting, not the provider's — it must follow.
    assert chain[0].max_tokens == 1024


def test_fallbacks_can_be_turned_off(monkeypatch):
    monkeypatch.setattr("llm_service.LLM_FALLBACK_ENABLED", False)
    cfg = _cfg("gemini", model="g", base_url=None, api_key="k")
    assert llm_service.build_fallbacks(cfg, {}) == []


def test_a_cpu_only_endpoint_is_appended_for_local_primaries(monkeypatch):
    """The last resort: slow, but it never competes for the GPU."""
    monkeypatch.setattr("llm_service.OLLAMA_CPU_URL", "http://localhost:11435")
    chain = llm_service.config_chain(_cfg())
    assert [c.base_url for c in chain] == ["http://localhost:11434",
                                           "http://localhost:11435"]
    # Not appended twice when it is already the primary.
    same = llm_service.config_chain(_cfg(base_url="http://localhost:11435"))
    assert len(same) == 1


def test_no_cpu_endpoint_configured_leaves_the_chain_alone():
    assert llm_service.config_chain(_cfg()) == [_cfg()]


# --------------------------------------------------------------------------- #
# Streaming
# --------------------------------------------------------------------------- #
def _drain(gen):
    async def _run():
        return [c async for c in gen]
    return asyncio.run(_run())


def test_a_stream_that_dies_before_the_first_token_moves_to_the_fallback(
        monkeypatch, _clean_gate):
    async def _oom(*a, **k):
        yield "Error from Ollama: 500 - model requires more system memory"

    async def _cloud(*a, **k):
        yield "Jupiter "
        yield "aspects."

    monkeypatch.setattr(llm_service, "_stream_ollama", _oom)
    monkeypatch.setattr(llm_service, "_stream_gemini", _cloud)

    cfg = _cfg()
    cfg.fallbacks = [_cfg("gemini", model="g", base_url=None, api_key="k")]
    assert _drain(llm_service.stream_answer({}, "q", None, cfg)) == ["Jupiter ",
                                                                     "aspects."]


def test_a_stream_with_nowhere_left_to_go_yields_the_error_as_text(monkeypatch,
                                                                   _clean_gate):
    """The SSE route's contract: this generator yields text, never raises. A
    failure the user can read beats a dead connection."""
    async def _oom(*a, **k):
        yield "Error from Ollama: 500 - out of memory"

    monkeypatch.setattr(llm_service, "_stream_ollama", _oom)
    out = _drain(llm_service.stream_answer({}, "q", None, _cfg()))
    assert len(out) == 1 and "busy with another workload" in out[0]


def test_a_mid_stream_failure_is_not_retried(monkeypatch, _clean_gate):
    """Once real tokens have reached the client, restarting would duplicate text."""
    async def _half(*a, **k):
        yield "Jupiter "
        yield "Error: Cannot connect to Ollama."

    monkeypatch.setattr(llm_service, "_stream_ollama", _half)
    out = _drain(llm_service.stream_answer({}, "q", None, _cfg()))
    assert out == ["Jupiter ", "Error: Cannot connect to Ollama."]


# --------------------------------------------------------------------------- #
# Scheduled digests: defer rather than send a permanently thinner digest
# --------------------------------------------------------------------------- #
def test_only_a_recoverable_narrative_failure_defers_the_digest():
    """A missing narrative is worth waiting for only if waiting could help. A
    model that is simply unconfigured will still be unconfigured in ten minutes,
    so that digest goes out now with its rule-based highlights."""
    busy = [{"name": "A", "_ai_retryable": True}, {"name": "B"}]
    assert digest.should_defer(busy, allow_defer=True) is True
    assert digest.should_defer([{"name": "A"}, {"name": "B"}], allow_defer=True) is False


def test_a_manual_send_never_defers():
    """Someone pressed "send me one now" — give them what we have."""
    assert digest.should_defer([{"name": "A", "_ai_retryable": True}],
                               allow_defer=False) is False


@pytest.mark.parametrize("kind,expected", [
    ("capacity", True), ("transient", True), ("config", False), ("fatal", False),
])
def test_the_block_flag_follows_the_failure_kind(kind, expected):
    """`_profile_block` sets `_ai_retryable` from the exception's own verdict, so
    this is the contract between the two."""
    assert LLMUnavailable("Error: x", kind=kind).retryable is expected


class _FakeCollection:
    def __init__(self):
        self.updates = []

    async def update_one(self, flt, update):
        self.updates.append((flt, update))


class _FakeDB:
    def __init__(self):
        self.col = _FakeCollection()

    def __getitem__(self, _name):
        return self.col


def test_deferring_gives_the_claim_back_so_a_later_tick_retries():
    """Without the rollback the window counts as served and the user simply never
    gets this digest — the failure mode deferral exists to prevent."""
    db = _FakeDB()
    doc = {"notifications": {"last_sent_date": "2026-07-29"}}
    asyncio.run(scheduler._defer(db, "u", "last_sent_date", "2026-07-30", doc, 0))

    flt, update = db.col.updates[0]
    assert flt == {"user_id": "u"}
    # Restored to the *previous* window, not cleared.
    assert update["$set"]["notifications.last_sent_date"] == "2026-07-29"
    assert update["$set"]["notifications.last_sent_date_defer"] == {
        "key": "2026-07-30", "count": 1}


def test_deferring_a_never_sent_user_clears_the_claim_field():
    db = _FakeDB()
    asyncio.run(scheduler._defer(db, "u", "last_sent_date", "2026-07-30",
                                 {"notifications": {}}, 2))
    _flt, update = db.col.updates[0]
    assert update["$unset"] == {"notifications.last_sent_date": ""}
    assert update["$set"]["notifications.last_sent_date_defer"]["count"] == 3


def test_deferrals_are_counted_per_window_not_forever():
    """Yesterday's patience must not be spent on today's digest."""
    same = {"notifications": {"last_sent_date_defer": {"key": "2026-07-30",
                                                       "count": 4}}}
    assert scheduler._deferrals_so_far(same, "last_sent_date", "2026-07-30") == 4
    assert scheduler._deferrals_so_far(same, "last_sent_date", "2026-07-31") == 0
    assert scheduler._deferrals_so_far({}, "last_sent_date", "2026-07-30") == 0


def test_deferral_is_bounded_so_the_digest_eventually_goes_out():
    """Late beats never: past the cap the digest sends with highlights only."""
    from config import settings
    assert settings.DIGEST_AI_MAX_DEFERRALS >= 1
    doc = {"notifications": {"last_sent_date_defer":
                             {"key": "k", "count": settings.DIGEST_AI_MAX_DEFERRALS}}}
    reached = scheduler._deferrals_so_far(doc, "last_sent_date", "k")
    assert not (reached < settings.DIGEST_AI_MAX_DEFERRALS)  # allow_defer is False
