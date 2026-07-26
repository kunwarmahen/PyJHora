"""Golden-value regression tests for AstrologyCompute (§3.2).

These pin the engine's output for two fixed charts so any drift — a PyJHora
version bump, an ayanamsa/node default change, a refactor of astrology.py — is
caught immediately. The chart-1 numbers were cross-checked against Jagannatha
Hora (todo §26) with the app's matched defaults (True Chitra + mean nodes), and
re-verified in §11.3 once chart 1's coordinates were corrected: every planet now
matches JHora to 0.01" and the ascendant to 11".

Longitudes are asserted to ±0.02° (the API rounds degrees to 2 dp); signs, D9
placements, dasha boundary dates and panchanga limbs are asserted exactly.
"""
import pytest

from astrology import AstrologyCompute as A

DEG_TOL = 0.02

# ── Chart 1 (owner, JHora-verified) ─────────────────────────────────────────
# 25 Ta 03' 36" — Jagannatha Hora prints 25 Ta 04' 23.79" for the same chart,
# an 11" agreement. (This read 24.83 while conftest held the wrong coordinates.)
CHART1_LAGNA = ("Taurus", 25.06)
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


def test_kota_chakra(args1):
    """§2.7 Kota Chakra — the fort, ported from the engine's PyQt-only widget.

    Pins the layout invariants (so the port can't silently drift from JHora) and
    the two defenders, which are derived independently of the grid.
    """
    r = A.get_kota_chakra(**args1, current_date="2026-07-16")
    assert r.get("status") == "success", r

    # Chart 1: Moon in Leo, Magha pada 1.
    assert r["birth_star"] == {"number": 10, "name": "Magha", "pada": 1}
    assert r["moon_sign"] == "Leo"
    # Kota Swami = lord of the Moon's sign (Leo -> Sun); Paala from the star/pada table.
    assert r["kota_lord"] == "Sun"
    assert r["kota_paala"] == "Saturn"

    # Four enclosures, 8/8/8/4 = all 28 stars, each exactly once.
    assert [ring["key"] for ring in r["rings"]] == \
        ["baahya", "praakaara", "durgantara", "sthamba"]
    assert [len(ring["cells"]) for ring in r["rings"]] == [8, 8, 8, 4]
    stars = [c["star"] for ring in r["rings"] for c in ring["cells"]]
    assert len(stars) == 28
    assert len(set(stars)) == 28, "a star is duplicated in the fort"
    assert "Abhijit" in stars, "the 28-star order must include Abhijit"

    # The fort is counted FROM the janma nakshatra, so it anchors the outer wall.
    assert r["rings"][0]["cells"][0]["star"] == "Magha"

    # Every graha lands somewhere; Abhijit is a cell but never occupied (planets
    # only ever carry a 1-27 nakshatra).
    placed = [p["name"] for ring in r["rings"] for c in ring["cells"] for p in c["transit"]]
    assert sorted(placed) == sorted(
        ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"])
    for ring in r["rings"]:
        for c in ring["cells"]:
            if c["star"] == "Abhijit":
                assert c["transit"] == [] and c["natal"] == []

    # Malefics are flagged as such, and reaching the inner rings reads as stressful.
    saturn = next(p for ring in r["rings"] for c in ring["cells"]
                  for p in c["transit"] if p["name"] == "Saturn")
    assert saturn["malefic"] is True


def test_tripataki_chakra(args1):
    """§2.7 Tripataki — the twelve rasis on the three-banner diagram.

    The engine only ever shipped this as a drawing, so what's pinned is the
    layout contract + that grahas land on the right signs (no invented verdict).
    """
    r = A.get_tripataki_chakra(**args1, current_date="2026-07-16")
    assert r.get("status") == "success", r
    assert r["natal_lagna"] == "Taurus"
    assert len(r["cells"]) == 12
    assert len({c["sign_name"] for c in r["cells"]}) == 12, "each rasi appears once"
    assert len(r["lines"]) == 18, "the three pataki lines flatten to 18 segments"

    # Perimeter layout is fixed: Aries at (1,3), Taurus at (1,4), … (engine table).
    aries = next(c for c in r["cells"] if c["sign_name"] == "Aries")
    assert (aries["x"], aries["y"]) == (1, 3)
    # Taurus lagna -> its cell is flagged and is house 1.
    lagna = [c for c in r["cells"] if c["is_lagna"]]
    assert len(lagna) == 1
    assert lagna[0]["sign_name"] == "Taurus" and lagna[0]["house_from_lagna"] == 1

    # Grahas plot on the sign they occupy (cross-checked against the transit test).
    by_sign = {c["sign_name"]: [p["name"] for p in c["transit"]] for c in r["cells"]}
    assert by_sign["Pisces"] == ["Saturn"]
    assert by_sign["Aquarius"] == ["Rahu"]
    assert "Sun" in by_sign["Gemini"]
    placed = sorted(p for v in by_sign.values() for p in v)
    assert len(placed) == 9, "all nine grahas plotted"


def test_tripataki_vedha_rules():
    """The Tajaka vedha rules the Tripataki reading is built on.

    Sourced rules: movable <-> dual except the dual in the 3rd from it; fixed <->
    fixed; dual <-> movable except the movable in the 11th from it. The two
    exclusions describe the SAME four pairs from both ends, so the map must come
    out symmetric with exactly three partners per sign — that reciprocity is the
    strongest check that the rules are transcribed right, so assert it.
    """
    from astrology.engine import (TRIPATAKI_VEDHA, MOVABLE_SIGNS, FIXED_SIGNS,
                                  DUAL_SIGNS, sign_class)

    # Vedha is mutual obstruction — the map must be symmetric.
    for s, partners in TRIPATAKI_VEDHA.items():
        for p in partners:
            assert s in TRIPATAKI_VEDHA[p], f"{s}->{p} not reciprocated"
        assert s not in partners, "a sign cannot vedha itself"
        assert len(partners) == 3, f"sign {s} has {len(partners)} vedha partners, expected 3"

    # Movable only ever meets dual, fixed only fixed, dual only movable.
    for m in MOVABLE_SIGNS:
        assert all(p in DUAL_SIGNS for p in TRIPATAKI_VEDHA[m])
    for f in FIXED_SIGNS:
        assert set(TRIPATAKI_VEDHA[f]) == set(FIXED_SIGNS) - {f}
    for d in DUAL_SIGNS:
        assert all(p in MOVABLE_SIGNS for p in TRIPATAKI_VEDHA[d])

    # The excluded pairs: each movable and the dual 3 signs on (its 3rd).
    for m, excluded in ((0, 2), (3, 5), (6, 8), (9, 11)):   # Ar-Ge, Cn-Vi, Li-Sg, Cp-Pi
        assert excluded not in TRIPATAKI_VEDHA[m]
        assert m not in TRIPATAKI_VEDHA[excluded]

    assert sign_class(0) == "movable" and sign_class(1) == "fixed" and sign_class(2) == "dual"


def test_tripataki_vedha_reading(args1):
    """The vedha actually read off chart 1 for the fixed transit date."""
    r = A.get_tripataki_chakra(**args1, current_date="2026-07-16")
    assert r["natal_lagna"] == "Taurus" and r["transit_moon"] == "Cancer"

    by_target = {v["target"]: v for v in r["vedha"]}

    # Moon in Cancer is movable -> obstructed from the duals EXCEPT Virgo (its 3rd).
    moon = by_target["Moon"]
    assert moon["sign_class"] == "movable"
    assert moon["vedha_signs"] == ["Gemini", "Pisces", "Sagittarius"]
    assert "Virgo" not in moon["vedha_signs"]

    # Lagna in Taurus is fixed -> obstructed from the other fixed signs only.
    lagna = by_target["Lagna"]
    assert lagna["sign_class"] == "fixed"
    assert lagna["vedha_signs"] == ["Aquarius", "Leo", "Scorpio"]

    # Every obstructing graha must actually sit on one of the vedha signs.
    for v in r["vedha"]:
        for h in v["obstructed_by"]:
            assert h["from_sign"] in v["vedha_signs"]
        assert v["tone"] in ("stressful", "supportive", "clear")


def test_tripataki_annual_basis(args1):
    """basis="annual" reads the Varshaphal (solar-return) chart, not the moment.

    Guards the engine quirk shared with get_varshaphal (varsha_pravesh years=N
    lands in birth_year+N-1, so the chart for `year` needs age+1) and the fact
    that the *annual* Lagna — not the natal one — is what gets judged.
    """
    a = A.get_tripataki_chakra(**args1, basis="annual", year=2026)
    assert a.get("status") == "success", a
    assert a["basis"] == "annual"
    # Chart 1's birthday is 4 June, so the 2026 solar return falls right there.
    assert a["transit_date"].startswith("2026-06"), a["transit_date"]
    # The annual Lagna differs from the natal Taurus — proving we judged the
    # varsha chart rather than silently reusing the natal one.
    assert a["natal_lagna"] == "Pisces"
    assert a["transit_moon"] == "Capricorn"

    by_target = {v["target"]: v for v in a["vedha"]}
    # Pisces is dual -> obstructed from the movables EXCEPT Capricorn (its 11th).
    assert by_target["Lagna"]["sign_class"] == "dual"
    assert by_target["Lagna"]["vedha_signs"] == ["Aries", "Cancer", "Libra"]
    # Capricorn is movable -> from the duals EXCEPT Pisces (its 3rd).
    assert by_target["Moon"]["sign_class"] == "movable"
    assert by_target["Moon"]["vedha_signs"] == ["Gemini", "Sagittarius", "Virgo"]

    # Transit basis is unchanged and still natal-Lagna based.
    t = A.get_tripataki_chakra(**args1, current_date="2026-07-16")
    assert t["basis"] == "transit" and t["natal_lagna"] == "Taurus"

    assert A.get_tripataki_chakra(**args1, basis="nonsense").get("status") == "failed"
    assert A.get_tripataki_chakra(**args1, basis="annual", year=1900).get("status") == "failed"


def test_kaala_chakra(args1):
    """§2.7 Kaala Chakra — the wheel of directions, ported from the PyQt widget.

    Pins the layout contract (4 inner + 8x3 outer = all 28 stars once) and the
    base star, which is derived independently of the wheel.
    """
    r = A.get_kaala_chakra(**args1, current_date="2026-07-16")
    assert r.get("status") == "success", r

    # Base star is the natal SUN's nakshatra (the engine's D1 rule). Chart 1's
    # Sun sits at Taurus 20deg -> Rohini.
    assert r["base_star"]["from"] == "Sun"
    assert r["base_star"]["name"] == "Rohini"

    # 4 inner + 8 directions x 3 = 28 stars, each exactly once.
    assert len(r["inner"]) == 4
    assert len(r["directions"]) == 8
    stars = [c["star"] for c in r["inner"]] + \
            [c["star"] for d in r["directions"] for c in d["cells"]]
    assert len(stars) == 28 and len(set(stars)) == 28
    assert "Abhijit" in stars

    # The engine's direction order + angles, kept verbatim so the wheel matches
    # desktop JHora (note its own orientation: 90deg is labelled East).
    assert [d["direction"] for d in r["directions"]] == [
        "Southeast", "East", "Northeast", "North",
        "Northwest", "West", "Southwest", "South"]
    assert [d["angle"] for d in r["directions"]] == [45, 90, 135, 180, 225, 270, 315, 360]

    # Every graha is placed exactly once; Abhijit's cell stays empty because a
    # graha only ever carries a 1-27 star (the slot-shift guarantees it).
    placed = [p["name"] for c in r["inner"] for p in c["planets"]] + \
             [p["name"] for d in r["directions"] for c in d["cells"] for p in c["planets"]]
    assert sorted(placed) == sorted(
        ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"])
    for d in r["directions"]:
        for c in d["cells"]:
            if c["star"] == "Abhijit":
                assert c["planets"] == []

    # Tone follows the occupants, and the summaries agree with the tones.
    for d in r["directions"]:
        if d["malefics"] and not d["benefics"]:
            assert d["tone"] == "stressful"
        elif d["benefics"] and not d["malefics"]:
            assert d["tone"] == "supportive"
        elif not d["malefics"] and not d["benefics"]:
            assert d["tone"] == "clear"
        else:
            assert d["tone"] == "mixed"
    assert r["avoid"] == [d["direction"] for d in r["directions"] if d["tone"] == "stressful"]


def test_kaala_star_slot_abhijit_shift():
    """A 1-27 nakshatra maps onto the 28-star order with Abhijit spliced in."""
    from astrology.engine import kaala_star_slot
    # Before Abhijit (index 21 of 1..28): unchanged, just 0-based.
    assert kaala_star_slot(1) == 0
    assert kaala_star_slot(21) == 20
    # At/after it: shifted up one to make room for Abhijit's slot (21).
    assert kaala_star_slot(22) == 22
    assert kaala_star_slot(27) == 27
    # Abhijit's own slot is never produced from a real graha's star.
    assert 21 not in {kaala_star_slot(n) for n in range(1, 28)}


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


# ── Nadi karaka reading ─────────────────────────────────────────────────────
def test_nadi_karakas_and_conjunctions(args1):
    """The karaka significators read by sign: Venus in its own Taurus with the
    Sun and Mercury, Saturn in Cancer with Mars, Jupiter in Aries with Ketu —
    and each graha signifies its occupied + owned + star-lord's signs."""
    r = A.get_nadi_reading(**args1)
    assert r.get("status") == "success", r
    assert len(r["karakas"]) == 9
    kb = {k["planet"]: k for k in r["karakas"]}

    venus = kb["Venus"]
    assert venus["sign_name"] == "Taurus"
    assert venus["sign_lord"] == "Venus"          # own sign → self-dispositor
    assert set(venus["conjunct"]) == {"Sun", "Mercury"}
    # Signifies its occupied sign + the other sign it owns (Libra).
    assert "Taurus" in venus["signifies_signs"]
    assert "Libra" in venus["signifies_signs"]

    assert kb["Saturn"]["sign_name"] == "Cancer"
    assert kb["Saturn"]["conjunct"] == ["Mars"]
    assert kb["Jupiter"]["sign_name"] == "Aries"
    assert kb["Jupiter"]["conjunct"] == ["Ketu"]
    assert kb["Moon"]["conjunct"] == []            # Moon alone in Leo


def test_nadi_spouse_karaka_gender(args1):
    """The spouse karaka to foreground flips with gender: Venus (wife-karaka)
    for a man, Jupiter (husband-karaka) for a woman; default is Venus."""
    assert A.get_nadi_reading(**args1)["spouse_karaka"] == "Venus"
    assert A.get_nadi_reading(gender=0, **args1)["spouse_karaka"] == "Venus"
    assert A.get_nadi_reading(gender=1, **args1)["spouse_karaka"] == "Jupiter"


def test_nadi_themes_and_triggers(args1):
    """Nine life themes, each headed by its karaka (marriage carries both spouse
    karakas), and transit triggers only from the slow movers into pivot signs."""
    r = A.get_nadi_reading(**args1)
    assert len(r["themes"]) == 9
    marriage = next(t for t in r["themes"] if "Marriage" in t["area"])
    assert [k["planet"] for k in marriage["karakas"]] == ["Venus", "Jupiter"]

    assert r["triggers"], "expected at least one transit trigger"
    for tr in r["triggers"]:
        assert tr["planet"] in {"Jupiter", "Saturn", "Rahu"}
        # ISO date, and sorted ascending.
        assert len(tr["date"]) == 10 and tr["date"][4] == "-"
    dates = [tr["date"] for tr in r["triggers"]]
    assert dates == sorted(dates)


# JHora's Shashtihayani maha dasas for chart 1, run under Lahiri (todo §52.1).
# Times dropped — we compare dates, and the residual is a few hours.
CHART1_SHASHTIHAYANI = [
    ("Mars",    "1969-07-29"),
    ("Moon",    "1979-07-29"),
    ("Mercury", "1985-07-29"),
    ("Venus",   "1991-07-29"),
    ("Saturn",  "1997-07-29"),
    ("Rahu",    "2003-07-29"),
    ("Jupiter", "2009-07-29"),
    ("Sun",     "2019-07-29"),
]


def test_shashtihayani_matches_jhora(args1):
    """Shashtihayani's balance at birth, against Jagannatha Hora (todo §52.1).

    PyJHora's `shastihayani._dhasa_start` divides the elapsed arc by ONE nakshatra,
    the Vimsottari rule. But Shashtihayani gives each lord a *contiguous block* of
    stars, so the balance is the fraction through the whole block — what
    `ashtottari.py` already does. On this chart the Moon is in the third of Mars's
    three stars, so the engine reported 5.6% elapsed where the truth is 68.6%:
    every period landed 6.3 years late. This pins the corrected phase.
    """
    r = A.get_dasha_periods("shashtihayani", ayanamsa="LAHIRI", **args1)
    assert r.get("status") == "success", r
    got = [(p["lord"], p["start_date"]) for p in r["periods"][:8]]
    assert [g[0] for g in got] == [e[0] for e in CHART1_SHASHTIHAYANI]

    from datetime import date
    for (lord, ours), (_, theirs) in zip(got, CHART1_SHASHTIHAYANI):
        delta = abs((date.fromisoformat(ours) - date.fromisoformat(theirs)).days)
        # Sub-day: what is left is the ayanamsa implementations differing by ~0.2',
        # i.e. ~8 hours over a ten-year period. The old bug was 2,300 days.
        assert delta <= 1, f"{lord}: ours {ours} vs JHora {theirs}"

    assert [p["duration_years"] for p in r["periods"][:8]] == [10, 6, 6, 6, 6, 6, 10, 10]


def test_dasha_periods_honour_the_ayanamsa(args1):
    """The setting must reach the computation — nakshatra dashas are read off the
    Moon's sidereal longitude, and this compute used to ignore `ayanamsa` entirely
    and always answer in True Chitra."""
    lahiri = A.get_dasha_periods("shashtihayani", ayanamsa="LAHIRI", **args1)
    citra = A.get_dasha_periods("shashtihayani", ayanamsa="TRUE_CITRA", **args1)
    assert lahiri["periods"][0]["start_date"] != citra["periods"][0]["start_date"]
