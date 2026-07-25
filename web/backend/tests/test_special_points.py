"""Golden-value tests for the special lagnas, upagrahas and Varnada (§26 follow-up).

Every expectation below is the value Jagannatha Hora prints for chart 1 (the
owner's chart, 1976-06-04 05:45:02, Aligarh) with the app's matched defaults —
True Chitra ayanamsa and mean nodes.

One caveat is deliberately encoded here. JHora's ascendant for this chart is
25 Ta 04' 23.79"; ours is 24 Ta 50' 29.18", a fixed 13.91' apart. That is not a
formula difference: raw Swiss Ephemeris agrees with us to 2", every planet
matches JHora to 0.01", and the gap is exactly reproduced by moving the birth
longitude ~0.24° east — i.e. the two programs were given different coordinates
for "Aligarh". So:

  * points that do not depend on the ascendant are pinned to JHora's own values;
  * points that hang off the ascendant are pinned to OUR values, with JHora's
    printed alongside, and the SIGNS (which are unaffected at this offset) are
    asserted against JHora.

If the ascendant question is ever settled, the second group is what changes.
"""
import pytest

from astrology import AstrologyCompute as A

DEG_TOL = 0.03

ARGS = dict(dob="1976-06-04", tob="05:45:02", place="Aligarh",
            lat=27.88, lon=78.08, tz=5.5)

# ── Ascendant-independent: pinned to Jagannatha Hora exactly ───────────────
# The six kaala-velas rise at eighth-parts of the day, so they follow sunrise
# rather than the natal ascendant.
JHORA_KAALA_VELAS = {
    "Gulika":        ("Gemini", 14.16),    # 14 Ge 09' 22.39"
    "Maandi":        ("Gemini", 25.42),    # 25 Ge 25' 22.72"
    "Kaala":         ("Leo", 9.65),        #  9 Le 38' 57.75"
    "Mrityu":        ("Virgo", 25.07),     # 25 Vi 04' 15.80"
    "Artha Prahara": ("Libra", 17.45),     # 17 Li 26' 56.09"
    "Yama Ghantaka": ("Scorpio", 9.45),    #  9 Sc 27' 12.42"
}

# Fixed offsets from the sidereal Sun.
JHORA_SOLAR_UPAGRAHAS = {
    "Dhuma":      ("Libra", 3.34),      #  3 Li 20' 13.22"
    "Vyatipata":  ("Virgo", 26.66),     # 26 Vi 39' 46.78"
    "Parivesha":  ("Pisces", 26.66),    # 26 Pi 39' 46.78"
    "Indrachapa": ("Aries", 3.34),      #  3 Ar 20' 13.22"
    "Upaketu":    ("Aries", 20.00),     # 20 Ar 00' 13.22"
}

# Moon/Rahu-derived, so unaffected by the ascendant offset.
JHORA_POINT_LAGNAS = {
    "Indu Lagna":   ("Aquarius", 0.75),  #  0 Aq 45' 12.05"
    "Bhrigu Bindu": ("Pisces", 9.15),    #  9 Pi 08' 53.67"
}

# ── Ascendant-dependent: our values, JHora's in the comment ───────────────
OUR_LAGNA_DEPENDENT = {
    "Sree Lagna":    ("Gemini", 15.18),  # JHora 15 Ge 24' 49.11"
    "Varnada Lagna": ("Leo", 24.84),     # JHora 25 Le 04' 23.79"
    "Bhava Lagna":   ("Taurus", 25.11),  # JHora 25 Ta 06' 48.83"
    "Ghati Lagna":   ("Gemini", 14.69),  # JHora 15 Ge 36' 27.50"
}

# V1..V12 signs, exactly as Jagannatha Hora prints them. These are unaffected by
# the 13.91' offset and are what pins the Varnada *method* choice: only method 1
# (Sanjay Rath) reproduces this sequence — the other three miss all twelve.
JHORA_VARNADA_SIGNS = [
    "Leo", "Virgo", "Sagittarius", "Taurus", "Aries", "Taurus",
    "Sagittarius", "Virgo", "Leo", "Capricorn", "Aries", "Capricorn",
]


@pytest.fixture(scope="module")
def points():
    r = A.get_special_points(**ARGS)
    assert r["status"] == "success", r
    return r


def _by_name(rows):
    return {row["name"]: row for row in rows}


@pytest.mark.parametrize("name,expected", sorted(JHORA_KAALA_VELAS.items()))
def test_kaala_vela_matches_jhora(points, name, expected):
    row = _by_name(points["upagrahas"]).get(name)
    assert row is not None, f"{name} missing from the upagraha table"
    assert row["sign_name"] == expected[0]
    assert row["degrees"] == pytest.approx(expected[1], abs=DEG_TOL)


@pytest.mark.parametrize("name,expected", sorted(JHORA_SOLAR_UPAGRAHAS.items()))
def test_solar_upagraha_matches_jhora(points, name, expected):
    """Guards the sidereal-Sun fix: feeding the tropical Sun put every one of
    these a full ayanamsa (~23.5°) out, which is nearly a whole sign."""
    row = _by_name(points["upagrahas"]).get(name)
    assert row is not None, f"{name} missing from the upagraha table"
    assert row["sign_name"] == expected[0]
    assert row["degrees"] == pytest.approx(expected[1], abs=DEG_TOL)


@pytest.mark.parametrize("name,expected", sorted(JHORA_POINT_LAGNAS.items()))
def test_point_lagna_matches_jhora(points, name, expected):
    row = _by_name(points["special_lagnas"]).get(name)
    assert row is not None, f"{name} missing from the special-lagna table"
    assert row["sign_name"] == expected[0]
    assert row["degrees"] == pytest.approx(expected[1], abs=DEG_TOL)


@pytest.mark.parametrize("name,expected", sorted(OUR_LAGNA_DEPENDENT.items()))
def test_lagna_dependent_points_stable(points, name, expected):
    """Pins our own values so a refactor can't drift them. The sign is JHora's;
    the degree carries the documented 13.91' ascendant offset."""
    row = _by_name(points["special_lagnas"]).get(name)
    assert row is not None, f"{name} missing from the special-lagna table"
    assert row["sign_name"] == expected[0]
    assert row["degrees"] == pytest.approx(expected[1], abs=DEG_TOL)


def test_varnada_v1_to_v12_signs_match_jhora(points):
    assert [v["sign_name"] for v in points["varnadas"]] == JHORA_VARNADA_SIGNS


def test_varnada_defaults_to_sanjay_rath(points):
    assert points["varnada_method"] == 1
    assert points["varnada_method_name"] == "Sanjay Rath"


def test_other_varnada_methods_differ():
    """The four derivations genuinely disagree — if they ever stop disagreeing,
    the Settings choice has silently become a no-op."""
    base = A.get_chart_details(**ARGS, varnada_method=1)["varnadas"]
    for m in (2, 3, 4):
        other = A.get_chart_details(**ARGS, varnada_method=m)["varnadas"]
        assert [v["sign_name"] for v in other] != [v["sign_name"] for v in base], \
            f"varnada method {m} is indistinguishable from method 1"


def test_unknown_varnada_method_falls_back_to_default():
    r = A.get_chart_details(**ARGS, varnada_method=99)
    assert r["varnada_method"] == 1


def test_new_sphutas_present(points):
    """Sookshma Tri and Rahu Tithi complete the Sphuta table against JHora's."""
    names = {s["name"] for s in points["sphutas"]}
    assert "Sookshma Tri Sphuta" in names
    assert "Rahu Tithi Sphuta" in names
    rahu_tithi = next(s for s in points["sphutas"] if s["name"] == "Rahu Tithi Sphuta")
    # Rahu/Moon-derived, so pinned to JHora: 27 Le 32' 22.08".
    assert rahu_tithi["sign_name"] == "Leo"
    assert rahu_tithi["degrees"] == pytest.approx(27.54, abs=DEG_TOL)


def test_time_lagnas_all_present(points):
    """The four kaala lagnas are the headline addition — fail loudly if the
    engine ever stops exposing one of the lambdas they hang off."""
    names = {s["name"] for s in points["special_lagnas"]}
    for n in ("Bhava Lagna", "Hora Lagna", "Ghati Lagna", "Vighati Lagna"):
        assert n in names


def test_interpreted_subset_is_narrow(points):
    """The seeded/narratable set must stay small and rule-backed. Widening it is
    a deliberate act, not something a refactor should do quietly."""
    assert set(points["interpreted"]) == {
        "Bhava Lagna", "Hora Lagna", "Ghati Lagna", "Varnada Lagna", "Gulika",
    }


def test_houses_are_relative_to_the_lagna(points):
    lagna = points["lagna_sign"]
    for row in points["special_lagnas"] + points["upagrahas"] + points["varnadas"]:
        assert row["house"] == ((row["sign"] - lagna) % 12) + 1


def test_kaala_vela_windows_in_panchanga():
    """The time face of the same four points, used by the muhurta cautions."""
    p = A.get_panchanga(date="2026-07-25", place="Aligarh",
                        lat=27.88, lon=78.08, tz=5.5)
    assert p["status"] == "success"
    kv = {k["name"]: k for k in p["kaala_velas"]}
    assert set(kv) == {"Kaala", "Mrityu", "Artha Prahara", "Yama Ghantaka"}
    for row in kv.values():
        assert row["start"] < row["end"]
        assert 1 <= row["part"] <= 8
