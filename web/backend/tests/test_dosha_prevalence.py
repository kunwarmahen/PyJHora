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
