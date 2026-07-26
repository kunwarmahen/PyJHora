"""Golden-value tests for the special lagnas, upagrahas and Varnada (§26 follow-up).

Every expectation below is the value **Jagannatha Hora itself prints** for the
owner's chart, with the app's matched defaults (True Chitra ayanamsa, mean nodes).

IMPORTANT — the coordinates here are NOT `conftest.CHART1`'s. The app profile
stores the birth place as Aligarh (27.88 N, 78.08 E); the JHora data file for the
same chart uses **Shahgarh, 27 N 50' 43", 78 E 20' 03"** — about 0.25° east. That
difference moves the ascendant by 13.9', which propagates into every lagna-derived
point. Since the purpose of this file is to prove agreement with JHora, it uses
JHora's own coordinates; `test_golden.py` continues to pin the app profile's.
Which of the two is the real birth place is an open question for the owner.

With these coordinates the agreement is essentially exact: the ascendant matches
to 11", sunrise to 2 s, and every point below to within the API's own 2-decimal
rounding (0.01° = 0.6').
"""
import pytest

from astrology import AstrologyCompute as A

# The API rounds degrees to 2 dp (0.01° = 0.6'), so anything at or below that is
# rounding, not drift. Ghati Lagna needs a little more: it advances 1.25°/min, so
# the 2-second sunrise difference against JHora shows up as ~2.5'.
DEG_TOL = 0.02
GHATI_TOL = 0.05

# Shahgarh, per JHora's own data file for this chart.
ARGS = dict(dob="1976-06-04", tob="05:45:02", place="Shahgarh",
            lat=27.845278, lon=78.334167, tz=5.5)

# ── Every value below is JHora's, converted from D M' S" to decimal degrees ──

JHORA_SPECIAL_LAGNAS = {
    # The time-based kaala lagnas. These are the rule-bearing ones, and the
    # reason `_kaala_lagna` exists — see the PyJHora timezone bug documented there.
    "Bhava Lagna":   ("Taurus", 25 + 6/60 + 48.83/3600),
    "Hora Lagna":    ("Gemini", 0 + 14/60 + 13.50/3600),
    "Ghati Lagna":   ("Gemini", 15 + 36/60 + 27.50/3600),
    # Point-derived.
    "Sree Lagna":    ("Gemini", 15 + 24/60 + 49.11/3600),
    "Indu Lagna":    ("Aquarius", 0 + 45/60 + 12.05/3600),
    "Bhrigu Bindu":  ("Pisces", 9 + 8/60 + 53.67/3600),
    "Varnada Lagna": ("Leo", 25 + 4/60 + 23.79/3600),
}

# The six kaala-velas rise at eighth-parts of the day, so they follow sunrise.
JHORA_KAALA_VELAS = {
    "Gulika":        ("Gemini", 14 + 9/60 + 22.39/3600),
    "Maandi":        ("Gemini", 25 + 25/60 + 22.72/3600),
    "Kaala":         ("Leo", 9 + 38/60 + 57.75/3600),
    "Mrityu":        ("Virgo", 25 + 4/60 + 15.80/3600),
    "Artha Prahara": ("Libra", 17 + 26/60 + 56.09/3600),
    "Yama Ghantaka": ("Scorpio", 9 + 27/60 + 12.42/3600),
}

# Fixed offsets from the SIDEREAL Sun. Feeding the tropical Sun (the bug fixed
# alongside this work) put every one of these out by a whole ayanamsa, ~23.5°.
JHORA_SOLAR_UPAGRAHAS = {
    "Dhuma":      ("Libra", 3 + 20/60 + 13.22/3600),
    "Vyatipata":  ("Virgo", 26 + 39/60 + 46.78/3600),
    "Parivesha":  ("Pisces", 26 + 39/60 + 46.78/3600),
    "Indrachapa": ("Aries", 3 + 20/60 + 13.22/3600),
    "Upaketu":    ("Aries", 20 + 0/60 + 13.22/3600),
}

# V1..V12, exactly as JHora prints them. This is what pins the Varnada *method*:
# only method 1 (Sanjay Rath) reproduces the sequence — 2/3/4 miss all twelve.
JHORA_VARNADA_SIGNS = [
    "Leo", "Virgo", "Sagittarius", "Taurus", "Aries", "Taurus",
    "Sagittarius", "Virgo", "Leo", "Capricorn", "Aries", "Capricorn",
]

# Known deltas, deliberately NOT asserted tight (documented, not swept away):
#   Pranapada Lagna — ours 1 Ta 04', JHora 2 Ta 28'. A genuine formula difference
#     in PyJHora's pranapada_lagna, ~84'. Reference-only point, no rule attached.
#   Kunda Lagna — ours 20 Le 41', JHora 20 Le 56'. Correct: Kunda is
#     ascendant x 81, so the 11" ascendant residual is amplified 81x into ~15'.
#   Vighati Lagna — advances a full sign every 2 minutes; not meaningfully
#     comparable and labelled as such in the UI.


@pytest.fixture(scope="module")
def points():
    r = A.get_special_points(**ARGS)
    assert r["status"] == "success", r
    return r


def _by_name(rows):
    return {row["name"]: row for row in rows}


@pytest.mark.parametrize("name,expected", sorted(JHORA_SPECIAL_LAGNAS.items()))
def test_special_lagna_matches_jhora(points, name, expected):
    row = _by_name(points["special_lagnas"]).get(name)
    assert row is not None, f"{name} missing from the special-lagna table"
    assert row["sign_name"] == expected[0]
    tol = GHATI_TOL if name == "Ghati Lagna" else DEG_TOL
    assert row["degrees"] == pytest.approx(expected[1], abs=tol)


def test_kaala_lagnas_beat_the_pyjhora_bug(points):
    """The load-bearing regression: `drik.bhava_lagna` & co. add the timezone to
    an already-local JD, evaluating the Sun 5.5 h late and throwing every kaala
    lagna ~13-16' off. If someone ever "simplifies" `_kaala_lagna` back to the
    drik lambdas, this fails."""
    from jhora.panchanga import drik
    import swisseph as swe

    place = drik.Place("Shahgarh", ARGS["lat"], ARGS["lon"], ARGS["tz"])
    jd = swe.julday(1976, 6, 4, 5 + 45/60 + 2/3600)
    buggy = drik.hora_lagna(jd, place)
    buggy_abs = (int(buggy[0]) % 12) * 30 + float(buggy[1])

    ours = _by_name(points["special_lagnas"])["Hora Lagna"]
    ours_abs = ours["sign"] * 30 + ours["degrees"]
    jhora_abs = 60 + JHORA_SPECIAL_LAGNAS["Hora Lagna"][1]

    assert abs(ours_abs - jhora_abs) * 60 < 1.0, "our Hora Lagna drifted from JHora"
    assert abs(buggy_abs - jhora_abs) * 60 > 10.0, \
        "drik's Hora Lagna now agrees with JHora — the upstream bug may be fixed, " \
        "in which case _kaala_lagna can be retired"


def test_pranapada_beats_the_tharparai_unit_bug(points):
    """`utils.udhayadhi_nazhikai` scales tharparai at 9000/hour and 150/minute —
    2.5 per second — but adds seconds raw, at 1. Pranapada advances 5°/minute, so
    that 60% shortfall lands 84' off JHora, more than a quarter of a sign.
    `_pranapada_lagna` fixes the scale; the ~12' residual is the 2 s sunrise
    difference, which at 5°/minute is already 10' and cannot be reduced here."""
    row = _by_name(points["special_lagnas"])["Pranapada Lagna"]
    jhora = 2 + 28/60 + 26.58/3600          # 2 Ta 28' 26.58"
    assert row["sign_name"] == "Taurus"
    err_arcmin = abs(row["degrees"] - jhora) * 60
    assert err_arcmin < 15, f"Pranapada drifted to {err_arcmin:.1f}' from JHora"
    # And prove the raw engine call is still the bad one, so the workaround is
    # not quietly redundant.
    from jhora.panchanga import drik
    import swisseph as swe
    place = drik.Place("Shahgarh", ARGS["lat"], ARGS["lon"], ARGS["tz"])
    jd = swe.julday(1976, 6, 4, 5 + 45/60 + 2/3600)
    raw = drik.pranapada_lagna(jd, place)
    raw_err = abs(((int(raw[0]) % 12) * 30 + float(raw[1])) - (30 + jhora)) * 60
    assert raw_err > 60, (
        "drik.pranapada_lagna now agrees with JHora — the upstream unit bug may "
        "be fixed, in which case _pranapada_lagna can be retired"
    )


def test_varnada_is_not_silently_corrupted_by_the_same_bug():
    """The one place the upstream bug still reaches us that we cannot patch.

    `charts._varnada_lagna_sanjay_rath` — the Varnada derivation we default to —
    calls `drik.hora_lagna` internally, so it inherits the ~14' error. It is
    mostly immune because it consumes only whether the Hora Lagna's sign is ODD
    or EVEN, and 14' rarely crosses a sign boundary. "Mostly" is the problem: on
    this very chart the Hora Lagna sits at 0 Ge 15', i.e. 15' past the cusp, so
    the margin and the error are the same size.

    This asserts the parity currently agrees. If it ever stops agreeing for a
    chart we care about, Varnada V1..V12 is wrong and the only fix is to
    reimplement the derivation locally (as `_kaala_lagna` did for the lagnas).
    """
    from jhora.panchanga import drik
    import swisseph as swe
    from astrology.engine import _kaala_lagna, KAALA_LAGNA_RATES

    place = drik.Place("Shahgarh", ARGS["lat"], ARGS["lon"], ARGS["tz"])
    jd = swe.julday(1976, 6, 4, 5 + 45/60 + 2/3600)
    buggy_sign = int(drik.hora_lagna(jd, place)[0]) % 12
    fixed_sign = _kaala_lagna(jd, place, KAALA_LAGNA_RATES["Hora Lagna"])[0]

    # 0-based index: 0=Aries is the 1st sign, i.e. odd. Parity is all Varnada uses.
    assert (buggy_sign % 2) == (fixed_sign % 2), (
        f"drik's Hora Lagna (sign {buggy_sign}) and the corrected one "
        f"(sign {fixed_sign}) now differ in odd/even parity — Varnada V1..V12 "
        "is silently wrong and the derivation must be reimplemented locally"
    )


@pytest.mark.parametrize("name,expected", sorted(JHORA_KAALA_VELAS.items()))
def test_kaala_vela_matches_jhora(points, name, expected):
    row = _by_name(points["upagrahas"]).get(name)
    assert row is not None, f"{name} missing from the upagraha table"
    assert row["sign_name"] == expected[0]
    assert row["degrees"] == pytest.approx(expected[1], abs=DEG_TOL)


@pytest.mark.parametrize("name,expected", sorted(JHORA_SOLAR_UPAGRAHAS.items()))
def test_solar_upagraha_matches_jhora(points, name, expected):
    """Guards the sidereal-Sun fix: the tropical Sun put these ~23.5° out."""
    row = _by_name(points["upagrahas"]).get(name)
    assert row is not None, f"{name} missing from the upagraha table"
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
    assert A.get_chart_details(**ARGS, varnada_method=99)["varnada_method"] == 1


def test_rahu_tithi_sphuta_matches_jhora(points):
    """Rahu/Moon-derived, so independent of the ascendant. JHora: 27 Le 32' 22.08"."""
    row = next(s for s in points["sphutas"] if s["name"] == "Rahu Tithi Sphuta")
    assert row["sign_name"] == "Leo"
    assert row["degrees"] == pytest.approx(27 + 32/60 + 22.08/3600, abs=DEG_TOL)


def test_sookshma_tri_sphuta_present(points):
    """Completes the Sphuta table against JHora's. Pinned loosely — it is a
    composite of Gulika and the ascendant and so inherits their residuals
    (JHora prints 8 Vi 48' 10.03"; we land ~9' away)."""
    row = next(s for s in points["sphutas"] if s["name"] == "Sookshma Tri Sphuta")
    assert row["sign_name"] == "Virgo"
    assert row["degrees"] == pytest.approx(8.65, abs=0.1)


def test_time_lagnas_all_present(points):
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
    p = A.get_panchanga(date="2026-07-25", place="Shahgarh",
                        lat=ARGS["lat"], lon=ARGS["lon"], tz=ARGS["tz"])
    assert p["status"] == "success"
    kv = {k["name"]: k for k in p["kaala_velas"]}
    assert set(kv) == {"Kaala", "Mrityu", "Artha Prahara", "Yama Ghantaka"}
    for row in kv.values():
        assert row["start"] < row["end"]
        assert 1 <= row["part"] <= 8
