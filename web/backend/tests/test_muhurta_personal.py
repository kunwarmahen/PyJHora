"""The personal half of a muhurta (§68.6).

`get_muhurta` used to score a day from the Panchanga alone, and its own docstring
said so: *"Location-driven (not birth-chart bound)"*. Two people in the same city
got the identical answer. These tests pin the join that fixed it — Tara Bala,
Chandra Bala, the running Vimsottari lords' gochara and per-window lagna shuddhi
— and, above all, the acceptance property the feature exists for:

    **two different charts, same city, same fortnight, different answers.**

They also pin the *class* of thing that was broken rather than one instance:
every day of a personalised scan carries the personal block, every window a lagna
verdict, and the verdict rules are asserted as rules (an `avoid` is always an 8th
from one of the two references) rather than as a table of expected dates.
"""
import pytest

from astrology import AstrologyCompute as A
from astrology.compute_muhurta import (
    _MUHURTA_LAGNA_SCORE, _muhurta_dasha_on, _muhurta_natal,
)

from .conftest import CHART1, CHART2

# One fixed fortnight so a failure is reproducible. Far enough out that it never
# collides with "today", which would make the scan's default range leak in.
START, END = "2026-11-02", "2026-11-16"
PLACE = dict(place="Shahgarh", lat=27.845278, lon=78.334167, tz=5.5)


def _birth_kwargs(chart):
    """A conftest chart as get_muhurta's birth_* kwargs."""
    return {
        "birth_dob": chart["dob"], "birth_tob": chart["tob"],
        "birth_lat": chart["latitude"], "birth_lon": chart["longitude"],
        "birth_tz": chart["timezone"],
    }


@pytest.fixture(scope="module")
def almanac():
    """The un-personalised scan — what this endpoint always returned."""
    return A.get_muhurta(activity="business", start_date=START, end_date=END, **PLACE)


@pytest.fixture(scope="module")
def personal1():
    return A.get_muhurta(activity="business", start_date=START, end_date=END,
                         **PLACE, **_birth_kwargs(CHART1))


@pytest.fixture(scope="module")
def personal2():
    return A.get_muhurta(activity="business", start_date=START, end_date=END,
                         **PLACE, **_birth_kwargs(CHART2))


# ── The almanac-only path is unchanged ──────────────────────────────────────

def test_without_birth_details_it_is_still_the_almanac(almanac):
    """No birth data → no personal layer, and it says so rather than implying one."""
    assert almanac["status"] == "success"
    assert almanac["personalized"] is False
    assert almanac["personal_basis"] is None
    assert almanac["days"], "a fortnight scan that returns no days is a dead feature"
    assert all(d["personal"] is None for d in almanac["days"])
    assert all("lagna_shuddhi" not in w for w in almanac["best_windows"])
    # The Panchanga score is still the whole score when nothing personal applies.
    assert all(d["score"] == d["panchanga_score"] for d in almanac["days"])


def test_missing_coordinates_fail_loudly_rather_than_answering_for_chennai():
    """The old fallback answered for Chennai (13.08/80.27) when a caller sent no
    place — a confidently wrong answer, not a worse one. §68.6."""
    r = A.get_muhurta(activity="general", start_date=START, end_date=START)
    assert r["status"] == "failed"
    assert "location" in r["error"].lower()

    sub = A.get_muhurta_subtools(date=START)
    assert sub["status"] == "failed"


# ── The personal layer exists on every day and every window ─────────────────

def test_every_day_of_a_personalised_scan_carries_all_four_checks(personal1):
    assert personal1["status"] == "success"
    assert personal1["personalized"] is True
    basis = personal1["personal_basis"]
    assert basis["birth_star"] and basis["birth_moon_sign"] and basis["birth_lagna_sign"]

    assert personal1["days"]
    for d in personal1["days"]:
        p = d["personal"]
        assert p is not None, f"{d['date']} has no personal block"
        assert p["tarabala"]["tara"] and p["tarabala"]["tone"]
        assert 1 <= p["chandrabala"]["position"] <= 12
        assert p["chandrabala"]["tone"] in ("good", "bad", "neutral")
        # The dasha layer is the one part that can legitimately be empty (a chart
        # whose sequence does not cover the date), but not for a living native.
        assert p["dasha"]["maha_lord"], f"{d['date']} found no running Mahadasha"
        assert p["dasha"]["lords"], f"{d['date']} scored no dasha lord's gochara"
        for lord in p["dasha"]["lords"]:
            assert 1 <= lord["house_from_moon"] <= 12
            assert lord["tone"] in ("good", "bad", "caution")


def test_every_window_of_a_personalised_scan_has_a_lagna_verdict(personal1):
    windows = [w for d in personal1["days"] for w in d["windows"]]
    assert windows, "a fortnight with no candidate windows cannot test the ranking"
    for w in windows:
        ls = w["lagna_shuddhi"]
        assert ls["verdict"] in _MUHURTA_LAGNA_SCORE
        assert 1 <= ls["from_moon"] <= 12 and 1 <= ls["from_lagna"] <= 12
        assert w["fit_score"] == w["day_score"] + _MUHURTA_LAGNA_SCORE[ls["verdict"]]


def test_lagna_verdicts_follow_the_stated_rule(personal1):
    """`avoid` means the 8th from the janma rasi or lagna — the classical bar —
    and nothing else does. Pinned as a rule so a later tweak to the thresholds
    has to be deliberate."""
    for d in personal1["days"]:
        for w in d["windows"]:
            ls = w["lagna_shuddhi"]
            counts = (ls["from_moon"], ls["from_lagna"])
            if ls["verdict"] == "avoid":
                assert 8 in counts
            else:
                assert 8 not in counts
            if ls["verdict"] == "caution":
                assert counts[0] in (6, 12) or counts[1] in (6, 12)
            if ls["verdict"] == "strong":
                assert all(c in (1, 4, 5, 7, 9, 10) for c in counts)


def test_a_barred_window_never_outranks_a_clear_one(personal1):
    """A window the native's own lagna shuddhi bars is shown, not dropped — but it
    sinks below everything clear, or the ranking would recommend the 8th."""
    verdicts = [(w.get("lagna_shuddhi") or {}).get("verdict")
                for w in personal1["best_windows"]]
    barred = [i for i, v in enumerate(verdicts) if v == "avoid"]
    clear = [i for i, v in enumerate(verdicts) if v != "avoid"]
    if barred and clear:
        assert min(barred) > max(clear)


# ── The acceptance property: it is no longer the same answer for everyone ───

def test_two_charts_in_the_same_city_get_different_answers(personal1, personal2):
    """The whole point of §68.6. Same place, same activity, same fortnight — the
    two natives must not receive the same ranking or the same day ratings."""
    assert personal1["personal_basis"] != personal2["personal_basis"]

    ratings1 = [d["rating"] for d in personal1["days"]]
    ratings2 = [d["rating"] for d in personal2["days"]]
    taras1 = [d["personal"]["tarabala"]["tara"] for d in personal1["days"]]
    taras2 = [d["personal"]["tarabala"]["tara"] for d in personal2["days"]]
    assert taras1 != taras2
    assert ratings1 != ratings2

    top1 = [(w["date"], w["start"]) for w in personal1["best_windows"]]
    top2 = [(w["date"], w["start"]) for w in personal2["best_windows"]]
    assert top1 != top2


def test_the_personal_layer_actually_moves_the_rating(almanac, personal1):
    """A personal layer that never changes a verdict is decoration. At least one
    day in a fortnight must rate differently from the bare almanac."""
    plain = {d["date"]: d["rating"] for d in almanac["days"]}
    mine = {d["date"]: d["rating"] for d in personal1["days"]}
    assert plain.keys() == mine.keys()
    assert any(plain[k] != mine[k] for k in plain)
    # …and the Panchanga half is untouched underneath it.
    plain_scores = {d["date"]: d["score"] for d in almanac["days"]}
    assert all(d["panchanga_score"] == plain_scores[d["date"]]
               for d in personal1["days"])


def test_personalised_scans_are_deterministic():
    """Same inputs, same output — the ayanamsa is set and restored around the
    natal/transit charts, so a second call must not drift."""
    kw = dict(activity="marriage", start_date=START, end_date="2026-11-08",
              **PLACE, **_birth_kwargs(CHART1))
    a, b = A.get_muhurta(**kw), A.get_muhurta(**kw)
    assert a["days"] == b["days"]
    assert a["best_windows"] == b["best_windows"]


# ── Cross-surface agreement: two lists that must not drift ──────────────────

def test_tarabala_agrees_with_the_day_subtools_surface():
    """The same Tara for the same native on the same day, whichever page asks.
    Muhurta computes it from the Panchanga's nakshatra index; the sub-tools
    compute it from the Moon at sunrise. If those two ever disagree the app
    contradicts itself on one screen."""
    day = "2026-11-05"
    scan = A.get_muhurta(activity="general", start_date=day, end_date=day,
                         **PLACE, **_birth_kwargs(CHART1))
    sub = A.get_muhurta_subtools(
        date=day, place=PLACE["place"], lat=PLACE["lat"], lon=PLACE["lon"],
        tz=PLACE["tz"], birth_dob=CHART1["dob"], birth_tob=CHART1["tob"],
        birth_lat=CHART1["latitude"], birth_lon=CHART1["longitude"],
        birth_tz=CHART1["timezone"])
    assert sub["status"] == "success"
    tb = scan["days"][0]["personal"]["tarabala"]
    assert tb["tara"] == sub["tarabala"]["tara"]
    assert tb["birth_star"] == sub["tarabala"]["birth_star"]


def test_the_dasha_lookup_tracks_the_bhukti_not_just_today():
    """A muhurta range is searched in the *future*, and a Bhukti can turn over
    inside the very fortnight being scanned — so each day looks its own lords up
    out of the sequence rather than reusing `current_dasha`."""
    dashas = A.get_dashas(dob=CHART1["dob"], tob=CHART1["tob"], place="",
                          lat=CHART1["latitude"], lon=CHART1["longitude"],
                          tz=CHART1["timezone"])
    seq = dashas["dasha_sequence"]
    maha = next(m for m in seq if m["sub_periods"])
    for sub in maha["sub_periods"][:3]:
        got_maha, got_bhukti = _muhurta_dasha_on(seq, sub["start_date"])
        assert got_maha == maha["lord"]
        assert got_bhukti == sub["lord"]
    # A date before the chart's first Mahadasha resolves to nothing, not a crash.
    assert _muhurta_dasha_on(seq, "1900-01-01") == (None, None)


def test_unusable_birth_details_degrade_to_the_almanac_rather_than_failing():
    """A muhurta with a broken profile must still answer the location question —
    the personal layer is an enrichment, never a precondition."""
    assert _muhurta_natal("not-a-date", "05:45", 27.8, 78.3, 5.5) is None
    assert _muhurta_natal(CHART1["dob"], CHART1["tob"], None, None, 5.5) is None

    r = A.get_muhurta(activity="general", start_date=START, end_date=START,
                      **PLACE, birth_dob="not-a-date", birth_tob="05:45",
                      birth_lat=27.8, birth_lon=78.3, birth_tz=5.5)
    assert r["status"] == "success"
    assert r["personalized"] is False


# ── The route carries the birth details through ────────────────────────────

def test_endpoint_personalises_only_when_a_body_is_sent(client):
    """The wiring most likely to rot: `/api/astrology/muhurta` takes its inputs as
    query params and the birth chart as an *optional body*. A body that silently
    fails to bind would leave the endpoint answering the almanac forever while
    every other layer looks correct."""
    params = {"activity": "business", "start_date": START, "end_date": "2026-11-06",
              "place": PLACE["place"], "latitude": PLACE["lat"],
              "longitude": PLACE["lon"], "timezone": PLACE["tz"]}

    plain = client.post("/api/astrology/muhurta", params=params)
    assert plain.status_code == 200, plain.text
    assert plain.json()["personalized"] is False

    mine = client.post("/api/astrology/muhurta", params=params, json=CHART1)
    assert mine.status_code == 200, mine.text
    body = mine.json()
    assert body["personalized"] is True
    assert body["personal_basis"]["birth_star"]
    assert all(d["personal"] for d in body["days"])
