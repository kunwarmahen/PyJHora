"""A hosted model must be able to find the foundation of a reading (§91).

claude.ai, reading the MCP connector, answered five questions without ever
fetching the natal chart: it read a forecast from an event list, a career
question from nothing, and said a past year could not be read because no
transit tool took a date. These pin the fixes:

  * get_reading_context bundles chart + topic houses + varga + dasha + transits,
    for today or any date, for every topic it advertises;
  * get_transits / get_upcoming_events accept a past date;
  * get_life_timeline's "next" lists hold no past dates;
  * the MCP server instructions only name tools that exist.
"""
import importlib.util
import os
import re

import pytest

import tools as tool_registry
from tests.conftest import CHART1

_INSTR = os.path.join(os.path.dirname(__file__), "..", "..", "mcp", "instructions.py")


def _instructions() -> str:
    spec = importlib.util.spec_from_file_location("mcp_instructions", _INSTR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.INSTRUCTIONS


def test_mcp_instructions_name_only_real_tools():
    names = set(re.findall(r"\b(get_[a-z_]+|search_[a-z_]+)\b", _instructions()))
    assert names, "instructions name no tools"
    unknown = sorted(n for n in names if n not in tool_registry.TOOLS)
    assert not unknown, f"MCP instructions name unknown tools: {unknown}"


def test_reading_topics_reference_real_vargas_and_tools():
    assert set(tool_registry.READING_TOPICS) == set(tool_registry._TOPIC_NEXT)
    for topic, (houses, varga) in tool_registry.READING_TOPICS.items():
        assert varga in tool_registry.SUPPORTED_VARGAS and varga != 1, topic
        assert houses and all(1 <= h <= 12 for h in houses), topic
    unknown = {n for ns in tool_registry._TOPIC_NEXT.values() for n in ns
               if n not in tool_registry.TOOLS}
    assert not unknown, unknown
    schema = tool_registry.TOOLS["get_reading_context"].parameters
    assert schema["properties"]["topic"]["enum"] == list(tool_registry.READING_TOPICS)


@pytest.mark.parametrize("topic", list(tool_registry.READING_TOPICS))
def test_every_topic_returns_a_grounded_reading(topic):
    r = tool_registry.dispatch("get_reading_context", {"topic": topic},
                               dict(CHART1), current_tz=5.5)
    assert "error" not in r, r
    assert len(r["natal"]["planets"]) == 9
    assert r["natal"]["lagna"]["sign_name"]
    houses = [f["house"] for f in r["focus_houses"]]
    assert houses == tool_registry.READING_TOPICS[topic][0]
    for f in r["focus_houses"]:
        # The lord's own natal house must be stated, not left to arithmetic.
        assert f["lord"] and f["lord_sits_in"]["house"] in range(1, 13), f
    want = {"D9", f"D{tool_registry.READING_TOPICS[topic][1]}"}
    assert set(r["vargas"]) == want, r["vargas"].keys()
    for code, v in r["vargas"].items():
        assert v.get("lagna") and v.get("planets"), code
    assert r["dasha"]["chain"], "no running dasha"
    assert r["transits"]["planets"]


def test_reading_context_reads_a_past_date():
    r = tool_registry.dispatch("get_reading_context",
                               {"topic": "career", "date": "2020-06-15"}, dict(CHART1))
    assert r["as_of"] == "2020-06-15" and r["is_past"] is True
    assert r["transits"]["date"] == "2020-06-15"
    maha = r["dasha"]["mahadasha"]
    assert maha["start_date"] <= "2020-06-15" <= maha["end_date"]
    if r["saturn_phase_from_moon"]:
        assert "is_current" not in r["saturn_phase_from_moon"]


def test_reading_context_rejects_unknown_topic_and_bad_date():
    with pytest.raises(tool_registry.ToolError):
        tool_registry.dispatch("get_reading_context", {"topic": "love"}, dict(CHART1))
    with pytest.raises(tool_registry.ToolError):
        tool_registry.dispatch("get_reading_context", {"date": "2026/01/01"}, dict(CHART1))


def test_transits_accept_a_date():
    r = tool_registry.dispatch("get_transits", {"date": "2026-03-01"}, dict(CHART1))
    assert r["transit_date"] == "2026-03-01"


def test_upcoming_events_accept_a_past_window():
    r = tool_registry.dispatch("get_upcoming_events",
                               {"from_date": "2026-01-01", "months": 12}, dict(CHART1))
    assert r["from_date"] == "2026-01-01"
    assert r["events"], "a year of a chart's events can't be empty"


def test_life_timeline_next_lists_hold_no_past_dates():
    r = tool_registry.dispatch("get_life_timeline", {}, dict(CHART1), current_tz=5.5)
    today = r["as_of"]
    assert all(i["date"] >= today for i in r["next_ingresses"]), r["next_ingresses"]
    assert all(e["date"] >= today for e in r["upcoming_eclipses"])


@pytest.mark.parametrize("name,args", [
    ("get_upcoming_events", {}),
    ("get_transits", {}),
    ("get_life_timeline", {}),
])
def test_timing_only_results_point_back_to_the_foundation(name, args):
    """A small hosted model (Haiku) answered 'how is my next year' from the
    event list alone even with the instructions in place — so the results
    themselves say they are timing only."""
    r = tool_registry.dispatch(name, args, dict(CHART1), current_tz=5.5)
    assert "get_reading_context" in r.get("note", ""), r.keys()


def test_no_timing_tool_advertises_itself_as_a_whole_forecast():
    for name in ("get_upcoming_events", "get_varshaphal"):
        desc = tool_registry.TOOLS[name].description
        assert "get_reading_context" in desc, name
        assert "what should I watch for this year" not in desc
