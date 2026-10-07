"""Every dosha the app can report carries how common it is (§76.6).

The figure is measured by scripts/dosha_prevalence.py under the app's own rules.
A dosha added (or renamed) without re-running it would reach a newcomer with no
context at all — the case this guards.
"""
import json
import os

from astrology import AstrologyCompute as A
from tests.conftest import CHART1, _compute_args

DATA = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dosha_prevalence.json")


def test_every_reported_dosha_has_a_measured_prevalence():
    doshas = A.get_doshas(**_compute_args(CHART1))["doshas"]
    assert doshas
    missing = [d["key"] for d in doshas if d.get("prevalence_percent") is None]
    assert not missing, f"re-run scripts/dosha_prevalence.py — no figure for {missing}"


def test_the_measurement_is_sane():
    data = json.load(open(DATA))
    assert data["samples"] >= 1000
    pct = {k: v["percent"] for k, v in data["doshas"].items()}
    assert all(0 <= v <= 100 for v in pct.values())
    # Ganda Moola is the Moon in 6 of 27 stars — a pure-probability cross-check
    # that the sampling itself is unbiased.
    assert abs(pct["ganda_moola"] - 100 * 6 / 27) < 2.5


def test_compatibility_mangal_carries_its_own_measured_figure(args1, args2):
    """The Compatibility tab's Mangal rule is not the Birth Chart's (§83.3/§84): it
    needs its own figure, measured with compute_match._mangal_dosha — the
    function the tab calls."""
    comp = A.get_compatibility(
        male_dob=args1["dob"], male_tob=args1["tob"], male_place=args1["place"],
        male_lat=args1["lat"], male_lon=args1["lon"], male_tz=args1["tz"],
        female_dob=args2["dob"], female_tob=args2["tob"], female_place=args2["place"],
        female_lat=args2["lat"], female_lon=args2["lon"], female_tz=args2["tz"],
    )
    md = comp["mangal_dosha"]
    stored = json.load(open(DATA))["compatibility"]["mangal"]
    assert md["prevalence_percent"] == stored["percent"]
    assert md["placement_percent"] == stored["placement_percent"]
    # Mars in 6 of 12 houses from the Lagna: the placement alone is ~50% by pure
    # probability (measured 50.6%); cancellations can only bring Manglik below it
    # (measured 31.0%, 2026-10-06). A figure near 89 means the old any-of-three
    # rule came back.
    assert abs(stored["placement_percent"] - 50) < 3
    assert 20 <= stored["percent"] < stored["placement_percent"]
