"""Tests for the per-graha nakshatra layer added to `get_nakshatra_profile`.

The page only ever read the *janma* (Moon's) star; every other graha's star was
computed in the birth chart but never surfaced or interpreted. These tests pin
the values, and — most importantly — assert the new list agrees with the birth
chart's own nakshatra fields, since the two are computed independently and
silently drifting apart would be the worst failure mode.
"""
import pytest

from astrology import AstrologyCompute as A
from llm_service import llm_service

CHART1_STARS = {
    "Lagna":   ("Mrigashira", 1, "Mars"),
    "Sun":     ("Rohini", 4, "Moon"),
    "Moon":    ("Magha", 1, "Ketu"),
    "Mars":    ("Ashlesha", 1, "Mercury"),
    "Mercury": ("Krittika", 2, "Sun"),
    "Jupiter": ("Bharani", 3, "Venus"),
    "Venus":   ("Rohini", 2, "Moon"),
    "Saturn":  ("Pushya", 1, "Saturn"),
    "Rahu":    ("Swati", 4, "Rahu"),
    "Ketu":    ("Bharani", 2, "Venus"),
}


@pytest.fixture
def profile1(args1):
    r = A.get_nakshatra_profile(**args1, current_date="2026-07-25")
    assert r["status"] == "success", r.get("error")
    return r


def test_planetary_nakshatras_pinned(profile1):
    got = {r["planet"]: (r["nakshatra"], r["pada"], r["lord"])
           for r in profile1["planetary_nakshatras"]}
    assert got == CHART1_STARS


def test_agrees_with_the_birth_chart(args1, profile1):
    """The birth chart derives each nakshatra independently — the two must match."""
    bc = A.calculate_birth_chart(**args1)
    stars = {r["planet"]: (r["nakshatra"], r["pada"])
             for r in profile1["planetary_nakshatras"]}
    for planet, pos in bc["d1_chart"].items():
        if planet in stars:
            assert stars[planet] == (pos["nakshatra"], pos["nakshatra_pada"]), planet
    assert stars["Lagna"] == (bc["lagna"]["nakshatra"], bc["lagna"]["nakshatra_pada"])


def test_janma_star_matches_the_moon_profile(profile1):
    """`is_janma` must mark the Moon's row, and only it."""
    janma = [r for r in profile1["planetary_nakshatras"] if r["is_janma"]]
    assert len(janma) == 1
    assert janma[0]["planet"] == "Moon"
    assert janma[0]["nakshatra"] == profile1["profile"]["name"]
    assert janma[0]["pada"] == profile1["profile"]["pada"]


def test_lagna_is_included(profile1):
    """The Lagna has a nakshatra too, and it is often the most telling one."""
    assert any(r["planet"] == "Lagna" for r in profile1["planetary_nakshatras"])


def test_every_row_is_complete(profile1):
    for r in profile1["planetary_nakshatras"]:
        assert 1 <= r["pada"] <= 4
        assert 1 <= r["nakshatra_index"] <= 27
        assert r["lord"] and r["deity"] and r["symbol"] and r["theme"]


def test_prompt_covers_every_graha(profile1):
    p = llm_service._build_planetary_nakshatras_prompt(profile1, "Tester")
    for planet in CHART1_STARS:
        assert planet in p
    assert "star lord" in p
    # It must not duplicate the janma-star personality reading.
    assert "Do not re-read the birth star" in p
