"""Every chart payload the LLM sees must speak in bhavas, not sign numbers.

The compute layer's `rasi` (0-based sign) and `house` (that + 1, the sign cell a
Kundali is drawn in) are renderer fields. Shipped to a model they read as house
numbers and outrank the truth: the owner's D9 Sun in Cancer arrived as
`{"rasi": 3, "house": 4}` and every reading placed it in the 4th, not the 12th
from the Navamsa Leo lagna.

These tests pin the AI boundary — `tools.dispatch`, `chart_context` and the
prompt-facing `get_horoscope_predictions` — as houses-from-the-lagna only.
"""
import pytest

from astrology import AstrologyCompute, chart_positions
import chart_context
import tools

from .conftest import CHART1, _compute_args

AYAN = "TRUE_CITRA"
BD1 = {"dob": CHART1["dob"], "tob": CHART1["tob"], "place": CHART1["place"],
       "latitude": CHART1["latitude"], "longitude": CHART1["longitude"],
       "timezone": CHART1["timezone"]}


def _layout_keys(node, path="$"):
    """Every place a drawing-only sign number survived into an LLM payload."""
    found = []
    if isinstance(node, dict):
        if "rasi" in node:
            found.append(f"{path}.rasi")
        for k, v in node.items():
            found += _layout_keys(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            found += _layout_keys(v, f"{path}[{i}]")
    return found


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


@pytest.mark.parametrize("tool,args", [
    ("get_natal_chart", {}),
    ("get_divisional_chart", {"varga_factor": 9}),
    ("get_divisional_chart", {"varga_factor": 10}),
    ("get_transits", {}),
    ("get_varshaphal", {"year": 2026}),
])
def test_no_tool_ships_a_sign_index_to_the_model(tool, args):
    out = tools.dispatch(tool, args, BD1, AYAN)
    assert not _layout_keys(out), _layout_keys(out)


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
