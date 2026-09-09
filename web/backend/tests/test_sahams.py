"""The Sahams — and a pin on the engine signature that silently emptied them.

Up to PyJHora V4.6.0 a saham was `punya_saham(planet_positions, night_time_birth)`.
V4.9.3 changed every one to `(jd_at_dob, place, dhasa_progression_correction=0.0)`
— they cast their own chart and work out day/night themselves. That change
arrived with the 5.0 upgrade (§61) and the call sites still passed the old pair,
so every saham raised TypeError into an `except TypeError` fallback, printed, and
was skipped. `get_sahams` returned `{"status": "success", "sahams": []}` and the
Sensitive Points page, the Varshaphal reading and the pravesha digests quietly
lost the whole panel (§64).

Nothing here needs an external oracle: a saham is arithmetic on three longitudes
the chart already gives us.
"""
import pytest

from astrology import AstrologyCompute, ZODIAC_NAMES

from .conftest import CHART1, _compute_args

AYAN = "TRUE_CITRA"


def _longitude(pos):
    return ZODIAC_NAMES.index(pos["sign_name"]) * 30.0 + pos["degrees"]


@pytest.fixture(scope="module")
def natal():
    return AstrologyCompute.get_sahams(ayanamsa=AYAN, **_compute_args(CHART1))


def test_all_thirty_six_natal_sahams_compute(natal):
    """The regression itself: this list was empty, under a 'success' status."""
    assert natal["status"] == "success"
    assert len(natal["sahams"]) == 36
    assert {s["name"] for s in natal["sahams"]} >= {"Punya", "Vidya", "Vivaha"}


def test_punya_is_moon_minus_sun_plus_lagna(natal):
    """Punya by day = Moon - Sun + Lagna. Checked against the chart itself.

    The owner is a day birth (05:45, after sunrise), so the day formula applies
    and the engine's night branch must not fire.
    """
    chart = AstrologyCompute.calculate_birth_chart(ayanamsa=AYAN, **_compute_args(CHART1))
    d1 = chart["d1_chart"]
    moon, sun = _longitude(d1["Moon"]), _longitude(d1["Sun"])
    lagna = chart["ascendant"]["rasi"] * 30.0 + chart["ascendant"]["degrees"]

    assert natal["night_birth"] is False
    expected = (moon - sun + lagna) % 360.0
    punya = next(s for s in natal["sahams"] if s["name"] == "Punya")
    assert punya["sign_name"] == ZODIAC_NAMES[int(expected // 30)]
    assert punya["degrees"] == pytest.approx(expected % 30, abs=0.02)
    # Pinned, so a drift in the ayanamsa or the formula shows up as a diff.
    assert (punya["sign_name"], punya["degrees"], punya["house"]) == ("Leo", 5.81, 4)


def test_every_saham_house_is_counted_from_the_lagna(natal):
    lagna = natal["lagna_sign"]
    for s in natal["sahams"]:
        sign = ZODIAC_NAMES.index(s["sign_name"])
        assert s["house"] == ((sign - lagna) % 12) + 1, s["name"]
        assert 0 <= s["degrees"] < 30


@pytest.mark.parametrize("compute,kwargs,path", [
    ("get_varshaphal", {"year": 2026}, ()),
    ("get_tithi_pravesha", {"year": 2026}, ()),
    ("get_monthly_digest", {"date": "2026-09-09", "basis": "solar"}, ("pravesh",)),
])
def test_the_annual_rungs_carry_their_eight_sahams(compute, kwargs, path):
    r = getattr(AstrologyCompute, compute)(ayanamsa=AYAN, **kwargs, **_compute_args(CHART1))
    for key in path:
        r = r.get(key) or {}
    assert len(r.get("sahams") or []) == 8, compute


def test_the_annual_saham_follows_the_return_instant_not_the_birth():
    """The 2026 solar return falls at 01:30 — night — so Punya must use the
    night formula (Sun - Moon + Lagna). Getting this from the birth's day/night
    instead, as the old code intended to, lands a whole sign away."""
    v = AstrologyCompute.get_varshaphal(year=2026, ayanamsa=AYAN, **_compute_args(CHART1))
    assert v["year_entry"]["time"].startswith("01:")
    moon, sun = _longitude(v["planets"]["Moon"]), _longitude(v["planets"]["Sun"])
    lagna = _longitude(v["lagna"])
    night = (sun - moon + lagna) % 360.0
    punya = next(s for s in v["sahams"] if s["name"] == "Punya")
    assert punya["sign_name"] == ZODIAC_NAMES[int(night // 30)]
    assert punya["degrees"] == pytest.approx(night % 30, abs=0.02)


def test_engine_saham_signature_is_jd_and_place():
    """Pin the upstream contract that broke silently.

    If a future PyJHora bump changes it again, this fails outright instead of
    every Saham list going quietly empty.
    """
    from jhora.horoscope.transit import saham as saham_mod
    import inspect

    params = list(inspect.signature(saham_mod.punya_saham).parameters)
    assert params[:2] == ["jd_at_dob", "place"]
    jd, place_obj, *_ = AstrologyCompute._natal_jd_place(
        CHART1["dob"], CHART1["tob"], CHART1["place"],
        CHART1["latitude"], CHART1["longitude"], CHART1["timezone"])
    assert isinstance(saham_mod.punya_saham(jd, place_obj), float)
