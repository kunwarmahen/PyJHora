"""§78: birth details held back from hosted models.

Two halves: the redactor itself (what a hosted model receives), and the claim
that it sits on every path out — asserted by capturing what the provider
adapters are actually handed, for a local and a hosted config.
"""
import asyncio
import json

import pytest

from llm.base import ModelConfig, ProviderType
from llm.privacy import PrivacyPolicy, WITHHELD, is_self_hosted, outbound_policy

BIRTH = {"name": "Asha", "dob": "1985-03-12", "tob": "10:45",
         "place": "Shahgarh, Uttar Pradesh, India",
         "latitude": 27.123456, "longitude": 78.654321, "timezone": 5.5}

PROMPT = """TODAY'S DATE: 2026-09-28

Birth Details:
- Date of Birth: 1985-03-12
- Time of Birth: 10:45
- Place of Birth: Shahgarh, Uttar Pradesh, India

Lagna (Ascendant): Leo
Moon dasha 1985-03-12 to 1992-01-01. Muhurta window 10:45–11:30."""


def _policy(**share):
    p = PrivacyPolicy.from_prefs({f"ai_share_birth_{k}": "true" for k, v in share.items() if v})
    p.remember({"birth_details": BIRTH})
    return p


def _cfg(pt, base_url=None, policy=None):
    return ModelConfig(pt, "m", base_url, "k", privacy=policy)


# ------------------------------------------------------------------ redactor
def test_default_withholds_all_three_and_keeps_the_age():
    out = _policy().redact_text(PROMPT)
    assert "1985-03-12" not in out
    assert "Shahgarh" not in out
    assert "- Time of Birth: " + WITHHELD["time"] in out
    assert "- Date of Birth: " + WITHHELD["date"] + " (age 41)" in out
    assert "- Place of Birth: " + WITHHELD["place"] in out


def test_a_bare_time_is_left_alone():
    # "10:45" is also a muhurta window here; only the labelled line goes.
    out = _policy().redact_text(PROMPT)
    assert "Muhurta window 10:45–11:30" in out


def test_chart_itself_is_untouched():
    out = _policy().redact_text(PROMPT)
    assert "Lagna (Ascendant): Leo" in out
    assert "to 1992-01-01" in out


def test_opting_in_sends_that_item():
    out = _policy(date=True).redact_text(PROMPT)
    assert "- Date of Birth: 1985-03-12" in out
    assert "Shahgarh" not in out
    everything = _policy(date=True, time=True, place=True)
    assert not everything.withholds_anything
    assert everything.redact_text(PROMPT) == PROMPT


def test_tool_result_json_redacts_birth_objects_only():
    result = json.dumps({
        "profile": {"birth_details": BIRTH},
        # A muhurta's location has no dob/tob — it is not birth data.
        "location": {"place": "Delhi", "latitude": 28.61, "longitude": 77.2},
    })
    out = json.loads(_policy().redact_text(result))
    bd = out["profile"]["birth_details"]
    assert bd["dob"] == WITHHELD["date"] and bd["tob"] == WITHHELD["time"]
    assert bd["place"] == bd["latitude"] == bd["longitude"] == WITHHELD["place"]
    assert bd["timezone"] == 5.5 and bd["name"] == "Asha"
    assert out["location"] == {"place": "Delhi", "latitude": 28.61, "longitude": 77.2}


def test_messages_are_copied_not_mutated():
    msgs = [{"role": "system", "content": PROMPT}, {"role": "user", "content": "hi"}]
    out = _policy().redact_messages(msgs)
    assert "1985-03-12" in msgs[0]["content"]
    assert "1985-03-12" not in out[0]["content"]


# ------------------------------------------------------------------ where it runs
@pytest.mark.parametrize("url,local", [
    ("http://localhost:11434", True),
    ("http://127.0.0.1:1234/v1", True),
    ("http://192.168.1.20:11434", True),
    ("http://100.101.1.2:11434", True),          # Tailscale CGNAT range
    ("http://ollama:11434", True),               # compose service name
    ("http://host.docker.internal:11434", True),
    ("https://api.together.xyz/v1", False),
    ("https://ollama.com", False),
])
def test_self_hosted_is_judged_by_endpoint(url, local):
    assert is_self_hosted(_cfg(ProviderType.OPENAI_COMPATIBLE, url)) is local


def test_hosted_providers_are_never_self_hosted():
    assert not is_self_hosted(_cfg(ProviderType.GEMINI))
    assert not is_self_hosted(_cfg(ProviderType.OPENAI, "https://api.openai.com/v1"))


def test_missing_policy_fails_closed():
    assert outbound_policy(_cfg(ProviderType.GEMINI)).withholds_anything
    assert outbound_policy(_cfg(ProviderType.OLLAMA, "http://localhost:11434")) is None


# ------------------------------------------------------------------ every path out
def _capture(monkeypatch):
    """Replace every provider adapter with one that records what it was sent."""
    from llm_service import llm_service
    import ai_outbound
    monkeypatch.setattr(ai_outbound, "record", lambda cfg, redacted: None)
    seen = []

    async def once(prompt, cfg, max_tokens, sys_prompt, usage):
        seen.append(json.dumps([prompt, sys_prompt]))
        return "ok"

    async def chat(messages, specs, cfg):
        seen.append(json.dumps(messages))
        return {"content": "ok", "tool_calls": [], "usage": None}

    async def stream(messages, cfg, cap, usage=None):
        seen.append(json.dumps(messages))
        yield "ok"

    for name in ("_call_ollama", "_call_openai_style", "_call_gemini"):
        monkeypatch.setattr(llm_service, name, once)
    for name in ("_chat_once_ollama", "_chat_once_openai", "_chat_once_gemini"):
        monkeypatch.setattr(llm_service, name, chat)
    for name in ("_stream_ollama", "_stream_openai_style", "_stream_gemini"):
        monkeypatch.setattr(llm_service, name, stream)
    return llm_service, seen


@pytest.mark.parametrize("hosted", [True, False])
def test_every_send_point_redacts_hosted_only(monkeypatch, hosted):
    svc, seen = _capture(monkeypatch)
    cfg = (_cfg(ProviderType.GEMINI, policy=_policy()) if hosted
           else _cfg(ProviderType.OLLAMA, "http://localhost:11434", _policy()))
    msgs = [{"role": "system", "content": PROMPT}, {"role": "user", "content": "?"}]

    async def run():
        await svc._complete_once(PROMPT, cfg, None, PROMPT, None)
        await svc._chat_once_on(msgs, [], cfg, use_json=False)

    asyncio.run(run())
    monkeypatch.setattr(svc, "build_chat_messages", lambda *a, **k: msgs)

    async def stream():
        async for _ in svc.stream_answer({}, "?", None, cfg):
            pass
    asyncio.run(stream())

    assert seen, "no send point was exercised"
    for payload in seen:
        assert ("1985-03-12" in payload) is (not hosted)
        assert ("Shahgarh" in payload) is (not hosted)


def test_plain_chat_send_point_redacts_hosted(monkeypatch):
    """`_complete_chat_once` builds its HTTP call inline (the tool loop's JSON
    protocol and forced final answer), so capture at the HTTP client."""
    import llm_service as mod
    svc, _ = _capture(monkeypatch)
    sent = []

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, headers=None):
            sent.append(__import__("json").dumps(json))
            return _Resp()

    monkeypatch.setattr(mod.httpx, "AsyncClient", _Client)
    cfg = _cfg(ProviderType.OPENAI, "https://api.openai.com/v1", _policy())
    msgs = [{"role": "system", "content": PROMPT}, {"role": "user", "content": "?"}]
    asyncio.run(svc._chat_once_on(msgs, [], cfg, use_json=True))
    assert sent and "1985-03-12" not in sent[0] and "Shahgarh" not in sent[0]
