"""Route wiring for the two new AI readings (arudhas, planetary nakshatras).

The golden tests cover the maths and the prompt; these cover the parts only the
route can get wrong — request-model binding (notably the arudha `selected` list),
the compute call, and that the user's selection actually reaches the LLM layer
rather than being dropped somewhere in between. The model call itself is stubbed,
so no provider, key or network is involved.
"""
import pytest

from tests.conftest import CHART1


@pytest.fixture
def stub_llm(monkeypatch):
    """Replace the model call + config resolution; capture what the route passed."""
    import routes.astrology_ai as mod
    from llm.base import ProviderType

    captured = {}

    class _Cfg:
        provider_type = ProviderType.OLLAMA
        model = "test-model"

    async def _resolve_cfg(_user, _request):
        return _Cfg()

    async def _analyze_arudhas(data, name="x", selected=None, config=None):
        captured.update(kind="arudha", data=data, name=name, selected=selected)
        return "stub arudha reading"

    async def _analyze_planetary(data, name="x", config=None):
        captured.update(kind="nakshatra", data=data, name=name)
        return "stub nakshatra reading"

    async def _save(*_a, **_kw):
        return None

    monkeypatch.setattr(mod, "_resolve_cfg", _resolve_cfg)
    monkeypatch.setattr(mod, "_save_reading", _save)
    monkeypatch.setattr(mod, "_enforce_rate_limit", lambda _u: None)
    monkeypatch.setattr(mod.llm_service, "analyze_arudhas", _analyze_arudhas)
    monkeypatch.setattr(mod.llm_service, "analyze_planetary_nakshatras", _analyze_planetary)
    return captured


def _body(**extra):
    return {"birth_details": CHART1, "person_name": "Tester", **extra}


def test_arudha_analysis_route(client, stub_llm):
    r = client.post("/api/astrology/arudha-analysis", json=_body())
    assert r.status_code == 200, r.text
    assert r.json()["ai_analysis"] == "stub arudha reading"
    # The route must hand the LLM the *enriched* payload, not the bare pada list.
    assert stub_llm["data"]["arudhas"][0]["lord"]
    assert stub_llm["data"]["al_derived"]


def test_arudha_selection_reaches_the_model(client, stub_llm):
    r = client.post("/api/astrology/arudha-analysis", json=_body(selected=["AL", "A7"]))
    assert r.status_code == 200, r.text
    assert stub_llm["selected"] == ["AL", "A7"]


def test_arudha_selection_defaults_to_none_when_absent(client, stub_llm):
    r = client.post("/api/astrology/arudha-analysis", json=_body())
    assert r.status_code == 200, r.text
    assert stub_llm["selected"] is None   # the prompt layer applies the default set


def test_planetary_nakshatras_route(client, stub_llm):
    r = client.post("/api/astrology/planetary-nakshatras-analysis", json=_body())
    assert r.status_code == 200, r.text
    assert r.json()["ai_analysis"] == "stub nakshatra reading"
    assert len(stub_llm["data"]["planetary_nakshatras"]) == 10
