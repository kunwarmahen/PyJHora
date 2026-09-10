"""The ayanamsa setting must actually reach every chart-derived compute.

This exists because it silently did not. `get_dasha_periods` was fixed once, and
its docstring then claimed it had been "the one compute in the app that did"
ignore the setting — but `get_dashas`, `get_dasha_children` and
`get_pancha_pakshi` never took an `ayanamsa` argument at all. The whole
Vimsottari page therefore answered in True Chitra no matter what the profile
said, and switching to Lahiri appeared to do nothing.

The failure mode is the nasty kind: nothing errors, nothing looks wrong, and the
numbers are plausible. It only surfaces at Sookshma, where periods are days long
and a ~3-day shift changes which lord is reported as running *today*.

Note the bug this file guards is real and fixed, but it was NOT the cause of the
Sookshma mismatch that led here — that remains open, and needs only 0.94' of Moon
longitude to explain. Do not read these pins as agreement with JHora.

Two guards here. The structural one catches the whole class the next time a
compute is added; the behavioural one proves the wiring is live end to end.
"""
import ast
import inspect
import os

import pytest

from astrology import AstrologyCompute as A
from tests.conftest import CHART1, _compute_args

PKG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "astrology")


# A birth moment goes by two names in this package. Most computes are *about* a
# chart and call the pair `dob`/`tob`; the ones that are about a place or a day
# and take a chart as an optional extra (the muhurta pair, §71) prefix it, because
# `dob` next to `date` reads as the same thing. Both are a birth moment and both
# therefore read a sidereal longitude, so the guard below has to know both names —
# it did not, and `get_muhurta_subtools` sat outside it computing a janma star in
# whatever ayanamsa happened to be set.
_BIRTH_MOMENT_NAMES = ({"dob", "tob"}, {"birth_dob", "birth_tob"})


def _chart_derived_computes():
    """Public AstrologyCompute methods that take a birth moment, under either name.

    Read off the source rather than the class so a method is caught even if it is
    never imported by another test.
    """
    found = []
    for fn in sorted(os.listdir(PKG)):
        if not fn.endswith(".py") or fn == "__init__.py":
            continue
        src = open(os.path.join(PKG, fn), encoding="utf-8").read()
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
                continue
            params = [a.arg for a in node.args.args] + [a.arg for a in node.args.kwonlyargs]
            if any(names <= set(params) for names in _BIRTH_MOMENT_NAMES):
                found.append((fn, node.name, params))
    return found


def test_the_guard_itself_sees_both_namings():
    """The guard is only worth as much as its search. If a rename or a new
    convention ever hides a whole file from `_chart_derived_computes`, this fails
    before the ayanamsa assertions start passing vacuously."""
    found = {name for _fn, name, _p in _chart_derived_computes()}
    assert {"get_dashas", "get_muhurta", "get_muhurta_subtools"} <= found, found


def test_every_chart_derived_compute_accepts_an_ayanamsa():
    """A compute that reads a birth moment reads the Moon's sidereal longitude,
    so it must be able to be told which ayanamsa to use. Taking the argument is
    the part that can be checked structurally; forwarding it is covered below."""
    missing = [f"{fn}::{name}" for fn, name, params in _chart_derived_computes()
               if "ayanamsa" not in params]
    assert not missing, (
        "these chart-derived computes cannot be told which ayanamsa to use, so "
        "they silently answer in the default: " + ", ".join(missing)
    )


@pytest.mark.parametrize("method", ["get_dashas", "get_dasha_children", "get_pancha_pakshi"])
def test_the_three_that_were_broken_still_take_it(method):
    """Named explicitly so a refactor that drops the argument fails loudly here
    rather than turning back into a silent wrong answer."""
    assert "ayanamsa" in inspect.signature(getattr(A, method)).parameters


def _sun_sookshma(ayanamsa):
    """The Rahu/Rahu/Jupiter/Sun Sookshma window — the node the bug surfaced on."""
    kids = A.get_dasha_children(**_compute_args(CHART1),
                                lords_path=["Rahu", "Rahu", "Jupiter"],
                                ayanamsa=ayanamsa)
    assert kids.get("status") == "success", kids
    sun = [c for c in kids["children"] if c["lord"] == "Sun"]
    assert len(sun) == 1, kids["children"]
    return sun[0]["start_date"], sun[0]["end_date"]


def test_ayanamsa_actually_moves_the_vimsottari_timeline():
    """Structural presence is not enough — the value has to reach the engine.

    ~1' of ayanamsa is ~0.0013 of a nakshatra, which across a 7-year Ketu balance
    is ~3 days, and that offset propagates unchanged to every deeper level. If
    these two ever come out equal, the argument is being accepted and dropped —
    which is exactly the bug this file was written for.
    """
    citra = A.get_dashas(**_compute_args(CHART1), ayanamsa="TRUE_CITRA")
    lahiri = A.get_dashas(**_compute_args(CHART1), ayanamsa="LAHIRI")
    assert citra["dasha_sequence"][0]["start_date"] != lahiri["dasha_sequence"][0]["start_date"], \
        "get_dashas ignores the ayanamsa"

    assert _sun_sookshma("TRUE_CITRA") != _sun_sookshma("LAHIRI"), \
        "get_dasha_children ignores the ayanamsa"


def test_both_ayanamsas_stay_pinned():
    """TRUE_CITRA is now Jagannatha Hora's own value, verified against the owner's
    printout: Sun Sookshma under Rahu/Rahu/Jupiter runs to 2026-09-12, and all
    nine Sookshmas in that Pratyantardasha agree to under a second.

    An earlier version of this test claimed the *Lahiri* row matched JHora. That
    was wrong twice over: the owner's JHora runs True Lahiri/Chitrapaksha (our
    TRUE_CITRA), and the real cause of the gap was the dasha year length plus the
    sub-period subdivision, both since fixed. Lahiri is kept only as the
    differential half of the guard — it must stay *different*, proving the
    ayanamsa still reaches the compute.
    """
    assert _sun_sookshma("TRUE_CITRA") == ("2026-09-05", "2026-09-12")
    assert _sun_sookshma("LAHIRI") == ("2026-09-08", "2026-09-15")


# ── The muhurta pair (§71): accepted AND forwarded ──────────────────────────
# These take the birth moment as `birth_dob`/`birth_tob`, which is how they hid
# from the structural guard above. Both read sidereal longitudes — the janma
# star, the day's star, the Panchaka lagna, the rising sign of a window — so the
# behavioural half is asserted here too rather than trusting the signature.

_MUHURTA_PLACE = dict(place="Shahgarh", lat=27.845278, lon=78.334167, tz=5.5)


def _muhurta_birth():
    return {"birth_dob": CHART1["dob"], "birth_tob": CHART1["tob"],
            "birth_lat": CHART1["latitude"], "birth_lon": CHART1["longitude"],
            "birth_tz": CHART1["timezone"]}


# TRUE_CITRA vs LAHIRI is the right differential for a *dasha* — ~1' of ayanamsa
# is ~3 days of a Ketu balance, which is loud. It is the wrong one here: these
# answers are bucketed into 13°20' nakshatras, so 1' moves a star name only when a
# longitude happens to sit within 1' of a boundary, and a test built on that would
# pass or fail on the accident of the month chosen. FAGAN is ~0.9° away, which puts
# CHART1's natal Moon on the other side of the Ashlesha/Magha boundary — so the
# janma star itself changes and every tara counted from it moves with it.
_FAR_AYANAMSA = "FAGAN"


def test_ayanamsa_reaches_the_muhurta_subtools():
    """A reader on another ayanamsa must not be handed True Chitra's stars: the
    janma star, the day's star and the Panchaka lagna are all sidereal."""
    def stars(ayanamsa):
        out = []
        for day in range(1, 11):
            r = A.get_muhurta_subtools(
                date=f"2026-11-{day:02d}", **_MUHURTA_PLACE,
                **_muhurta_birth(), ayanamsa=ayanamsa)
            assert r["status"] == "success", r
            out.append((r["today_nakshatra"], r["tarabala"]["birth_star"],
                        r["tarabala"]["tara"], r["panchaka"]["type"]))
        return out

    assert stars("TRUE_CITRA") != stars(_FAR_AYANAMSA), \
        "get_muhurta_subtools ignores the ayanamsa"


def test_ayanamsa_reaches_the_muhurta_scan():
    """Same for the scan — the personal layer's janma star comes off the natal
    Moon's sidereal longitude, so the taras it hands back must move with it."""
    def taras(ayanamsa):
        r = A.get_muhurta(activity="general", start_date="2026-11-01",
                          end_date="2026-11-10", **_MUHURTA_PLACE,
                          **_muhurta_birth(), ayanamsa=ayanamsa)
        assert r["personalized"] is True, r
        return [(d["date"], d["personal"]["tarabala"]["tara"]) for d in r["days"]]

    assert taras("TRUE_CITRA") != taras(_FAR_AYANAMSA), \
        "get_muhurta ignores the ayanamsa"


def test_the_muhurta_pair_restores_the_default_ayanamsa():
    """Both set the process-global sidereal mode and must put it back, or the
    next compute in the same request answers in whatever the last caller asked
    for. Checked through a neighbour rather than by reading swe's state."""
    baseline = A.get_dashas(**_compute_args(CHART1))["dasha_sequence"][0]["start_date"]

    A.get_muhurta(activity="general", start_date="2026-11-01", end_date="2026-11-02",
                  **_MUHURTA_PLACE, **_muhurta_birth(), ayanamsa="LAHIRI")
    assert A.get_dashas(**_compute_args(CHART1))["dasha_sequence"][0]["start_date"] == baseline

    A.get_muhurta_subtools(date="2026-11-01", **_MUHURTA_PLACE,
                           **_muhurta_birth(), ayanamsa="LAHIRI")
    assert A.get_dashas(**_compute_args(CHART1))["dasha_sequence"][0]["start_date"] == baseline
