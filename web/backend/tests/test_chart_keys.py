"""One meaning per key, across every chart the compute layer produces.

Since §65 there are exactly two sign-ish numbers in a chart payload and they do
not overlap:

  `sign_num`  1-based sign — the CELL a Kundali component draws the graha in.
  `house`     the bhava, counted whole-sign from that chart's own lagna.

Before the rename the drawing coordinate was itself called `house`, which put a
plausible wrong number under the right name: the AI read it as a bhava (§63), and
so did the Varshaphal and Tithi Pravesha pages, which printed a "House" column
straight off the sign cell.

These tests walk the real payloads rather than the code, so they hold for any
chart added later.
"""
import pytest

from astrology import AstrologyCompute, ZODIAC_NAMES

from .conftest import CHART1, _compute_args

AYAN = "TRUE_CITRA"
ARGS = _compute_args(CHART1)


def _charts():
    """(label, lagna, planets) for every chart-shaped payload we publish."""
    natal = AstrologyCompute.calculate_birth_chart(ayanamsa=AYAN, **ARGS)
    yield "natal d1_chart", natal["lagna"], natal["d1_chart"]
    yield "natal planets (renderer)", natal["lagna"], natal["planets"]
    yield "navamsa", natal["d9_lagna"], natal["d9_chart"]

    for varga in (2, 9, 10, 60):
        d = AstrologyCompute.calculate_divisional_chart(
            varga_factor=varga, ayanamsa=AYAN, **ARGS)
        yield f"D{varga}", d["lagna"], d["planets"]

    v = AstrologyCompute.get_varshaphal(year=2026, ayanamsa=AYAN, **ARGS)
    yield "varshaphal", v["lagna"], v["planets"]

    t = AstrologyCompute.get_tithi_pravesha(year=2026, ayanamsa=AYAN, **ARGS)
    yield "tithi pravesha", t["lagna"], t["planets"]

    n = AstrologyCompute.get_now_chart(
        place=CHART1["place"], lat=CHART1["latitude"], lon=CHART1["longitude"],
        tz=CHART1["timezone"], current_time="2026-09-09 12:00", ayanamsa=AYAN)
    yield "chart of the moment", n["lagna"], n["planets"]


CHARTS = list(_charts())


@pytest.mark.parametrize("label,lagna,planets", CHARTS, ids=[c[0] for c in CHARTS])
def test_house_is_the_bhava_and_sign_num_is_the_cell(label, lagna, planets):
    assert lagna["sign_num"] == ZODIAC_NAMES.index(lagna["sign_name"]) + 1
    assert lagna["house"] == 1, f"{label}: the lagna's own sign is the 1st bhava"
    for name, p in planets.items():
        sign = ZODIAC_NAMES.index(p["sign_name"])
        assert p["sign_num"] == sign + 1, f"{label} {name}"
        assert p["house"] == ((sign - (lagna["sign_num"] - 1)) % 12) + 1, f"{label} {name}"


@pytest.mark.parametrize("label,lagna,planets", CHARTS, ids=[c[0] for c in CHARTS])
def test_no_chart_still_speaks_the_old_key(label, lagna, planets):
    """`rasi` was the 0-based twin of the same number; nothing publishes it now."""
    assert "rasi" not in lagna, label
    for name, p in planets.items():
        assert "rasi" not in p, f"{label} {name}"


def test_transits_name_every_reference_they_count_from():
    """A transit has no single `house` — it is read from the lagna, the Moon and
    the arudhas at once, so each count is named and none is called `house`."""
    t = AstrologyCompute.get_transits(ayanamsa=AYAN, **ARGS)
    lagna_sign = t["natal"]["lagna"]["sign_num"] - 1
    moon_sign = t["natal"]["moon"]["sign_num"] - 1
    for name, p in t["planets"].items():
        sign = ZODIAC_NAMES.index(p["sign_name"])
        assert p["sign_num"] == sign + 1, name
        assert "house" not in p, name
        assert p["house_from_lagna"] == ((sign - lagna_sign) % 12) + 1, name
        assert p["house_from_moon"] == ((sign - moon_sign) % 12) + 1, name


def test_bhava_chart_draws_by_cusp_and_says_so():
    """The Chalit chart is the one place the cell is NOT the graha's own sign:
    a graha is drawn in the sign of the bhava its cusp puts it in."""
    b = AstrologyCompute.get_bhava_chart(ayanamsa=AYAN, **ARGS)
    assert b["lagna"]["sign_num"] == ZODIAC_NAMES.index(b["lagna"]["sign_name"]) + 1
    for name, p in b["planets"].items():
        assert 1 <= p["sign_num"] <= 12, name
        assert 1 <= p["bhava"] <= 12, name
        assert "rasi" not in p and "house" not in p, name
