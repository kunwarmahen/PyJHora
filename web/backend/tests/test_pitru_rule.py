"""Pitru Dosha uses our narrowed rule, not PyJHora's five-condition OR (§83).

Upstream's rule fired for 88.8% of charts. Ours keeps only the Sun-and-9th core —
the Sun or Rahu in the 9th, or the Sun in one sign with Rahu/Ketu — and every
other upstream condition must now leave the dosha absent.
"""
import json
import os

from astrology import AstrologyCompute as A
from astrology.compute_strength import _pitru_description, _pitru_reasons
from tests.conftest import CHART1, _compute_args

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dosha_prevalence.json")


def _pp(lagna=0, **signs):
    """Planet positions with Aries lagna by default; planets default to signs that
    trigger nothing (Sun in 2, Moon in 3, Rahu 6 / Ketu 12 axis, rest in 4)."""
    base = {0: 1, 1: 2, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3, 7: 5, 8: 11}
    names = {"sun": 0, "moon": 1, "mars": 2, "mercury": 3, "jupiter": 4,
             "venus": 5, "saturn": 6, "rahu": 7, "ketu": 8}
    for k, v in signs.items():
        base[names[k]] = v
    return [["L", (lagna, 10.0)]] + [[p, (s, 15.0)] for p, s in sorted(base.items())]


def test_each_condition_fires_on_its_own():
    assert _pitru_reasons(_pp()) == []
    assert _pitru_reasons(_pp(sun=8)) == ["sun_9"]          # Aries lagna -> 9th is Sagittarius
    assert _pitru_reasons(_pp(rahu=8, ketu=2)) == ["rahu_9"]
    assert _pitru_reasons(_pp(sun=5)) == ["sun_rahu"]
    assert _pitru_reasons(_pp(sun=11)) == ["sun_ketu"]
    assert _pitru_reasons(_pp(lagna=4, sun=0)) == ["sun_9"]  # 9th counted from the lagna


def test_dropped_upstream_conditions_no_longer_fire():
    from jhora.horoscope.chart import dosha
    dropped = [
        dict(moon=8),                               # Moon in the 9th
        # upstream's "Ketu in the 4th" actually tests planet 7 (Rahu) in the 4th
        dict(rahu=3, ketu=9, mars=4, saturn=4, mercury=4, jupiter=4, venus=4),
        dict(sun=1, mars=1, saturn=1),              # Sun afflicted by Mars/Saturn
        dict(moon=5),                               # Moon with Rahu
        dict(venus=4, mercury=4),                   # Venus+Mercury in the 5th
    ]
    for kw in dropped:
        assert dosha.pitru_dosha(_pp(**kw))[0], kw  # the fixture really is upstream's case
        assert _pitru_reasons(_pp(**kw)) == [], kw


def test_description_names_what_fired_in_both_languages():
    assert "In this chart: the Sun is in the 9th house." in _pitru_description(["sun_9"], "en")
    assert "In this chart" not in _pitru_description([], "en")
    hi = _pitru_description(["sun_rahu"], "hi")
    assert "सूर्य और राहु एक ही राशि में हैं" in hi
    assert _pitru_description([], "ta") == _pitru_description([], "en")


def test_get_doshas_uses_the_narrowed_rule():
    from astrology.engine import charts, drik, swe
    a = _compute_args(CHART1)
    y, m, d = map(int, a["dob"].split("-"))
    hh, mm = map(int, a["tob"].split(":")[:2])
    pp = charts.rasi_chart(swe.julday(y, m, d, hh + mm / 60),
                           drik.Place(a["place"], a["lat"], a["lon"], a["tz"]))
    for lang in ("en", "hi"):
        row = next(x for x in A.get_doshas(lang=lang, **a)["doshas"] if x["key"] == "pitru")
        assert row["present"] == bool(_pitru_reasons(pp))
        assert row["description"] == _pitru_description(_pitru_reasons(pp), lang)


def test_measured_prevalence_is_the_narrowed_rules():
    # Upstream's rule measured 88.8% on this same sample (seed 76, n=5000);
    # the narrowed rule measured 31.5% on 2026-10-06. A figure back near 90
    # means the json was regenerated against the old rule.
    pct = json.load(open(DATA))["doshas"]["pitru"]["percent"]
    assert 25 <= pct <= 40, pct
