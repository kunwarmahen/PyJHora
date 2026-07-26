"""Provider wiring for the LLM service — no network, no database.

The dispatch sites (completion / streaming / tool mode) used to list the
OpenAI-schema provider types inline, so adding a provider meant editing five
tuples and silently getting "Unsupported LLM provider" from whichever one was
missed. These tests pin the wiring instead of the prose.
"""
import asyncio
import time

import pytest

from llm.base import (OPENAI_STYLE_PROVIDERS, ProviderType, _KEY_ENV_VAR,
                      _missing_key_error, _request_timeout)
from llm_service import llm_service


def test_openrouter_resolves_to_its_own_endpoint_and_key():
    cfg = llm_service.resolve_config("openrouter", api_key="sk-or-test")
    assert cfg.provider_type is ProviderType.OPENROUTER
    assert cfg.base_url == "https://openrouter.ai/api/v1"
    assert cfg.api_key == "sk-or-test"
    # A blank model falls back to the server-side default, never to empty.
    assert cfg.model


def test_openrouter_speaks_the_openai_schema():
    """It must be in the shared tuple, or _complete/_stream/_chat_once all bail
    out with "Unsupported LLM provider" at runtime."""
    assert ProviderType.OPENROUTER in OPENAI_STYLE_PROVIDERS


def test_every_provider_type_is_dispatchable():
    """Every enum member is handled by some adapter — Ollama and Gemini have
    their own, everything else must be OpenAI-schema."""
    handled = set(OPENAI_STYLE_PROVIDERS) | {ProviderType.OLLAMA, ProviderType.GEMINI}
    assert set(ProviderType) == handled


def test_cloud_providers_report_a_missing_key_by_env_var_name():
    for pt in (ProviderType.OPENAI, ProviderType.OPENROUTER, ProviderType.GEMINI):
        msg = _missing_key_error(pt)
        assert msg and _KEY_ENV_VAR[pt] in msg
    # Keyless providers must not produce a key error (Ollama is local; a
    # local OpenAI-compatible server usually needs no key either).
    assert _missing_key_error(ProviderType.OLLAMA) is None
    assert _missing_key_error(ProviderType.OPENAI_COMPATIBLE) is None


def test_slow_providers_get_the_long_timeout():
    assert _request_timeout(ProviderType.OPENROUTER) == 300.0
    assert _request_timeout(ProviderType.OPENAI_COMPATIBLE) == 300.0
    assert _request_timeout(ProviderType.OPENAI) == 120.0


def test_openrouter_status_needs_a_key_and_caches_the_catalogue(monkeypatch):
    """Availability follows the key; the model list is served from cache without
    re-fetching (list_providers runs on every settings/chat page load)."""
    monkeypatch.setattr(llm_service, "openrouter_api_key", "", raising=False)
    monkeypatch.setattr(llm_service, "_model_cache",
                        {"openrouter": (["vendor/a", "vendor/b"], time.monotonic())},
                        raising=False)

    async def _boom(*a, **k):  # any HTTP call here is a cache miss = test failure
        raise AssertionError("catalogue was re-fetched despite a warm cache")

    monkeypatch.setattr("httpx.AsyncClient.get", _boom)

    off = asyncio.run(llm_service._openrouter_status())
    assert off["available"] is False
    assert "OPENROUTER_API_KEY" in off["reason"]
    assert off["models"] == ["vendor/a", "vendor/b"]
    # Configured default isn't in the catalogue and no known-good substitute is
    # either, so the user's configured id is preserved rather than blanked.
    assert off["default_model"] == llm_service.openrouter_default_model

    on = asyncio.run(llm_service._openrouter_status(user_key="sk-or-user"))
    assert on["available"] is True and on["has_user_key"] is True
    assert on["reason"] is None


def test_catalogue_failure_degrades_to_the_static_lists(monkeypatch):
    """A cold cache plus an unreachable vendor API must not raise: OpenRouter
    falls back to an empty dropdown (typed ids still work), while Gemini and
    OpenAI fall back to their curated lists so the picker is never empty."""
    monkeypatch.setattr(llm_service, "_model_cache", {}, raising=False)

    async def _fail(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("httpx.AsyncClient.get", _fail)
    assert asyncio.run(llm_service._openrouter_models()) == []
    assert asyncio.run(llm_service._gemini_models("k")) == []

    gem = asyncio.run(llm_service._gemini_status(user_key="k"))
    assert gem["models"] == list(llm_service._GEMINI_FALLBACK_MODELS)
    oai = asyncio.run(llm_service._openai_status(user_key="k"))
    assert oai["models"] == list(llm_service._OPENAI_FALLBACK_MODELS)


def test_live_catalogues_replace_the_static_lists(monkeypatch):
    """The whole point of listing live: a model released after this code was
    written (say gemini-3.5-flash) must reach the dropdown."""
    monkeypatch.setattr(llm_service, "_model_cache", {}, raising=False)

    class _Resp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    async def _get(self, url, **kwargs):
        if "generativelanguage" in url:
            return _Resp({"models": [
                {"name": "models/gemini-3.5-flash",
                 "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/text-embedding-004",
                 "supportedGenerationMethods": ["embedContent"]},
            ]})
        return _Resp({"data": [{"id": "gpt-6"}, {"id": "text-embedding-3-large"},
                               {"id": "whisper-1"}]})

    monkeypatch.setattr("httpx.AsyncClient.get", _get)

    gem = asyncio.run(llm_service._gemini_status(user_key="k"))
    assert gem["models"] == ["gemini-3.5-flash"]  # embedding model filtered out
    oai = asyncio.run(llm_service._openai_status(user_key="k"))
    assert oai["models"] == ["gpt-6"]  # embeddings + whisper filtered out


def test_gemini_without_a_key_shows_the_static_list_and_no_network(monkeypatch):
    """No key means no ListModels call is even possible — don't attempt one."""
    monkeypatch.setattr(llm_service, "gemini_api_key", "", raising=False)
    monkeypatch.setattr(llm_service, "_model_cache", {}, raising=False)

    async def _boom(*a, **k):
        raise AssertionError("called the vendor API without a key")

    monkeypatch.setattr("httpx.AsyncClient.get", _boom)
    status = asyncio.run(llm_service._gemini_status())
    assert status["available"] is False
    assert status["models"] == list(llm_service._GEMINI_FALLBACK_MODELS)


def test_openrouter_sends_attribution_headers(monkeypatch):
    monkeypatch.setattr(llm_service, "openrouter_site_url", "https://example.com",
                        raising=False)
    cfg = llm_service.resolve_config("openrouter", api_key="sk-or-test")
    headers = llm_service._openai_style_headers(cfg)
    assert headers["Authorization"] == "Bearer sk-or-test"
    assert headers["HTTP-Referer"] == "https://example.com"
    assert headers["X-Title"]

    # Other providers get no OpenRouter-specific headers.
    plain = llm_service._openai_style_headers(llm_service.resolve_config("openai", api_key="sk"))
    assert "HTTP-Referer" not in plain and "X-Title" not in plain


def test_retired_default_model_is_substituted_not_served():
    """`default_model` is handed straight to the next request, so it must exist
    in the live catalogue whenever we can see one."""
    pick = llm_service._pick_default_model
    live = ["gemini-2.0-flash", "gemini-3.5-flash"]
    # Still offered -> untouched.
    assert pick("gemini-3.5-flash", live, ("gemini-2.0-flash",)) == "gemini-3.5-flash"
    # Retired -> first preferred id that is actually listed.
    assert pick("gemini-1.5-flash", live, ("gemini-2.0-flash",)) == "gemini-2.0-flash"
    # No preferred id available -> keep the configured one rather than guess.
    assert pick("gemini-1.5-flash", live, ("nope",)) == "gemini-1.5-flash"
    # Empty catalogue means "couldn't read it", not "model is gone".
    assert pick("gemini-1.5-flash", [], ("gemini-2.0-flash",)) == "gemini-1.5-flash"


def test_keyed_providers_covers_every_provider_that_needs_a_key():
    """The Settings → API Keys tab and the POST validation both read this tuple;
    a provider missing from it can never receive a per-user key."""
    import user_settings
    for pt in _KEY_ENV_VAR:
        assert pt.value in user_settings.KEYED_PROVIDERS


@pytest.mark.parametrize("alias,expected", [
    ("openrouter", ProviderType.OPENROUTER),
    ("chatgpt", ProviderType.OPENAI),
    ("qwen", ProviderType.OLLAMA),
    ("nonsense", ProviderType.OLLAMA),
])
def test_legacy_and_new_provider_strings_resolve(alias, expected):
    assert llm_service.resolve_config(alias).provider_type is expected


# --------------------------------------------------------------------------- #
# Stale model guard (ensure_model_installed)
# --------------------------------------------------------------------------- #
def _warm_ollama_cache(monkeypatch, installed):
    """Pre-fill the model cache for the configured Ollama host, and make any
    HTTP call a failure so the test proves the cache is what's read."""
    url = llm_service.ollama_url.rstrip("/")
    monkeypatch.setattr(llm_service, "_model_cache",
                        {f"ollama@{url}": (installed, time.monotonic())},
                        raising=False)

    async def _boom(*a, **k):
        raise AssertionError("catalogue was re-fetched despite a warm cache")

    monkeypatch.setattr("httpx.AsyncClient.get", _boom)


def test_model_from_another_provider_falls_back_to_the_default(monkeypatch):
    """The reported bug: a Gemini model id left over from a provider switch was
    sent to Ollama, and every reading answered "model not found"."""
    _warm_ollama_cache(monkeypatch, ["gemma4:12b", "llama3:8b"])
    monkeypatch.setattr(llm_service, "ollama_default_model", "gemma4:12b",
                        raising=False)

    cfg = llm_service.resolve_config("ollama", model="gemini-3.5-flash")
    assert asyncio.run(llm_service.ensure_model_installed(cfg)).model == "gemma4:12b"


def test_a_bare_model_name_matches_its_latest_tag(monkeypatch):
    """Ollama resolves "llama3" to "llama3:latest" — it is not a missing model."""
    _warm_ollama_cache(monkeypatch, ["llama3:latest"])
    cfg = llm_service.resolve_config("ollama", model="llama3")
    assert asyncio.run(llm_service.ensure_model_installed(cfg)).model == "llama3"


def test_an_unreadable_catalogue_changes_nothing(monkeypatch):
    """Ollama down ⇒ an empty list. Nothing is judged missing; the call fails on
    its own terms rather than being silently re-pointed."""
    _warm_ollama_cache(monkeypatch, [])
    cfg = llm_service.resolve_config("ollama", model="gemma4:12b")
    assert asyncio.run(llm_service.ensure_model_installed(cfg)).model == "gemma4:12b"


def test_fallback_uses_an_installed_model_when_the_default_is_gone(monkeypatch):
    """`ollama rm` of the configured default must not leave us substituting
    another model that isn't there either."""
    _warm_ollama_cache(monkeypatch, ["llama3:8b"])
    monkeypatch.setattr(llm_service, "ollama_default_model", "gemma4:12b",
                        raising=False)
    cfg = llm_service.resolve_config("ollama", model="mistral:7b")
    assert asyncio.run(llm_service.ensure_model_installed(cfg)).model == "llama3:8b"


def test_hosted_providers_are_left_alone(monkeypatch):
    """Only Ollama's catalogue is local, keyless and authoritative — a hosted
    provider's model id is never second-guessed (and never fetched here)."""
    async def _boom(*a, **k):
        raise AssertionError("a hosted provider's catalogue was fetched")

    monkeypatch.setattr("httpx.AsyncClient.get", _boom)
    cfg = llm_service.resolve_config("gemini", model="gemini-3.5-flash",
                                     api_key="k")
    assert asyncio.run(llm_service.ensure_model_installed(cfg)).model == "gemini-3.5-flash"
