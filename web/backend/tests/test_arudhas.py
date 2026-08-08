"""Golden + structural tests for the enriched bhava-arudha analysis.

`get_arudha_padas` only ever answered "which sign is AL in?". `get_arudha_analysis`
adds the structure a reading needs — lord, occupants, rasi drishti, and the houses
counted *from* AL/UL — so these tests pin both the values and the arithmetic that
derives them, plus the prompt's handling of the user's arudha selection.

Chart 1 is the JHora-verified reference chart from conftest.
"""
import re

import pytest

from astrology import AstrologyCompute as A
from astrology.compute_digests import _ordinal
from llm_service import llm_service

# ── Golden arudha placements for chart 1 (1976-06-04 05:45:02, Aligarh) ──────
CHART1_ARUDHA_SIGNS = {
    "AL": "Aquarius", "A2": "Aries", "A3": "Virgo", "A4": "Scorpio",
    "A5": "Capricorn", "A6": "Sagittarius", "A7": "Virgo", "A8": "Leo",
    "A9": "Libra", "A10": "Sagittarius", "A11": "Taurus", "UL": "Cancer",
}
# AL is Aquarius, so the houses read from it run Pisces → Scorpio → Sag → Capricorn.
CHART1_AL_DERIVED = {2: "Pisces", 10: "Scorpio", 11: "Sagittarius", 12: "Capricorn"}
CHART1_UL_DERIVED = {2: "Leo", 7: "Capricorn"}


@pytest.fixture
def arudha1(args1):
    r = A.get_arudha_analysis(**args1)
    assert r["status"] == "success", r.get("error")
    return r


def test_arudha_signs_pinned(arudha1):
    got = {a["short"]: a["sign_name"] for a in arudha1["arudhas"]}
    assert got == CHART1_ARUDHA_SIGNS


def test_enrichment_agrees_with_the_plain_pada_call(args1, arudha1):
    """The enriched call must not drift from the one the chart cells already use."""
    plain = A.get_arudha_padas(**args1)
    assert plain["status"] == "success"
    assert {p["short"]: p["sign_name"] for p in plain["arudha_padas"]} == \
           {a["short"]: a["sign_name"] for a in arudha1["arudhas"]}


def test_al_derived_houses(arudha1):
    assert {d["house_from_al"]: d["sign_name"] for d in arudha1["al_derived"]} == CHART1_AL_DERIVED


def test_ul_derived_houses(arudha1):
    assert {d["house_from_ul"]: d["sign_name"] for d in arudha1["ul_derived"]} == CHART1_UL_DERIVED


def test_derived_houses_are_counted_from_their_arudha_not_the_lagna(arudha1):
    """The bug this guards: deriving 'the 12th from AL' off the Lagna instead of AL."""
    by_short = {a["short"]: a for a in arudha1["arudhas"]}
    al = by_short["AL"]["sign"] - 1
    ul = by_short["UL"]["sign"] - 1
    for d in arudha1["al_derived"]:
        assert (d["sign"] - 1) == (al + d["house_from_al"] - 1) % 12
    for d in arudha1["ul_derived"]:
        assert (d["sign"] - 1) == (ul + d["house_from_ul"] - 1) % 12


def test_house_from_lagna_is_consistent(arudha1):
    lagna = arudha1["lagna"]["sign"] - 1
    for a in arudha1["arudhas"]:
        assert a["house_from_lagna"] == ((a["sign"] - 1 - lagna) % 12) + 1


def test_every_arudha_carries_the_reading_fields(arudha1):
    for a in arudha1["arudhas"]:
        assert a["lord"], a
        assert isinstance(a["occupants"], list)
        assert isinstance(a["aspecting_planets"], list)
        assert 1 <= a["lord_house_from_arudha"] <= 12


def test_occupants_match_the_lord_placement(arudha1):
    """A11 falls in Taurus and Venus (its lord) sits in Taurus — so the lord must
    be counted as the 1st from its own arudha and appear among the occupants."""
    a11 = next(a for a in arudha1["arudhas"] if a["short"] == "A11")
    assert a11["lord"] == "Venus"
    assert a11["lord_house_from_arudha"] == 1
    assert "Venus" in a11["occupants"]


# ── Prompt: the selection is the user's, and only it gets read ───────────────
def test_prompt_reads_only_the_selected_arudhas(arudha1):
    p = llm_service._build_arudha_prompt(arudha1, "Tester", ["AL", "A10"])
    assert "AL (Arudha Lagna)" in p
    assert "A10" in p
    assert "UL (Upapada)" not in p
    # AL was picked, so its derived houses ride along; UL's must not.
    assert "from the Arudha Lagna" in p
    assert "from the Upapada" not in p


def test_prompt_defaults_when_nothing_selected(arudha1):
    for sel in (None, []):
        p = llm_service._build_arudha_prompt(arudha1, "Tester", sel)
        for short in ("AL (Arudha Lagna)", "UL (Upapada)", "A10", "A11"):
            assert short in p


def test_prompt_ignores_unknown_codes(arudha1):
    """Client-supplied codes are filtered against the known set, never interpolated raw."""
    p = llm_service._build_arudha_prompt(arudha1, "Tester", ["A99", "<script>"])
    assert "A99" not in p
    assert "<script>" not in p
    assert "AL (Arudha Lagna)" in p   # falls back rather than emitting an empty reading


def test_prompt_uses_correct_ordinals(arudha1):
    p = llm_service._build_arudha_prompt(arudha1, "Tester", ["AL"])
    assert "2nd from it" in p
    assert "12th from it" in p
    assert "10th from it" in p
    assert " 2th" not in p   # leading space: "12th" legitimately ends in "2th"
    assert " 1th" not in p


# ── The arudha frame inside get_transits (§60) ───────────────────────────────
#
# The gochara reading counts each transiting graha from the natal arudhas as
# well as the Lagna and the Moon. These pin the *class* of thing that can break:
# the join being silently absent, and the arithmetic disagreeing with the padas
# it claims to be counted from.

def test_transits_carry_every_arudha_reference(args1):
    """Each transiting graha is counted from all twelve padas, and the named
    AL/UL shortcuts agree with the map they summarize."""
    tr = A.get_transits(**args1, current_date="2026-08-07")
    assert tr["status"] == "success", tr
    padas = tr["arudhas"]["padas"]
    # The same twelve arudhas the natal analysis reports, in the same signs —
    # arudhas are natal points, so a transit date must not move them.
    assert {p["short"]: p["sign_name"] for p in padas} == CHART1_ARUDHA_SIGNS
    assert tr["arudhas"]["al"]["sign_name"] == "Aquarius"
    assert tr["arudhas"]["ul"]["sign_name"] == "Cancer"

    by_short = {p["short"]: p["sign"] - 1 for p in padas}
    for name, p in tr["planets"].items():
        houses = p["house_from_padas"]
        assert set(houses) == set(CHART1_ARUDHA_SIGNS), name
        for short, h in houses.items():
            # Counted inclusively from the arudha's sign to the graha's sign.
            assert h == ((p["rasi"] - by_short[short]) % 12) + 1, f"{name} {short}"
        # The two named columns are the map's AL/UL entries, not a second sum.
        assert p["house_from_al"] == houses["AL"], name
        assert p["house_from_ul"] == houses["UL"], name


def test_transit_arudha_significations_come_from_the_one_table(args1):
    """The classical meanings shipped with the transits are the same table the
    natal arudha analysis derives its houses from — two copies would drift."""
    from astrology.engine import AL_HOUSE_SIGNIFICATIONS, UL_HOUSE_SIGNIFICATIONS

    tr = A.get_transits(**args1, current_date="2026-08-07")
    sig = tr["arudhas"]["significations"]
    assert sig["AL"] is AL_HOUSE_SIGNIFICATIONS
    assert sig["UL"] is UL_HOUSE_SIGNIFICATIONS

    # Every house the natal analysis describes must have its meaning here, so a
    # reading can name the same house whether it arrives via natal or transit.
    an = A.get_arudha_analysis(**args1)
    for row in an["al_derived"]:
        assert row["signifies"] == AL_HOUSE_SIGNIFICATIONS[row["house_from_al"]]
    for row in an["ul_derived"]:
        assert row["signifies"] == UL_HOUSE_SIGNIFICATIONS[row["house_from_ul"]]


def test_golden_arudha_houses_for_a_fixed_transit_date(args1):
    """Pinned values, so a change in the arudha maths or the house count fails
    here rather than quietly re-reading someone's chart."""
    tr = A.get_transits(**args1, current_date="2026-08-07")
    p = tr["planets"]
    # AL is Aquarius (sign 11), UL is Cancer (sign 4).
    assert (p["Saturn"]["sign_name"], p["Saturn"]["house_from_al"],
            p["Saturn"]["house_from_ul"]) == ("Pisces", 2, 9)
    assert (p["Jupiter"]["sign_name"], p["Jupiter"]["house_from_al"],
            p["Jupiter"]["house_from_ul"]) == ("Cancer", 6, 1)


def test_digest_names_the_arudha_only_for_houses_the_tradition_reads(args1):
    """The daily highlight fires on the read houses and stays silent otherwise —
    and never renders a raw "2th"."""
    from astrology.engine import AL_HOUSE_SIGNIFICATIONS

    d = A.get_daily_digest(**args1, date="2026-08-07")
    lines = [h for h in d["highlights"] if "Arudha Lagna" in h or "Upapada" in h]
    assert lines, d["highlights"]

    # Every ordinal in every highlight must be the one _ordinal() would write.
    # Checked as a class, not per-phrase: the Sade-Sati line (houses 12/1/2) and
    # the Jupiter-from-Moon line (any house) had both been rendering "1th"/"2th"
    # since they shipped, and a substring test for "2th" would pass "12th".
    for h in d["highlights"]:
        for num, suffix in re.findall(r"\b(\d+)(st|nd|rd|th)\b", h):
            assert f"{num}{suffix}" == _ordinal(int(num)), f"{h!r}"
    # Every arudha line quotes a signification from the shared table.
    for line in lines:
        if "Arudha Lagna" in line:
            assert any(s in line for s in AL_HOUSE_SIGNIFICATIONS.values()), line
    # At most one arudha line per slow graha, the same budget the Moon lines take.
    for graha in ("Saturn", "Jupiter"):
        assert len([h for h in lines if h.startswith(graha)]) <= 1
