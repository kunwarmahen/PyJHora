"""Tests for nakshatra gochara (§75) — the star each graha transits, its dated
window, and the four personal hooks that turn it into a reading.

Two failure modes drive most of what is pinned here.

The first is a *silently wrong window*. The scanner samples once a day and
bisects; that is sound only while a graha cannot cross a whole arc between two
samples, which is true of every graha but the Moon at 13°20'. A window that is
merely plausible — right star, wrong dates, or a date taken from the edge of the
scan rather than a real ingress — reads exactly like a correct one, so the spans
are checked for contiguity, for containing the moment they claim to, and for
naming the same star the position payload names.

The second is *the verdict quietly learning from the symbolism*. The tradition
supplies no "graha X transiting star Y" result table. The deity, symbol and
theme ride along as imagery and the verdict must stay a pure function of
tarabala plus the graha's own nature — so that is asserted directly, by feeding
the same tara and nature through different stars.
"""
import pytest

from astrology import AstrologyCompute as A
from astrology.engine import _tarabala, TARABALA_NAMES
import reference_data as refdata
import tools as tool_registry

from .conftest import CHART1, CHART2

# A fixed transit date, so every window below is a stated fact rather than
# whatever today happens to be.
WHEN = "2026-09-21"


def _args(chart):
    return {"dob": chart["dob"], "tob": chart["tob"], "place": chart["place"],
            "lat": chart["latitude"], "lon": chart["longitude"],
            "tz": chart["timezone"]}


@pytest.fixture(scope="module")
def gochara():
    r = A.get_nakshatra_gochara(current_date=WHEN, **_args(CHART1))
    assert r.get("status") == "success", r.get("error")
    return r


@pytest.fixture(scope="module")
def by_planet(gochara):
    return {g["planet"]: g for g in gochara["grahas"]}


# ── The shape ───────────────────────────────────────────────────────────────

def test_every_graha_is_present_and_ordered(gochara):
    names = [g["planet"] for g in gochara["grahas"]]
    assert names == ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus",
                     "Saturn", "Rahu", "Ketu"]


def test_no_bare_house_key_on_a_transit_row(by_planet):
    """A transit is counted from several references at once, so the payload
    contract forbids an unqualified `house` — it is the key that made readings
    place a graha in the wrong bhava (todo.md §63/§65)."""
    for g in by_planet.values():
        assert "house" not in g
        assert isinstance(g["house_from_lagna"], int)
        assert isinstance(g["house_from_moon"], int)


def test_the_moon_is_given_no_window_and_the_payload_says_why(gochara, by_planet):
    assert by_planet["Moon"]["window"] is None
    assert by_planet["Moon"]["upcoming"] == []
    assert "Moon" in gochara["no_window"]["planets"]
    assert gochara["no_window"]["reason"]


@pytest.mark.parametrize("planet", ["Sun", "Mars", "Mercury", "Jupiter",
                                    "Venus", "Saturn", "Rahu", "Ketu"])
def test_every_other_graha_gets_a_dated_window(by_planet, planet):
    """The class of bug this catches: a graha added to `_NAK_WINDOW_PLANETS`
    without an entry in `_NAK_SCAN_SPAN`, which would return a silent None."""
    w = by_planet[planet]["window"]
    assert w is not None, f"{planet} has no star window"
    assert w["leaves"], f"{planet} has no exit date"


# ── The windows are real ────────────────────────────────────────────────────

@pytest.mark.parametrize("planet", ["Sun", "Mars", "Jupiter", "Saturn", "Rahu"])
def test_the_window_contains_the_transit_date(by_planet, planet):
    w = by_planet[planet]["window"]
    if w.get("entered"):
        assert w["entered"] <= WHEN
    assert WHEN <= w["leaves"]


@pytest.mark.parametrize("planet", ["Sun", "Mars", "Jupiter", "Saturn", "Rahu"])
def test_upcoming_stars_run_forward_in_time_from_the_window(by_planet, planet):
    g = by_planet[planet]
    dates = [u["enters"] for u in g["upcoming"]]
    assert dates == sorted(dates), f"{planet}'s star calendar is out of order"
    if dates:
        # The first upcoming star begins exactly where this one ends; a gap would
        # mean the scan lost a span.
        assert dates[0] == g["window"]["leaves"]


def test_a_retrograde_reentry_is_a_step_backwards_through_the_stars(by_planet):
    """The flag exists because a graha turning back into the star it just left is
    a real ingress and a different story from the forward one. It must mean that
    and nothing else."""
    seen = False
    for g in by_planet.values():
        prev = g.get("nakshatra_index")
        for u in g.get("upcoming") or []:
            back = u["nakshatra_index"] == ((prev - 2) % 27) + 1
            assert u["retrograde_reentry"] == back, (
                f"{g['planet']} -> {u['nakshatra']}: flag {u['retrograde_reentry']} "
                f"but the step from {prev} is {'backwards' if back else 'forwards'}")
            seen = seen or back
            prev = u["nakshatra_index"]
    assert seen, "no retrograde re-entry anywhere in the window — the flag is untested"


def test_an_unknown_entry_date_is_reported_as_unknown_not_guessed(by_planet):
    """The first span starts at the edge of the scan, not at an ingress. Printing
    that edge as "entered" would be a fabricated date."""
    for g in by_planet.values():
        w = g.get("window")
        if w and not w["entered_known"]:
            assert w["entered"] is None
            assert w["days_in"] is None


# ── The scanner ─────────────────────────────────────────────────────────────

def test_the_arc_scanner_still_answers_the_sign_question_it_was_split_from():
    """`_planet_sign_spans` became the 30° case of `_planet_arc_spans`. Sade Sati
    is built on it, so the two must not have drifted apart."""
    import swisseph as swe
    jd = swe.julday(2026, 1, 1, 12.0)
    generic = A._planet_arc_spans(6, jd, jd + 900, 5.5, 30.0)
    specific = A._planet_sign_spans(6, jd, jd + 900, 5.5)
    assert generic == specific


def test_nakshatra_spans_tile_the_window_without_gaps_or_overlaps():
    import swisseph as swe
    jd = swe.julday(2026, 1, 1, 12.0)
    spans = A._nakshatra_spans(6, jd, jd + 900, 5.5)   # Saturn
    assert len(spans) > 1
    for (_, _, end), (_, nxt_start, _) in zip(spans, spans[1:]):
        assert end == nxt_start
    assert spans[0][1] == jd
    assert spans[-1][2] == jd + 900
    for nak0, _, _ in spans:
        assert 0 <= nak0 <= 26


def test_the_window_names_the_same_star_the_position_does(by_planet):
    """The star in `nakshatra` comes from the transit chart; the window comes
    from an independent longitude scan. Drift between them is the failure this
    whole feature would hide best."""
    for g in by_planet.values():
        if not g.get("window"):
            continue
        assert g["nakshatra"] == refdata.NAKSHATRA_NAMES[g["nakshatra_index"] - 1]


# ── The four personal hooks ─────────────────────────────────────────────────

def test_tarabala_is_the_count_from_this_native_s_birth_star(gochara, by_planet):
    janma = gochara["janma"]["nakshatra_index"]
    for g in by_planet.values():
        expected_name, expected_tone = _tarabala(janma, g["nakshatra_index"])
        assert g["tarabala"]["name"] == expected_name
        assert g["tarabala"]["tone"] == expected_tone
        assert g["tarabala"]["meaning"]


def test_upcoming_stars_carry_their_own_tarabala(gochara, by_planet):
    janma = gochara["janma"]["nakshatra_index"]
    for g in by_planet.values():
        for u in g.get("upcoming") or []:
            assert u["tarabala"] == _tarabala(janma, u["nakshatra_index"])[0]


def test_the_star_lord_is_the_vimsottari_lord_of_that_star(by_planet):
    for g in by_planet.values():
        assert g["nakshatra_lord"] == refdata.NAKSHATRA_LORD[g["nakshatra_index"] - 1]


def test_nodes_own_no_houses_and_everyone_else_owns_two_or_one(by_planet):
    for name, g in by_planet.items():
        if name in ("Rahu", "Ketu"):
            assert g["owns_houses"] == []
        else:
            assert 1 <= len(g["owns_houses"]) <= 2
            assert g["owns_houses"] == sorted(g["owns_houses"])


def test_dasha_emphasis_names_a_lord_that_is_actually_running(gochara, by_planet):
    """Emphasis says the transit is *live* for this chart. It may never claim a
    dasha link that the dasha block does not show."""
    running = {gochara["dasha"].get("maha"), gochara["dasha"].get("antar")}
    for g in by_planet.values():
        for line in g["emphasis"]:
            if "dasha lord" in line:
                assert any(lord and lord in line for lord in running), line


def test_natal_resonance_agrees_with_the_birth_chart(by_planet):
    """`natal_star` here and the nakshatra the birth chart reports are computed
    in different places; if they disagree, one of them is lying."""
    natal = A.get_nakshatra_profile(current_date=WHEN, **_args(CHART1))
    assert natal["status"] == "success"
    from_chart = {p["planet"]: p["nakshatra"] for p in natal["planetary_nakshatras"]}
    for name, g in by_planet.items():
        if name in from_chart:
            assert g["natal_resonance"]["natal_star"] == from_chart[name]
            assert g["natal_resonance"]["own_natal_star"] == (
                from_chart[name] == g["nakshatra"])


# ── The verdict is a rule, not a mood ───────────────────────────────────────

@pytest.mark.parametrize("chart", [CHART1, CHART2])
def test_the_verdict_is_a_pure_function_of_tarabala_and_the_grahas_nature(chart):
    """The spine of §75: tarabala tone, tilted one step by whether a natural
    malefic sits in a rough tara or a natural benefic in a kind one. Nothing
    else may move it — least of all the star's deity.

    Asserted by recomputing the label from those two inputs alone, across two
    charts so the stars and taras differ.
    """
    from astrology.engine import _SBC_MALEFICS, _SBC_BENEFICS
    r = A.get_nakshatra_gochara(current_date=WHEN, **_args(chart))
    assert r["status"] == "success"
    for g in r["grahas"]:
        score = A._NAK_SUPPORT_TONE.get(g["tarabala"]["tone"], 0)
        if g["planet"] in _SBC_MALEFICS and score < 0:
            score -= 1
        elif g["planet"] in _SBC_BENEFICS and score > 0:
            score += 1
        expected = ("supportive" if score >= 2
                    else "pressured" if score <= -2 else "mixed")
        assert g["support"] == expected, g["planet"]


def test_two_grahas_of_the_same_nature_in_the_same_tara_get_the_same_verdict():
    """The same statement as the test above, put the way a reader would notice it
    breaking: if the deity ever leaked into the verdict, two grahas alike in
    every input that is allowed to matter would start disagreeing."""
    seen = {}
    for chart in (CHART1, CHART2):
        r = A.get_nakshatra_gochara(current_date=WHEN, **_args(chart))
        from astrology.engine import _SBC_MALEFICS
        for g in r["grahas"]:
            key = (g["tarabala"]["tone"], g["planet"] in _SBC_MALEFICS)
            if key in seen:
                assert seen[key][1] == g["support"], (
                    f"{seen[key][0]} and {g['planet']} share tara tone "
                    f"{key[0]} and nature, but got {seen[key][1]} vs {g['support']}")
            else:
                seen[key] = (g["planet"], g["support"])


def test_symbolism_is_carried_but_kept_in_its_own_block(by_planet):
    """It must be present (a reading draws its language from it) and it must be
    separable (so the prompt can hand it over labelled as imagery)."""
    for g in by_planet.values():
        sym = g["symbolism"]
        assert set(sym) == {"deity", "symbol", "theme"}
        assert all(sym.values())
        i = g["nakshatra_index"] - 1
        assert sym["deity"] == refdata.NAKSHATRA_DEITY[i]
        assert sym["theme"] == refdata.NAKSHATRA_THEME[i]
        # None of the imagery may appear in the reasons the verdict gives.
        reasons = " ".join(g["support_reasons"]).lower()
        assert sym["deity"].lower() not in reasons


def test_every_support_reason_starts_from_a_real_tara(by_planet):
    taras = {name for name, _ in TARABALA_NAMES}
    for g in by_planet.values():
        assert g["support_reasons"]
        assert any(g["support_reasons"][0].startswith(tara) for tara in taras)


# ── Wiring ──────────────────────────────────────────────────────────────────

def test_the_tool_is_registered_and_dispatches():
    assert "get_nakshatra_gochara" in tool_registry.TOOLS
    r = tool_registry.dispatch("get_nakshatra_gochara", {"current_date": WHEN},
                               dict(CHART1))
    assert r["grahas"] and r["janma"]["nakshatra"]


def test_the_tool_hands_the_model_the_symbolism_under_a_name_that_disclaims_it():
    """The model sees this block; the key is the only thing stopping it being
    read as a rule, so the key is pinned."""
    r = tool_registry.dispatch("get_nakshatra_gochara", {"current_date": WHEN},
                               dict(CHART1))
    for g in r["grahas"]:
        assert "symbolism_not_a_rule" in g
        assert "symbolism" not in g


def test_the_tool_is_reachable_from_the_ai_catalog():
    cat = {t["name"]: t for t in tool_registry.tool_catalog()}
    assert "get_nakshatra_gochara" in cat
    assert cat["get_nakshatra_gochara"]["category"] == "Timing"
    assert cat["get_nakshatra_gochara"]["label"]
    assert "get_nakshatra_gochara" in tool_registry.SECTION_TOOL.values()


def test_the_prompt_declares_the_data_authoritative_and_the_imagery_optional():
    """A chakra reading once contradicted its own input because the numbers were
    merely offered to it, and the whole point of §75 is that a deity may not
    drive a prediction. Both guards live in the prompt text."""
    from llm_service import llm_service
    d = A.get_nakshatra_gochara(current_date=WHEN, **_args(CHART1))
    p = llm_service._build_nakshatra_gochara_prompt(d, "Asha")
    assert "AUTHORITATIVE" in p
    assert "IMAGERY ONLY (not a rule)" in p
    assert "Tarabala is the spine" in p
    # The dates are the point of the feature; they must reach the model.
    sat = next(g for g in d["grahas"] if g["planet"] == "Saturn")
    assert sat["window"]["leaves"] in p


# ── Determinism + bounds ────────────────────────────────────────────────────

def test_the_same_question_twice_gives_the_same_answer():
    a = A.get_nakshatra_gochara(current_date=WHEN, **_args(CHART1))
    b = A.get_nakshatra_gochara(current_date=WHEN, **_args(CHART1))
    assert a == b


def test_the_horizon_is_clamped_rather_than_trusted():
    """A caller-supplied horizon is bounded at both ends — the scan cost is
    linear in it. 0 and None both mean "unspecified" and take the default, which
    is the `or` idiom the route passes through."""
    for asked, expected in ((10, 90), (400, 400), (99999, 3660),
                            (0, 1100), (None, 1100)):
        r = A.get_nakshatra_gochara(current_date=WHEN, horizon_days=asked,
                                    **_args(CHART1))
        assert r["horizon_days"] == expected, asked


def test_a_longer_horizon_never_shortens_the_current_window():
    short = A.get_nakshatra_gochara(current_date=WHEN, horizon_days=90, **_args(CHART1))
    long = A.get_nakshatra_gochara(current_date=WHEN, horizon_days=3000, **_args(CHART1))
    s = {g["planet"]: g for g in short["grahas"]}
    for g in long["grahas"]:
        w1, w2 = s[g["planet"]].get("window"), g.get("window")
        if w1 and w2 and w1.get("entered") and w2.get("entered"):
            assert w1["entered"] == w2["entered"]


def test_the_exact_minute_is_honoured_so_the_moon_matches_the_transit_table():
    """§75 sits on the same page as the sign-level transit table, which anchors
    to the wall-clock minute. The Moon moves ~0.5 deg/hr, so computing this card
    at noon put it in a different star from the table directly above it — two
    cards on one page disagreeing about the Moon reads as a bug, because it is
    one. Both must answer for the same instant.
    """
    late = A.get_nakshatra_gochara(current_date=WHEN, current_time="22:56",
                                   current_tz=5.5, **_args(CHART1))
    table = A.get_transits(current_date=WHEN, current_time="22:56",
                           current_tz=5.5, **_args(CHART1))
    assert late["status"] == "success" and table["status"] == "success"
    assert late["transit_time"] == "22:56"
    for g in late["grahas"]:
        assert g["nakshatra"] == table["planets"][g["planet"]]["nakshatra"], g["planet"]


def test_without_a_time_it_still_answers_for_local_noon():
    r = A.get_nakshatra_gochara(current_date=WHEN, **_args(CHART1))
    assert r["transit_time"] == "12:00"


def test_upcoming_stars_carry_their_own_imagery(by_planet):
    """A model narrating "what changes next" will supply a deity from memory if
    it is not given one, and it gets them wrong — a live run called Uttara
    Bhadrapada's Ahir Budhnya "the Naga deities", which belongs to Ashlesha. The
    fix is data, not a prohibition, so the data has to actually be there."""
    for g in by_planet.values():
        for u in g.get("upcoming") or []:
            i = u["nakshatra_index"] - 1
            assert u["deity"] == refdata.NAKSHATRA_DEITY[i]
            assert u["theme"] == refdata.NAKSHATRA_THEME[i]


def test_the_prompt_hands_over_the_upcoming_stars_deities_too():
    from llm_service import llm_service
    d = A.get_nakshatra_gochara(current_date=WHEN, **_args(CHART1))
    p = llm_service._build_nakshatra_gochara_prompt(d, "Asha")
    sat = next(g for g in d["grahas"] if g["planet"] == "Saturn")
    nxt = sat["upcoming"][0]
    assert nxt["deity"] in p, "the next star's deity never reaches the model"
    assert "Do not name a deity, symbol or theme from memory" in p
