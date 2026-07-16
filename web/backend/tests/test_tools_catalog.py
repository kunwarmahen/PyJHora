"""The AI tool catalog is a contract (§8.9 / §2.3).

It backs three consumers at once: the Ask page's smart-lookup mode, the read-only
public API (`GET /api/v1/tools`), and the MCP server, which registers whatever the
catalog reports. So a tool that is registered but undescribed — or a handler that
raises on a plain call — degrades all three at once, silently.

These are cheap structural checks, not behaviour tests (the golden tests cover the
computes themselves).
"""
import pytest

import tools as tool_registry
from tests.conftest import CHART1


def test_every_tool_has_display_metadata():
    """No tool may fall through to the 'Other' bucket — the AI Capabilities page
    and the MCP client both group by category."""
    catalog = tool_registry.tool_catalog()
    assert len(catalog) == len(tool_registry.TOOLS)
    uncategorised = [t["name"] for t in catalog if t["category"] == "Other"]
    assert not uncategorised, f"tools missing _DISPLAY metadata: {uncategorised}"
    for t in catalog:
        assert t["description"].strip(), f"{t['name']} has no model-facing description"
        assert t["parameters"].get("type") == "object", f"{t['name']} has a bad schema"


def test_always_tools_all_exist():
    unknown = [n for n in tool_registry.ALWAYS_TOOLS if n not in tool_registry.TOOLS]
    assert not unknown, f"ALWAYS_TOOLS names unknown tools: {unknown}"


def test_section_tools_all_exist():
    unknown = [t for t in tool_registry.SECTION_TOOL.values()
               if t not in tool_registry.TOOLS]
    assert not unknown, f"SECTION_TOOL names unknown tools: {unknown}"


@pytest.mark.parametrize("name,args", [
    ("get_sarvatobhadra_chakra", {"current_date": "2026-07-16"}),
    ("get_kota_chakra", {"current_date": "2026-07-16"}),
    ("get_kaala_chakra", {"current_date": "2026-07-16"}),
    ("get_tripataki_chakra", {"basis": "annual", "year": 2026}),
    ("get_dasha_periods", {"dhasa_type": "sudharsana_chakra"}),
])
def test_session_tools_dispatch(name, args):
    """Every tool added for the chakras + alternate dashas actually runs."""
    r = tool_registry.dispatch(name, args, dict(CHART1))
    assert "error" not in r, r


def test_kaala_tool_reports_directions():
    r = tool_registry.dispatch("get_kaala_chakra", {"current_date": "2026-07-16"},
                               dict(CHART1))
    assert [d["direction"] for d in r["directions"]] == [
        "Southeast", "East", "Northeast", "North",
        "Northwest", "West", "Southwest", "South"]
    assert r["base_star"] == "Rohini"


def test_dasha_periods_tool_requires_a_known_system():
    with pytest.raises(tool_registry.ToolError) as e:
        tool_registry.dispatch("get_dasha_periods", {}, dict(CHART1))
    # The error must list the choices, else the model can't recover.
    assert "sudharsana_chakra" in str(e.value)
    with pytest.raises(tool_registry.ToolError):
        tool_registry.dispatch("get_dasha_periods", {"dhasa_type": "nope"}, dict(CHART1))


def test_dasha_periods_tool_truncates_the_long_wheel():
    """Sudarshana runs to 108 one-year rows; the tool must cap them but still say
    so and still surface the running period."""
    r = tool_registry.dispatch("get_dasha_periods",
                               {"dhasa_type": "sudharsana_chakra"}, dict(CHART1))
    assert r["total_periods"] == 108
    assert len(r["periods"]) == 24
    assert r["current"] is not None
    assert r["lord_type"] == "chakra"


def test_every_section_reaches_the_model():
    """A context section must survive the whole chain: DEFAULT_SECTIONS -> a
    builder block -> the rendered prompt the model actually reads.

    This caught a real gap: the chakra sections were added to DEFAULT_SECTIONS and
    built into the context, but `_render_context_block` never emitted them — so
    the Ask-page chip would have been a no-op and the model would never have seen
    the data. Structural, so it can't rot silently again.
    """
    from chart_context import build_chart_context, DEFAULT_SECTIONS
    from llm_service import llm_service

    # Sections whose payload is genuinely rendered elsewhere (the natal base is
    # always present, not a toggle) would go here; today every toggle renders.
    on = {k: True for k in DEFAULT_SECTIONS}
    ctx = build_chart_context(dict(CHART1), sections=on)
    block = llm_service._render_context_block(ctx)

    # Each section that produced context must show up in the rendered block.
    markers = {
        "sarvatobhadra": "Sarvatobhadra Chakra",
        "kota": "Kota Chakra",
        "kaala": "Kaala Chakra",
        "tripataki": "Tripataki Chakra",
    }
    for section, marker in markers.items():
        assert section in ctx, f"{section} produced no context block"
        assert marker in block, (
            f"{section} is built into the context but never rendered into the "
            f"prompt — the model would never see it")


def test_section_tool_covers_every_toggleable_section():
    """Every section chip must have a tool behind it, or Smart-lookup mode can't
    fetch it when the user sets the chip to 'tool'."""
    from chart_context import DEFAULT_SECTIONS

    missing = [s for s in DEFAULT_SECTIONS if s not in tool_registry.SECTION_TOOL]
    assert not missing, f"sections with no tool: {missing}"
