"""The prompt is right for *every* lagna, not just the owner's (§68.1).

`test_house_rulers.py` guards one fact for one chart. That is how §67's own fix
shipped with a bug in it: an early cut derived the ruler table from `sign_num`
(a drawing coordinate, §65) and produced an **Aries table for every chart** —
wrong-looking-plausible for exactly one lagna in twelve, and structurally
invisible to a single-chart test.

So this sweeps all twelve. One date and place, twelve birth times, one per
ascending sign; for each chart it asserts that

  1. the context's ruler table matches a *different* compute call (get_friendships),
  2. the rendered prompt states those lordships in English,
  3. every planet's house is the whole-sign count from that chart's own lagna,
  4. the claim checker reads its own facts back out of the finished prompt, and
  5. a reading built from the true facts passes while one built from the *next*
     lagna's facts is caught — which is precisely the Aries-table failure.

Test the class, not the instance: the parametrization is the point.
"""
import pytest

import chart_context
import claim_check as cc
from astrology import (AstrologyCompute, RASI_LORDS, ZODIAC_NAMES, chart_positions,
                       sign_index)
from llm.prompts import PromptsMixin

AYAN = "TRUE_CITRA"

# One birth per ascending sign — same date and place, so the lagna is the only
# thing that moves. Derived by sweeping the day and keeping the first time that
# rose in each sign; pinned here so the suite needs no search at run time.
LAGNA_TIMES = {
    "Aries": "12:05:00", "Taurus": "14:05:00", "Gemini": "16:05:00",
    "Cancer": "18:05:00", "Leo": "20:05:00", "Virgo": "00:05:00",
    "Libra": "00:35:00", "Scorpio": "02:35:00", "Sagittarius": "04:35:00",
    "Capricorn": "07:05:00", "Aquarius": "08:35:00", "Pisces": "10:35:00",
}
BASE = {"dob": "1990-01-15", "place": "Chennai",
        "latitude": 13.0827, "longitude": 80.2707, "timezone": 5.5}
# Every section off: house rulers are seeded unconditionally, and the twelve
# charts should not each pay for a dasha tree and a transit scan.
BARE = {k: False for k in chart_context.DEFAULT_SECTIONS}


class _Prompts(PromptsMixin):
    pass


def _birth(sign):
    return {**BASE, "tob": LAGNA_TIMES[sign]}


def _args(sign):
    b = _birth(sign)
    return {"dob": b["dob"], "tob": b["tob"], "place": b["place"],
            "lat": b["latitude"], "lon": b["longitude"], "tz": b["timezone"]}


@pytest.fixture(scope="module")
def charts():
    """{sign: (context, rendered prompt block)} for all twelve lagnas."""
    out = {}
    for sign in LAGNA_TIMES:
        ctx = chart_context.build_chart_context(_birth(sign), ayanamsa=AYAN,
                                                sections=dict(BARE), vargas=[1])
        out[sign] = (ctx, _Prompts()._render_context_block(ctx))
    return out


ALL_SIGNS = list(LAGNA_TIMES)


def test_the_twelve_charts_really_are_twelve_lagnas(charts):
    """If the fixture ever drifts onto one lagna, every test below passes for the
    wrong reason."""
    got = {sign: ctx["lagna"]["sign_name"] for sign, (ctx, _) in charts.items()}
    assert got == {s: s for s in ALL_SIGNS}


@pytest.mark.parametrize("sign", ALL_SIGNS)
def test_rulers_match_an_independent_compute(sign, charts):
    ctx, _ = charts[sign]
    engine = {h["house"]: h["lord"]
              for h in AstrologyCompute.get_friendships(ayanamsa=AYAN, **_args(sign))
              ["house_lords"]}
    seeded = {r["house"]: r["lord"] for r in ctx["house_rulers"]}
    assert seeded == engine
    # And derived from *this* lagna, not from Aries.
    asc = ZODIAC_NAMES.index(sign)
    assert seeded == {i + 1: RASI_LORDS[(asc + i) % 12] for i in range(12)}


@pytest.mark.parametrize("sign", ALL_SIGNS)
def test_the_prompt_states_every_lordship_in_english(sign, charts):
    ctx, text = charts[sign]
    for row in ctx["house_rulers"]:
        assert f"{cc.ordinal(row['house'])} {row['sign']}: {row['lord']}" in text
    assert "L9 in H3" not in text        # the shorthand §67 replaced
    ninth = ctx["house_rulers"][8]
    assert f"the 9th lord HERE is {ninth['lord']}" in text


@pytest.mark.parametrize("sign", ALL_SIGNS)
def test_every_planet_house_is_the_whole_sign_count(sign, charts):
    """The §63/§65 failure: a sign number rendered under the word "house"."""
    ctx, text = charts[sign]
    asc = ZODIAC_NAMES.index(ctx["lagna"]["sign_name"])
    for name, pos in ctx["planetary_positions"].items():
        expected = ((ZODIAC_NAMES.index(pos["sign_name"]) - asc) % 12) + 1
        assert pos["house"] == expected, f"{sign} lagna: {name}"
        assert "sign_num" not in pos and "rasi" not in pos
        assert f"{name}: {pos['sign_name']}" in text


@pytest.mark.parametrize("sign", ALL_SIGNS)
def test_the_checker_reads_back_what_the_prompt_says(sign, charts):
    """Facts and prompt come from one context, so a contradiction the checker
    reports is genuinely the model denying what it was told."""
    ctx, _ = charts[sign]
    facts = cc.build_facts(ctx)
    lagna = chart_positions(ctx["lagna"], {})["lagna"]
    assert facts.planet_sign["Lagna"] == lagna["sign_name"]
    assert len(facts.house_lord) == 12
    assert facts.house_sign[1] == sign


def _reading(facts):
    """A reading that states this chart's facts, in the phrasings models use."""
    lines = [f"The Ascendant is {facts.planet_sign['Lagna']}."]
    for planet, house in sorted(facts.planet_house.items()):
        if planet == "Lagna":
            continue
        lines.append(f"{planet} is in the {cc.ordinal(house)} house, "
                     f"in {facts.planet_sign[planet]}.")
    for house in range(1, 13):
        lines.append(f"The {cc.ordinal(house)} lord is {facts.house_lord[house]}, "
                     f"and the {cc.ordinal(house)} house is {facts.house_sign[house]}.")
    return "\n".join(lines)


@pytest.mark.parametrize("sign", ALL_SIGNS)
def test_a_true_reading_passes_for_every_lagna(sign, charts):
    """~30 checkable claims per chart, ~360 across the sweep, none flagged."""
    facts = cc.build_facts(charts[sign][0])
    report = cc.check(_reading(facts), facts)
    assert report["contradictions"] == [], f"{sign} lagna: {report['contradictions']}"
    assert report["checked"] >= 30, "the corpus stopped being checkable"


@pytest.mark.parametrize("sign", ALL_SIGNS)
def test_another_lagnas_reading_is_caught(sign, charts):
    """The Aries-table bug, generalized: a reading correct for a *different*
    ascendant must not pass here. A single-chart test cannot see this."""
    other = ALL_SIGNS[(ALL_SIGNS.index(sign) + 1) % 12]
    facts = cc.build_facts(charts[sign][0])
    wrong = _reading(cc.build_facts(charts[other][0]))
    found = cc.check(wrong, facts)["contradictions"]
    assert found, f"{sign} lagna accepted a reading written for {other}"
    assert {c["kind"] for c in found} >= {"lordship", "placement_house"}
