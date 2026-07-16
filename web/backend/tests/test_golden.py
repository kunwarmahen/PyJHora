"""Golden-value regression tests for AstrologyCompute (§3.2).

These pin the engine's output for two fixed charts so any drift — a PyJHora
version bump, an ayanamsa/node default change, a refactor of astrology.py — is
caught immediately. The chart-1 numbers were cross-checked against Jagannatha
Hora (todo §26) with the app's matched defaults (True Chitra + mean nodes).

Longitudes are asserted to ±0.02° (the API rounds degrees to 2 dp); signs, D9
placements, dasha boundary dates and panchanga limbs are asserted exactly.
"""
import pytest

from astrology import AstrologyCompute as A

DEG_TOL = 0.02

# ── Chart 1 (owner, JHora-verified) ─────────────────────────────────────────
CHART1_LAGNA = ("Taurus", 24.83)
CHART1_PLANETS = {
    "Sun": ("Taurus", 20.00),
    "Moon": ("Leo", 0.75),
    "Mars": ("Cancer", 17.02),
    "Mercury": ("Taurus", 1.58),
    "Jupiter": ("Aries", 22.86),
    "Venus": ("Taurus", 16.15),
    "Saturn": ("Cancer", 6.37),
    "Rahu": ("Libra", 17.54),
    "Ketu": ("Aries", 17.54),
}
CHART1_D9 = {
    "Sun": "Cancer", "Moon": "Aries", "Mars": "Sagittarius",
    "Mercury": "Capricorn", "Jupiter": "Libra", "Venus": "Taurus",
    "Saturn": "Leo", "Rahu": "Pisces", "Ketu": "Virgo",
}
CHART1_SARVA = [24, 31, 21, 26, 25, 28, 35, 20, 22, 30, 36, 39]
CHART1_SARVA_TOTAL = 337

# ── Chart 2 ─────────────────────────────────────────────────────────────────
CHART2_LAGNA = ("Taurus", 13.20)
CHART2_PLANETS = {
    "Sun": ("Capricorn", 1.25),
    "Moon": ("Leo", 22.23),
    "Mars": ("Scorpio", 26.12),
    "Mercury": ("Sagittarius", 17.73),
    "Jupiter": ("Gemini", 9.67),
    "Venus": ("Capricorn", 7.05),
    "Saturn": ("Sagittarius", 23.60),
    "Rahu": ("Capricorn", 23.99),
    "Ketu": ("Cancer", 23.99),
}


def _assert_chart(result, exp_lagna, exp_planets):
    assert result.get("status") != "failed", result
    assert result["lagna"]["sign_name"] == exp_lagna[0]
    assert result["lagna"]["degrees"] == pytest.approx(exp_lagna[1], abs=DEG_TOL)
    for name, (sign, deg) in exp_planets.items():
        p = result["planets"][name]
        assert p["sign_name"] == sign, f"{name}: {p['sign_name']} != {sign}"
        assert p["degrees"] == pytest.approx(deg, abs=DEG_TOL), \
            f"{name}: {p['degrees']} != {deg}"


def test_chart1_d1(args1):
    _assert_chart(A.calculate_birth_chart(**args1), CHART1_LAGNA, CHART1_PLANETS)


def test_chart1_d9_signs(args1):
    r = A.calculate_birth_chart(**args1)
    for name, sign in CHART1_D9.items():
        assert r["d9_chart"][name]["sign_name"] == sign, \
            f"D9 {name}: {r['d9_chart'][name]['sign_name']} != {sign}"


def test_chart2_d1(args2):
    _assert_chart(A.calculate_birth_chart(**args2), CHART2_LAGNA, CHART2_PLANETS)


def test_chart1_vimsottari_boundaries(args1):
    d = A.get_dashas(**args1)
    assert d.get("status") != "failed", d
    seq = d["dasha_sequence"]
    # First three maha lords + boundary dates (all 120 years are seeded from birth).
    assert [(m["lord"], m["start_date"], m["end_date"]) for m in seq[:3]] == [
        ("Ketu", "1976-01-11", "1983-01-11"),
        ("Venus", "1983-01-11", "2003-01-11"),
        ("Sun", "2003-01-11", "2009-01-11"),
    ]


def test_chart1_panchanga_fixed_date(args1):
    p = A.get_panchanga(date="2026-07-16", place="Aligarh",
                        lat=27.88, lon=78.08, tz=5.5)
    assert p.get("status") == "success", p
    assert p["vaara"]["name"] == "Thursday"
    assert p["tithi"]["name"] == "Shukla Dwitiya"
    assert p["nakshatra"]["name"] == "Ashlesha"
    assert p["yoga"]["name"] == "Siddhi"
    assert p["karana"]["name"] == "Kaulava"


def test_chart1_ashtakavarga(args1):
    av = A.get_ashtakavarga(**args1)
    assert av.get("status") == "success", av
    assert av["sarva"] == CHART1_SARVA
    assert av["sarva_total"] == CHART1_SARVA_TOTAL
    # The eight Bhinna rows always sum to the Sarva total.
    assert sum(av["sarva"]) == CHART1_SARVA_TOTAL


def test_ashtakoot_pair(args1, args2):
    comp = A.get_compatibility(
        male_dob=args1["dob"], male_tob=args1["tob"], male_place=args1["place"],
        male_lat=args1["lat"], male_lon=args1["lon"], male_tz=args1["tz"],
        female_dob=args2["dob"], female_tob=args2["tob"], female_place=args2["place"],
        female_lat=args2["lat"], female_lon=args2["lon"], female_tz=args2["tz"],
    )
    assert comp["total_score"] == pytest.approx(27.0, abs=0.01)
    assert comp["status"] == "Very Good Match"
    assert comp["boy"] == {"nakshatra": "Magha", "pada": 1}
    assert comp["girl"] == {"nakshatra": "Purva Phalguni", "pada": 3}


def test_marriage_workspace_seventh_house(args1, args2):
    mw = A.get_marriage_workspace(
        male_dob=args1["dob"], male_tob=args1["tob"], male_place=args1["place"],
        male_lat=args1["lat"], male_lon=args1["lon"], male_tz=args1["tz"],
        female_dob=args2["dob"], female_tob=args2["tob"], female_place=args2["place"],
        female_lat=args2["lat"], female_lon=args2["lon"], female_tz=args2["tz"],
    )
    assert mw.get("status") == "success", mw
    male = mw["seventh_house"]["male"]
    # Taurus lagna → 7th is Scorpio, lord Mars (debilitated in Cancer for this chart).
    assert male["lagna_sign"] == "Taurus"
    assert male["seventh_sign"] == "Scorpio"
    assert male["seventh_lord"] == "Mars"
    assert male["seventh_lord_condition"]["dignity"] == "debilitated"


def test_transit_carries_bindu_annotation(args1):
    """§2.4 join: pin the actual bindu counts + chips for a fixed transit date.

    Values are pinned (not just type-checked) so a drift in either half of the
    join — the Ashtakavarga tables or the chip thresholds — fails here."""
    tr = A.get_transits(**args1, current_date="2026-07-16")
    assert tr.get("status") == "success", tr
    planets = tr["planets"]

    # (sign, own-BAV bindus, Sarva bindus, chip) for the fixed date.
    expected = {
        "Saturn":  ("Pisces", 5, 39, "good"),
        "Jupiter": ("Cancer", 3, 26, "weak"),
        "Sun":     ("Gemini", 2, 21, "weak"),
    }
    for name, (sign, bav, sav, strength) in expected.items():
        p = planets[name]
        assert p["sign_name"] == sign, f"{name} sign: {p['sign_name']} != {sign}"
        assert p["bav_bindus"] == bav, f"{name} BAV: {p['bav_bindus']} != {bav}"
        assert p["sav_bindus"] == sav, f"{name} SAV: {p['sav_bindus']} != {sav}"
        assert p["bindu_strength"] == strength, \
            f"{name} chip: {p['bindu_strength']} != {strength}"

    # The lunar nodes have no Bhinnashtakavarga of their own, so they carry no
    # BAV count and are judged on the Sarva total alone.
    rahu = planets["Rahu"]
    assert rahu["bav_bindus"] is None
    assert rahu["sav_bindus"] == 36
    assert rahu["bindu_strength"] == "good"

    # The per-planet SAV reading must agree with the returned Sarva row.
    sarva = tr["ashtakavarga"]["sarva"]
    assert sarva[planets["Saturn"]["rasi"]] == 39


def test_sudarshana_chakra_dasha(args1):
    """§2.7 Sudarshana Chakra: a 12-year wheel run from three references at once.

    Guards the subtle bit — the engine's triple members are named `*_house` but are
    actually 0-based **sign indices**, so year 1 must land on each wheel's own natal
    sign (house 1 on all three), not on an offset sign.
    """
    r = A.get_dasha_periods("sudharsana_chakra", **args1)
    assert r.get("status") == "success", r
    assert r["lord_type"] == "chakra"
    # Chart 1: Taurus lagna, Leo Moon, Taurus Sun.
    assert r["chakra_refs"] == {"lagna": "Taurus", "moon": "Leo", "sun": "Taurus"}
    # 12-year wheel x 9 cycles.
    assert len(r["periods"]) == 108

    y1 = r["periods"][0]
    assert y1["start_date"] == "1976-06-04"
    assert y1["lord"] == "Taurus · Leo · Taurus"
    for wheel, sign in (("lagna", "Taurus"), ("moon", "Leo"), ("sun", "Taurus")):
        assert y1["chakra"][wheel] == {"house": 1, "sign": sign}

    # Year 2 advances one house on every wheel; year 13 wraps back to the start.
    assert [r["periods"][1]["chakra"][w]["house"] for w in ("lagna", "moon", "sun")] == [2, 2, 2]
    assert r["periods"][12]["lord"] == y1["lord"]
    assert [r["periods"][12]["chakra"][w]["house"] for w in ("lagna", "moon", "sun")] == [1, 1, 1]


def test_bindu_chip_thresholds():
    """The classical thresholds themselves: own-BAV >=5 supported / ==4 neutral /
    <=3 rough, and the node fallback on Sarva (>=30 / >=25 / else)."""
    chip = A._bindu_chip
    assert chip(8, 40)[0] == "good"
    assert chip(5, 10)[0] == "good"
    assert chip(4, 10)[0] == "neutral"
    assert chip(3, 40)[0] == "weak"
    assert chip(0, 40)[0] == "weak"
    # Nodes (no own BAV) fall back to the Sarva total.
    assert chip(None, 30)[0] == "good"
    assert chip(None, 25)[0] == "neutral"
    assert chip(None, 24)[0] == "weak"
