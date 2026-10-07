"""The Birth Chart's Manglik is Compatibility's rule (§86) — one reader, one answer."""
from astrology import AstrologyCompute as A
from astrology.compute_match import _mangal_dosha
from astrology.compute_strength import _manglik_description
from astrology.engine import charts, drik, swe
from tests.conftest import CHART1, CHART2, _compute_args


def _pp(args):
    y, mo, d = map(int, args["dob"].split("-"))
    hh, mm = map(int, args["tob"].split(":")[:2])
    return charts.rasi_chart(swe.julday(y, mo, d, hh + mm / 60),
                             drik.Place(args["place"], args["lat"], args["lon"], args["tz"]))


def test_birth_chart_manglik_agrees_with_compatibility():
    for chart in (CHART1, CHART2):
        args = _compute_args(chart)
        row = next(d for d in A.get_doshas(**args)["doshas"] if d["key"] == "manglik")
        assert row["present"] == _mangal_dosha(_pp(args))["manglik"], chart


def test_description_names_the_house_and_the_cancellation():
    placed = {"from": {"Lagna": 7}, "mars_sign": "Libra", "cancellations": []}
    assert "Mars is in the 7th house from the Lagna, in Libra." in _manglik_description(placed, "en")
    cancelled = dict(placed, cancellations=["Jupiter is conjunct Mars, cancelling the dosha."],
                     cancellation_codes=[{"code": "jupiter"}])
    assert "Cancelled: Jupiter is conjunct Mars" in _manglik_description(cancelled, "en")
    hi = _manglik_description(cancelled, "hi")
    assert "सातवें" in hi and "तुला" in hi and "गुरु" in hi
    assert "Libra" not in hi and "Jupiter" not in hi
    assert "In this chart" not in _manglik_description({"from": {}, "cancellations": []}, "en")
