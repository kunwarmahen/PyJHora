"""A UTC+0 birth is a real offset, not a missing one (§86).

`tz or 5.5` read tz=0.0 as "not given" and charted every London / Lisbon / Accra
/ Reykjavik birth as if born in India — 5½ hours off, a different Lagna.
"""
import glob
import os
import re

from astrology import AstrologyCompute as A

LONDON = dict(dob="1990-05-10", tob="12:00:00", place="London", lat=51.51, lon=-0.13)


def test_utc_zero_birth_is_not_charted_as_ist():
    zero = A.get_birth_chart(**LONDON, tz=0.0)["ascendant"]["sign_name"]
    assert zero == "Leo"  # Gemini is what IST (+5:30) gives — the old bug
    assert A.get_birth_chart(**LONDON, tz=5.5)["ascendant"]["sign_name"] != zero


def test_no_truthiness_fallback_for_an_offset():
    """The class test: `<offset> or 5.5` anywhere in the backend brings it back."""
    root = os.path.dirname(os.path.dirname(__file__))
    bad = []
    for p in glob.glob(f"{root}/astrology/*.py") + glob.glob(f"{root}/routes/*.py") + glob.glob(f"{root}/*.py"):
        for i, line in enumerate(open(p), 1):
            if re.search(r"(tz|timezone|tz_offset)\s+or\s+(5\.5|[a-z_]+\.?[a-z_]*timezone)", line):
                bad.append(f"{os.path.relpath(p, root)}:{i}")
    assert not bad, f"0 is a real UTC offset — use `5.5 if tz is None else tz`: {bad}"
