"""Who rules which house — stated, not left to the model's priors.

A Life Report chapter on dharma told the owner "the 9th house of fortune and
dharma is ruled by Jupiter, placed in the 12th in Aries". Jupiter *is* in the
12th in Aries, and Jupiter *is* the natural karaka of dharma — but with a Taurus
lagna the 9th is Capricorn, so its lord is Saturn, and Jupiter rules the 8th and
11th. The reading then built a chapter on the wrong ruler (§67).

The lordships were in the context all along, rendered as `- L9 in H3 (Saturn)`
under twenty yoga definitions. Correct data, and the model's prior beat it.
"""
import pytest

from astrology import AstrologyCompute
import chart_context
from llm.prompts import PromptsMixin

from .conftest import CHART1, _compute_args

AYAN = "TRUE_CITRA"
BD1 = {"dob": CHART1["dob"], "tob": CHART1["tob"], "place": CHART1["place"],
       "latitude": CHART1["latitude"], "longitude": CHART1["longitude"],
       "timezone": CHART1["timezone"]}


class _Prompts(PromptsMixin):
    pass


@pytest.fixture(scope="module")
def ctx():
    return chart_context.build_chart_context(BD1, ayanamsa=AYAN)


def test_house_rulers_match_the_engine(ctx):
    """Derived from the lagna here; computed independently by get_friendships."""
    engine = {h["house"]: h["lord"]
              for h in AstrologyCompute.get_friendships(
                  ayanamsa=AYAN, **_compute_args(CHART1))["house_lords"]}
    seeded = {r["house"]: r["lord"] for r in ctx["house_rulers"]}
    assert seeded == engine
    # The owner's chart, pinned: Taurus lagna.
    assert seeded[9] == "Saturn"
    assert seeded[8] == seeded[11] == "Jupiter"


def test_rulers_are_seeded_even_with_every_section_off():
    """A house's lord costs one line and no compute call, so it is never a
    section the caller can switch off and leave the model guessing."""
    bare = chart_context.build_chart_context(
        BD1, ayanamsa=AYAN,
        sections={k: False for k in chart_context.DEFAULT_SECTIONS})
    assert bare["house_rulers"][8] == {"house": 9, "sign": "Capricorn", "lord": "Saturn"}


def test_the_prompt_names_the_ninth_lord_and_pre_empts_the_karaka_slip(ctx):
    text = _Prompts()._render_context_block(ctx)
    assert "9th Capricorn: Saturn" in text
    assert "8th Sagittarius: Jupiter" in text
    # The correction is chart-specific, so it contradicts the wrong answer
    # outright rather than warning in the abstract.
    assert "the 9th lord HERE is Saturn" in text
    assert "Jupiter rules the 8th and 11th" in text
    assert "never from a planet's natural karaka-ship" in text


def test_house_lords_read_as_english_not_shorthand(ctx):
    """`L9 in H3 (Saturn)` is a dialect the model has to decode."""
    text = _Prompts()._render_context_block(ctx)
    assert "9th lord is Saturn, in the 3rd" in text
    assert "L9 in H3" not in text


def test_rulers_follow_the_lagna_not_aries():
    """Regression on the derivation itself: it reads the LLM-facing lagna, whose
    `sign_num` is stripped (§65), so it must resolve the sign by name. Reading
    `sign_num` produced an Aries table for every chart."""
    from chart_context import _house_rulers
    assert _house_rulers({"sign_name": "Taurus", "house": 1})[0]["sign"] == "Taurus"
    assert _house_rulers({"sign_name": "Scorpio"})[0]["lord"] == "Mars"
