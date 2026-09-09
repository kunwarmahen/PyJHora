"""Every chart payload the LLM sees must speak in bhavas, not sign numbers.

The compute layer's `rasi` (0-based sign) and `house` (that + 1, the sign cell a
Kundali is drawn in) are renderer fields. Shipped to a model they read as house
numbers and outrank the truth: the owner's D9 Sun in Cancer arrived as
`{"rasi": 3, "house": 4}` and every reading placed it in the 4th, not the 12th
from the Navamsa Leo lagna.

These tests pin the AI boundary — `tools.dispatch`, `chart_context` and the
prompt-facing `get_horoscope_predictions` — as houses-from-the-lagna only.
"""
import re

import pytest

from astrology import AstrologyCompute, ZODIAC_NAMES, chart_positions, sanitize
import chart_context
import llm_service
import tools

from .conftest import CHART1, _compute_args

AYAN = "TRUE_CITRA"
BD1 = {"dob": CHART1["dob"], "tob": CHART1["tob"], "place": CHART1["place"],
       "latitude": CHART1["latitude"], "longitude": CHART1["longitude"],
       "timezone": CHART1["timezone"]}


def _layout_keys(node, path="$"):
    """Every place a sign index survived into an LLM payload.

    `rasi` anywhere, and a bare integer `sign` / `*_sign` whose own `*_name`
    sibling already spells the sign out — the latter is 0-based in most payloads
    and 1-based in the arudhas, so it is unreadable even in principle.
    """
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            is_int = isinstance(v, int) and not isinstance(v, bool)
            named = ("sign_name" in node if k == "sign" else f"{k}_name" in node)
            if k == "rasi" and is_int:
                found.append(f"{path}.rasi")
            elif is_int and (k == "sign" or k.endswith("_sign")) and named:
                found.append(f"{path}.{k}")
            found += _layout_keys(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += _layout_keys(v, f"{path}[{i}]")
    return found


def _sample_args(tool):
    """Fill a tool's required params from its own schema, so every tool runs."""
    args = {}
    spec = tool.parameters or {}
    props = spec.get("properties", {})
    for name in spec.get("required", []):
        p = props.get(name, {})
        if "enum" in p:
            args[name] = p["enum"][0]
        elif p.get("type") == "integer":
            args[name] = 2026 if "year" in name else 9
        elif p.get("type") == "array":
            args[name] = ["Venus"]
        else:
            args[name] = "Venus"
    # Handlers that require an argument the schema marks optional.
    args.update({"get_dasha_periods": {"dhasa_type": "ashtottari"}}.get(tool.name, {}))
    return args


# ── the helper itself ───────────────────────────────────────────────────────
def test_chart_positions_counts_from_the_lagna():
    view = chart_positions(
        {"rasi": 4, "house": 5, "sign_name": "Leo", "degrees": 15.56},
        {"Sun": {"rasi": 3, "house": 4, "sign_name": "Cancer", "degrees": 0.03},
         "Moon": {"rasi": 0, "house": 1, "sign_name": "Aries", "degrees": 6.78},
         "Saturn": {"rasi": 4, "house": 5, "sign_name": "Leo", "degrees": 27.3}},
    )
    assert view["lagna"]["house"] == 1
    assert view["planets"]["Sun"]["house"] == 12      # Cancer, 12th from Leo
    assert view["planets"]["Moon"]["house"] == 9      # Aries, 9th from Leo
    assert view["planets"]["Saturn"]["house"] == 1    # with the lagna
    assert "Leo" in view["house_system"]
    # The renderer's numbers are gone, the readable ones stay.
    for pos in [view["lagna"]] + list(view["planets"].values()):
        assert "rasi" not in pos
        assert set(pos) >= {"sign_name", "degrees", "house"}


def test_chart_positions_survives_a_lagna_without_rasi():
    """Payloads that carry only the 1-based `house` (varga lagnas) still count."""
    view = chart_positions({"house": 5, "sign_name": "Leo"},
                           {"Sun": {"house": 4, "sign_name": "Cancer"}})
    assert view["planets"]["Sun"]["house"] == 12


# ── the AI boundary ─────────────────────────────────────────────────────────
def test_navamsa_tool_gives_houses_from_the_navamsa_lagna():
    d9 = tools.dispatch("get_divisional_chart", {"varga_factor": 9}, BD1, AYAN)
    assert d9["lagna"]["sign_name"] == "Leo"
    assert d9["lagna"]["house"] == 1
    assert d9["planets"]["Sun"] == {"degrees": 0.03, "sign_name": "Cancer", "house": 12}
    assert d9["planets"]["Moon"]["house"] == 9
    assert not _layout_keys(d9), _layout_keys(d9)


def test_natal_tool_gives_houses_from_the_lagna():
    natal = tools.dispatch("get_natal_chart", {}, BD1, AYAN)
    lagna_sign = natal["lagna"]["sign_name"]
    assert natal["lagna"]["house"] == 1
    assert lagna_sign in natal["house_system"]
    # The Moon's house agrees with the sign count from the lagna.
    from astrology import ZODIAC_NAMES
    moon = natal["planetary_positions"]["Moon"]
    expected = ((ZODIAC_NAMES.index(moon["sign_name"])
                 - ZODIAC_NAMES.index(lagna_sign)) % 12) + 1
    assert moon["house"] == expected == natal["moon_sign"]["house"]
    assert not _layout_keys(natal), _layout_keys(natal)


@pytest.mark.parametrize("name", sorted(tools.TOOLS))
def test_no_tool_ships_a_sign_index_to_the_model(name):
    """The sweep, not a list I curated: every tool, run for real and walked.

    `dispatch` sanitizes on the way out, so this also covers tools written after
    this test — which is the point. It fails on a handler that invents a new key
    holding a sign index next to its own name.
    """
    out = tools.dispatch(name, _sample_args(tools.TOOLS[name]), BD1, AYAN)
    assert not _layout_keys(out), _layout_keys(out)


@pytest.mark.parametrize("varga", [2, 3, 4, 7, 9, 10, 12, 16, 20, 24, 27, 30, 40, 45, 60])
def test_every_divisional_chart_counts_its_own_houses(varga):
    """Not a D9 problem — every varga went out with sign numbers for houses."""
    d = tools.dispatch("get_divisional_chart", {"varga_factor": varga}, BD1, AYAN)
    asc = ZODIAC_NAMES.index(d["lagna"]["sign_name"])
    assert d["lagna"]["house"] == 1
    for name, p in d["planets"].items():
        expected = ((ZODIAC_NAMES.index(p["sign_name"]) - asc) % 12) + 1
        assert p["house"] == expected, f"D{varga} {name}"


def test_sanitize_keeps_real_houses_and_sign_names():
    """It must only take the ambiguous integers — never a bhava or a name."""
    clean = sanitize({
        "sphutas": [{"name": "Prana", "sign": 8, "sign_name": "Sagittarius",
                     "house": 8, "degrees": 3.2}],
        "lagna_sign": 1, "lagna_sign_name": "Taurus",
        "moon_sign": "Leo",                       # a name, not an index
        "vedha": [{"target": "Rohini", "sign": "Taurus"}],
        "flags": {"combust": True},               # bools are not sign indices
    })
    assert clean["sphutas"][0] == {"name": "Prana", "sign_name": "Sagittarius",
                                   "house": 8, "degrees": 3.2}
    assert "lagna_sign" not in clean and clean["lagna_sign_name"] == "Taurus"
    assert clean["moon_sign"] == "Leo"
    assert clean["vedha"][0]["sign"] == "Taurus"
    assert clean["flags"] == {"combust": True}


def test_transits_keep_their_own_house_counts():
    """Stripping the layout keys must not take house_from_lagna with it."""
    t = tools.dispatch("get_transits", {}, BD1, AYAN)
    saturn = t["planets"]["Saturn"]
    assert "house" not in saturn          # was the sign number
    assert 1 <= saturn["house_from_lagna"] <= 12
    assert 1 <= saturn["house_from_moon"] <= 12


def test_seeded_context_matches_the_tool_payloads():
    ctx = chart_context.build_chart_context(
        BD1, sections={k: False for k in chart_context.DEFAULT_SECTIONS},
        vargas=[1, 9], ayanamsa=AYAN)
    assert ctx["lagna"]["house"] == 1
    assert ctx["planetary_positions"]["Moon"]["house"] == ctx["moon_sign"]["house"]
    d9 = next(v for v in ctx["vargas"] if v["varga"] == 9)
    assert d9["planets"]["Sun"]["house"] == 12
    assert not _layout_keys(ctx["vargas"]), _layout_keys(ctx["vargas"])


def test_prediction_summary_is_house_counted():
    """get_horoscope_predictions feeds the compatibility/compare prompts."""
    p = AstrologyCompute.get_horoscope_predictions(
        ayanamsa=AYAN, **_compute_args(CHART1))
    assert p["lagna"]["house"] == 1
    assert p["sun_sign"]["house"] == p["planetary_positions"]["Sun"]["house"]
    assert not _layout_keys(p), _layout_keys(p)


# ── the prompt surface (readings that never touch tools.py) ─────────────────
def _houses_in(text):
    """[(planet, sign, house)] from a prompt's planet lines."""
    return re.findall(r"- (\w+): (\w+)[^\n]*?house (\d+)", text)


def test_chart_of_the_moment_prompt_counts_from_its_ascendant():
    """This reading is built straight from the compute payload, whose `planets`
    are the renderer's set — it was printing the sign cell as the bhava."""
    d = AstrologyCompute.get_now_chart(
        place=CHART1["place"], lat=CHART1["latitude"], lon=CHART1["longitude"],
        tz=CHART1["timezone"], current_time="2026-09-09 12:00", ayanamsa=AYAN)
    text = llm_service.LLMService()._build_now_chart_prompt(d)
    asc = ZODIAC_NAMES.index(d["lagna"]["sign_name"])
    rows = _houses_in(text)
    assert len(rows) == 9
    for planet, sign, house in rows:
        assert int(house) == ((ZODIAC_NAMES.index(sign) - asc) % 12) + 1, planet


def test_varshaphal_prompt_counts_from_the_annual_ascendant():
    v = AstrologyCompute.get_varshaphal(year=2026, ayanamsa=AYAN, **_compute_args(CHART1))
    text = llm_service.LLMService()._build_varshaphal_prompt(v, "Owner")
    asc = ZODIAC_NAMES.index(v["lagna"]["sign_name"])
    found = re.findall(r"(\w+): (\w+) \(house (\d+)\)", text)
    assert len(found) >= 9
    for planet, sign, house in found:
        if sign in ZODIAC_NAMES:
            assert int(house) == ((ZODIAC_NAMES.index(sign) - asc) % 12) + 1, planet
