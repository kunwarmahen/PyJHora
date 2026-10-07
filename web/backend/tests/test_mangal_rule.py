"""Compatibility's Mangal dosha: Mars from the Lagna, cancellations cancel (§84)."""
from astrology.compute_match import _mangal_dosha


def _pp(lagna=0, **signs):
    """Aries lagna; Mars defaults to the 3rd (no dosha), others out of the way."""
    base = {0: 4, 1: 4, 2: 2, 3: 4, 4: 10, 5: 4, 6: 4, 7: 5, 8: 11}
    ids = {"sun": 0, "moon": 1, "mars": 2, "mercury": 3, "jupiter": 4,
           "venus": 5, "saturn": 6, "rahu": 7, "ketu": 8}
    for k, v in signs.items():
        base[ids[k]] = v
    return [["L", (lagna, 10.0)]] + [[p, (s, 15.0)] for p, s in sorted(base.items())]


def test_mars_from_the_lagna_makes_manglik():
    r = _mangal_dosha(_pp(mars=6))            # 7th from an Aries lagna, Libra
    assert r["manglik"] and r["status"] == "manglik" and r["from"]["Lagna"] == 7


def test_moon_or_venus_alone_is_supporting_not_manglik():
    # Mars in Gemini (3rd from Lagna); Moon in Gemini -> Mars 1st from Moon.
    r = _mangal_dosha(_pp(mars=2, moon=2, venus=2))
    assert not r["manglik"] and r["status"] == "none"
    assert r["supporting"] == ["Moon", "Venus"]


def test_cancellations_cancel():
    assert _mangal_dosha(_pp(mars=0))["status"] == "cancelled"          # own sign, 1st
    assert _mangal_dosha(_pp(mars=9, lagna=6))["status"] == "cancelled"  # exalted, 4th from Libra
    r = _mangal_dosha(_pp(mars=6, jupiter=6))                           # Jupiter with Mars
    assert r["status"] == "cancelled" and not r["manglik"]
    assert r["cancellations"]


def test_moon_house_exception_does_not_cancel_a_lagna_placement():
    # Mars in Taurus is 2nd from an Aries lagna (dosha) — Taurus is not a 2nd-house
    # exception sign. From a Taurus Moon it is 1st, whose exception is Aries only.
    r = _mangal_dosha(_pp(mars=1, moon=1))
    assert r["manglik"] and r["cancellations"] == []
