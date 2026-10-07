"""Latitude 0 (the equator) and longitude 0 (Greenwich) are real places (§89).

`if not lat or not lon` read 0.0 as "not given" and charted the birth in Chennai —
the coordinate twin of §86's `tz or 5.5`.
"""
import glob
import os
import re

from astrology import AstrologyCompute as A

# Accra-ish, on the Greenwich meridian; and a point on the equator (Quito's longitude).
GREENWICH = dict(dob="1990-05-10", tob="12:00:00", place="Greenwich line", lat=5.6, lon=0.0, tz=0.0)
EQUATOR = dict(dob="1990-05-10", tob="12:00:00", place="Equator", lat=0.0, lon=-78.5, tz=-5.0)


def _lagna(**kw):
    return A.get_birth_chart(**kw)["ascendant"]["absolute_longitude"]


def test_zero_coordinate_births_are_not_charted_in_chennai():
    chennai = dict(lat=13.0827, lon=80.2707)
    for birth in (GREENWICH, EQUATOR):
        here = _lagna(**birth)
        assert abs(here - _lagna(**{**birth, **chennai})) > 1, birth["place"]
        # ...and a hair off zero gives (almost) the same chart, as it should.
        nudged = {k: (v + 1e-6 if k in ("lat", "lon") and v == 0.0 else v) for k, v in birth.items()}
        assert abs(here - _lagna(**nudged)) < 0.01, birth["place"]


def test_no_truthiness_fallback_for_a_coordinate():
    """The class test: `not lat` / `lat or <default>` anywhere in the backend brings it back."""
    root = os.path.dirname(os.path.dirname(__file__))
    bad = []
    pat = re.compile(r"\bnot\s+[a-z_]*(lat|lon|latitude|longitude)\b|\b[a-z_]*(lat|lon|latitude|longitude)\s+or\s+[\d.-]")
    for p in glob.glob(f"{root}/astrology/*.py") + glob.glob(f"{root}/routes/*.py") + glob.glob(f"{root}/*.py"):
        for i, line in enumerate(open(p), 1):
            if pat.search(line):
                bad.append(f"{os.path.relpath(p, root)}:{i}")
    assert not bad, f"0 is a real coordinate — use `x is None`: {bad}"
