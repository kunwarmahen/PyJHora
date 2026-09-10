"""The claim checker: what the model said vs what the chart computes (§68.1).

The bug class this guards is four sections old — §63 read a drawing coordinate as
a house, §64 reasoned over Sahams that had been empty for months, §65 had one key
meaning two things, §67 said "the 9th house is ruled by Jupiter" when the 9th
here is Capricorn. Every one reached a finished reading and was caught by a human.

Two halves, and the first matters more:

  • **Precision.** A false alarm costs a regeneration and puts a warning under
    someone's reading, so the true-and-tricky corpus below is the real test. Each
    line is either true for CHART1 or is not a claim about it at all — a textbook
    aside, a varga, a transit, a hypothetical — and any of them being flagged is
    a bug in the rules, not in the model.

  • **Recall**, including the four historical slips verbatim.
"""
import asyncio

import pytest

import chart_context
import claim_check as cc
from astrology import AstrologyCompute

from .conftest import CHART1, _compute_args

AYAN = "TRUE_CITRA"
BD1 = {"dob": CHART1["dob"], "tob": CHART1["tob"], "place": CHART1["place"],
       "latitude": CHART1["latitude"], "longitude": CHART1["longitude"],
       "timezone": CHART1["timezone"]}


@pytest.fixture(scope="module")
def ctx():
    return chart_context.build_chart_context(BD1, ayanamsa=AYAN)


@pytest.fixture(scope="module")
def facts(ctx):
    return cc.build_facts(ctx)


# ── The truth table ─────────────────────────────────────────────────────────

def test_facts_agree_with_the_engine(facts):
    """Built from the context the model is handed, checked against a *different*
    compute call — so a contradiction is genuinely internal to the prompt."""
    engine = {h["house"]: h["lord"]
              for h in AstrologyCompute.get_friendships(
                  ayanamsa=AYAN, **_compute_args(CHART1))["house_lords"]}
    assert facts.house_lord == engine
    # The owner's chart, pinned (Taurus lagna) — the §67 case.
    assert facts.house_lord[9] == "Saturn"
    assert facts.house_sign[9] == "Capricorn"
    assert facts.lords_of["Jupiter"] == [8, 11]
    assert facts.planet_house["Jupiter"] == 12
    assert facts.planet_sign["Jupiter"] == "Aries"


def test_dignity_is_derived_not_asserted(facts):
    """Exaltation needs no extra section and no compute call — the sign fixes it."""
    assert facts.dignity["Mars"] == "debilitated"   # Cancer
    assert facts.dignity["Venus"] == "own"          # Taurus
    assert "Sun" not in facts.dignity               # Taurus: neither
    # Rahu/Ketu are deliberately absent: the classical sources disagree and
    # EXALTATION_SIGN omits them, so no claim about them is ever judged.
    assert "Rahu" not in facts.dignity and "Ketu" not in facts.dignity


def test_flags_are_none_when_the_section_is_off():
    """"No information" and "no flag" must not collapse into each other, or every
    combust claim is contradicted for free the moment someone toggles a section."""
    bare = chart_context.build_chart_context(
        BD1, ayanamsa=AYAN,
        sections={k: False for k in chart_context.DEFAULT_SECTIONS})
    assert cc.build_facts(bare).flags is None
    assert cc.check("Venus is combust.", cc.build_facts(bare))["contradictions"] == []


def test_house_rulers_rebuilt_from_the_lagna_alone():
    """A context saved before §67 has no `house_rulers`; the lagna is enough."""
    facts = cc.build_facts({"lagna": {"sign_name": "Taurus"},
                            "planetary_positions": {}})
    assert facts.house_lord[9] == "Saturn"
    assert facts.house_sign[1] == "Taurus"


# ── Precision: none of these may ever be flagged ────────────────────────────

TRUE_OR_NEUTRAL = [
    # True of CHART1.
    "Jupiter, lord of the 8th and 11th, sits in the 12th house in Aries.",
    "Saturn, the karaka of longevity and discipline, is in the 3rd house.",
    "The 9th house is Capricorn, so its lord is Saturn.",
    "The 9th lord is Saturn and the 9th house is Capricorn.",
    "The 10th lord Saturn sits in the 3rd, in Cancer.",
    "Mercury and Venus are both in Taurus in the 1st house.",
    "Mars is debilitated in Cancer, in the 3rd house.",
    "The Moon is in Magha, whose lord is Ketu.",
    "The Ascendant is Taurus at 25 degrees, in Mrigashira nakshatra.",
    "Ketu occupies the 12th house in Aries.",
    "The chart shows Venus combust, within a degree of the Sun.",
    # Not claims about this chart at all.
    "Jupiter gives good results in the 5th house for Taurus natives.",
    "The Moon in the 4th house is a classical placement for domestic comfort.",
    "People with Ketu in the 12th often report vivid dreams.",
    "Venus is not in the 7th house here.",
    "Mars aspects the 6th house from its position.",
    "In D9 the Sun moves to the 7th house.",
    "In the Navamsa, Jupiter is in the 5th house.",
    "Saturn transits the 10th house through 2027.",
    "Saturn will enter the 5th house in the first half of 2027.",
    "The 3rd house from the Moon holds Rahu.",
    "Were Mercury in Virgo, it would be exalted.",
    "If Mars were in the 7th house, this would be a Manglik chart.",
    "The dasha of Jupiter ran through the first half of 2019.",
    "Your Saturn return arrives in the 3rd week of June 2035.",
    "Rahu is retrograde by nature, as always.",
    "Guru Chandala yoga does not form here.",
]


@pytest.mark.parametrize("line", TRUE_OR_NEUTRAL)
def test_no_false_alarms(line, facts):
    report = cc.check(line, facts)
    assert report["contradictions"] == [], (
        f"false alarm on a true/neutral line: {line}\n{report['contradictions']}")


def test_rahu_retrograde_is_never_judged(facts):
    """The engine flags retrogression only for the five tara-grahas — Rahu and
    Ketu are Mean nodes, so perpetually retrograde and deliberately unflagged.
    Checking a Rahu claim against that would manufacture a contradiction out of
    a convention."""
    assert cc.check("Rahu is retrograde.", facts)["contradictions"] == []
    assert cc.check("Saturn is retrograde.", facts)["contradictions"]


# ── Recall: the four historical slips, verbatim ─────────────────────────────

def test_the_sixty_seven_sentence(facts):
    """The Life Report chapter that started this: correct data in the context,
    and the model's prior beat it."""
    said = ("The 9th house of fortune and dharma is ruled by Jupiter, "
            "placed in the 12th in Aries.")
    found = cc.check(said, facts)["contradictions"]
    assert len(found) == 1
    assert found[0]["kind"] == "lordship"
    assert "the 9th lord is Saturn" in found[0]["truth"]
    assert "Capricorn" in found[0]["truth"]
    # It names what Jupiter *does* rule, so the retry has somewhere to go.
    assert "8th and 11th" in found[0]["truth"]


@pytest.mark.parametrize("said,kind", [
    ("Mars is in the 5th house, driving sibling conflict.", "placement_house"),
    ("Mercury is in Virgo, which sharpens the intellect.", "placement_sign"),
    ("The 4th lord is Jupiter.", "lordship"),
    ("The 9th house is Sagittarius.", "house_sign"),
    ("Mercury is retrograde in this chart.", "condition"),
    ("Mercury is exalted, giving a fine analytical mind.", "dignity"),
    ("The Moon is in Rohini nakshatra.", "nakshatra"),
])
def test_each_claim_kind_is_caught(said, kind, facts):
    found = cc.check(said, facts)["contradictions"]
    assert [c["kind"] for c in found] == [kind], f"{said} -> {found}"


def test_a_repeated_slip_is_reported_once(facts):
    text = ("Mars is in the 5th house. Mars in the 5th house colours the whole "
            "chart. Again, Mars is in the 5th house.")
    assert len(cc.check(text, facts)["contradictions"]) == 1


def test_markdown_emphasis_does_not_hide_a_claim(facts):
    assert cc.check("**Mars** is in the *5th house*.", facts)["contradictions"]


def test_sanskrit_names_are_understood(facts):
    """Models reach for these, and a name we do not parse is a claim we do not
    check — a silent hole rather than a visible one."""
    assert cc.check("Kuja is in the 5th house.", facts)["contradictions"]
    assert cc.check("Guru is in Kanya.", facts)["contradictions"]
    assert cc.check("Chandra is in Moola nakshatra.", facts)["contradictions"]


# ── The rules that keep precision high ──────────────────────────────────────

# ── The "Nth Lord (Planet)" family, from the first live run ─────────────────
# Every sentence here is real output from gemma4:12b on the owner's chart, and
# every one was reported as a contradiction by the first cut of these rules. The
# lord word comes *after* the ordinal, where the gap between two anchors cannot
# see it, so "the 1st Lord (Venus) and 2nd Lord (Mercury) are both placed in the
# 1st house" read as "Venus is in the 2nd house". Models write this constantly.

LIVE_TRUE_SENTENCES = [
    ("Because the 1st Lord (Venus) and 2nd Lord (Mercury) are both placed in the "
     "1st house, your personal identity and your resources/values are deeply "
     "intertwined."),
    ("Since the 10th Lord (Saturn) and 9th Lord (Saturn) are located here, your "
     "career and fortune are tied to your personal efforts and initiatives."),
    "*   **The 12th House Placement:** Jupiter (11th Lord) and Ketu are in the 12th house.",
    # The lord word can sit behind a *list* of ordinals.
    ("*   **Conjunction in the 1st House:** The presence of the Sun (4th lord), "
     "Mercury (2nd & 5th lord), and Venus (1st & 6th lord) in the 1st house "
     "creates a strong persona."),
    ("*   **The 3rd House Cluster:** The 3rd house (effort, courage, siblings) is "
     "occupied by both Mars (7th & 12th lord) and Saturn (9th & 10th lord)."),
    "Jupiter is the 8th and 11th lord.",
    # A glossing aside between the ordinals and the lord word.
    "*   **Saturn (Cancer, 3rd House, Pushya):** Saturn is the 9th (fortune) and 10th (career) lord.",
    # "Lagna Lord" is a phrase for the 1st lord, not a claim that the Lagna rules.
    "*   **Venus (Taurus, 1st House, Rohini):** Venus is the **Lagna Lord** (1st) and is placed in its **Own Sign (Taurus)**.",
    # A comma-list of houses after a subject the first item already refused.
    "*   **Sareera Soukhya Yoga:** Your Lagna Lord (Venus), Jupiter, and Venus are in Kendra houses (1st, 10th, 11th).",
    # A house named with its lord in parentheses, twice in one sentence.
    "Your career is governed by the 10th house (Saturn) and the 1st house (Venus).",
    # A slash-joined list of lordships, and one of houses.
    "With your Lagna Lord (Venus) and 2nd/5th Lords (Mercury) in the 1st house, you are the brand.",
    "**Mercury:** To strengthen your 1st/5th house influence, engage in writing or public speaking.",
    # A lord word behind two glossed ordinals, then a real placement.
    "Mercury is the 2nd (wealth/speech) and 5th (intellect/creativity) lord, placed in the 1st house.",
    # The lord belongs to ITS house, not to whichever house is named next.
    "As the 4th lord (home/happiness) in the 1st, the Sun bestows a persona of authority.",
    # An axis names a pair of houses and places nothing.
    "Rahu & Ketu (6th/12th Axis): the nodes drive this chart.",
    # An unnamed lord is the subject of what follows it.
    "With Rahu in the 6th (house of obstacles) and your 6th lord in the 1st, you overcome much.",
    "Due to the Rahu Mahadasha and the Debilitated 7th Lord, do not rush into a decision.",
    # A sign leading its own planet.
    "the Taurus Lagna, the Leo Moon, and the potent planetary cluster in the 1st House.",
    # A list of "(Planet)" items, each closed off before the next.
    ("**Sareera Soukhya Yoga:** Your Lagna Lord (Venus), the 9th/10th Lord "
     "(Saturn), and the 11th Lord (Jupiter) are in significant positions."),
]


@pytest.mark.parametrize("line", LIVE_TRUE_SENTENCES)
def test_the_lord_after_the_ordinal_is_not_a_placement(line, facts):
    assert cc.check(line, facts)["contradictions"] == []


def test_that_phrasing_still_yields_its_lordships(line=LIVE_TRUE_SENTENCES[0]):
    """Not merely un-flagged — correctly *understood*. Suppressing the false
    alarm by refusing to parse the sentence would have passed the test above and
    quietly halved the checker's coverage."""
    claims = {(c.kind, c.subject, c.value) for c in cc.extract_claims(line)}
    assert ("lordship", 1, "Venus") in claims
    assert ("lordship", 2, "Mercury") in claims


def test_a_lord_word_is_not_inherited_by_the_next_planet_in_a_list(facts):
    """"Jupiter (11th Lord) and Ketu" made Ketu the 11th lord too, because the
    consumed lord word was still sitting in the next anchor's gap."""
    claims = [(c.kind, c.subject, c.value)
              for c in cc.extract_claims(
                  "Jupiter (11th Lord) and Ketu are in the 12th house.")]
    assert ("lordship", 11, "Jupiter") in claims
    assert ("lordship", 11, "Ketu") not in claims


def test_a_list_of_ordinals_shares_one_lord():
    """"Mercury (2nd & 5th lord)" is two lordships, not a placement in the 2nd —
    and "Jupiter is the 8th and 11th lord" is two more. Both were live output."""
    assert {(c.kind, c.subject, c.value)
            for c in cc.extract_claims("Mercury (2nd & 5th lord) sits here.")} \
        >= {("lordship", 2, "Mercury"), ("lordship", 5, "Mercury")}
    assert {(c.kind, c.subject, c.value)
            for c in cc.extract_claims("Jupiter is the 8th and 11th lord.")} \
        == {("lordship", 8, "Jupiter"), ("lordship", 11, "Jupiter")}


def test_a_wrong_lord_in_a_list_is_still_caught(facts):
    found = cc.check("Jupiter is the 4th and 6th lord.", facts)["contradictions"]
    assert {c["said"] for c in found} == {"the 4th lord is Jupiter",
                                          "the 6th lord is Jupiter"}


def test_a_wrong_lord_in_that_phrasing_is_still_caught(facts):
    """The suppression must not be a blanket one.

    Only the lordship is checked here, not "sits in the 5th": the placement's gap
    crosses a closing parenthesis, and a subject inside parentheses is an aside
    rather than the sentence's subject ("the 10th house (Saturn) and the 1st
    house (Venus)" does not put Saturn in the 1st). That rule costs a few true
    claims and removes a whole family of false ones."""
    found = cc.check("The 9th Lord (Jupiter) sits in the 5th.", facts)["contradictions"]
    assert {c["kind"] for c in found} == {"lordship"}


def test_the_lagna_rules_nothing(facts):
    """The Lagna is not a graha. "Venus is the Lagna Lord (1st)" is correct
    English and must not be read as the *Lagna* ruling the 1st house."""
    assert cc.check("Venus is the Lagna Lord (1st).", facts)["contradictions"] == []


def test_an_aside_between_the_ordinals_and_the_lord_word(facts):
    claims = {(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "Saturn is the 9th (fortune) and 10th (career) lord.")}
    assert claims == {("lordship", 9, "Saturn"), ("lordship", 10, "Saturn")}
    assert cc.check("Saturn is the 5th (children) and 6th (debts) lord.",
                    facts)["contradictions"]


def test_a_house_naming_its_own_sign_is_its_own_clause(facts):
    """"The 1st lord is Mars, and the 1st house is Aries" is two statements, and
    the second is about the house — not about Mars being in it."""
    claims = {(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "The 9th lord is Saturn, and the 9th house is Capricorn.")}
    assert ("placement_house", "Saturn", 9) not in claims
    assert ("house_sign", 9, "Capricorn") in claims


def test_a_house_list_does_not_reach_back_past_a_planet(facts):
    """"the 1st Lord (Venus) and 2nd Lord (Mercury)" — the 2nd is Mercury's, not
    Venus's. The list rule that lets "the 8th and 11th" share a lord must not."""
    claims = {(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "The 1st Lord (Venus) and 2nd Lord (Mercury) are both here.")}
    assert ("lordship", 2, "Mercury") in claims
    assert ("lordship", 2, "Venus") not in claims


def test_a_parenthetical_subject_does_not_reach_the_next_house(facts):
    """"the 10th house (Saturn) and the 1st house (Venus)" names two lords; it
    does not put Saturn in the 1st."""
    assert not [c for c in cc.extract_claims(
        "Your career is governed by the 10th house (Saturn) and the 1st house (Venus).")
        if c.kind == "placement_house"]


def test_a_slash_joins_a_list_like_and(facts):
    """"your 1st/5th house influence" is one list, not a placement in the 5th."""
    assert cc.extract_claims(
        "**Mercury:** To strengthen your 1st/5th house influence, write more.") == []
    claims = {(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "The 2nd/5th Lords (Mercury) sit here.")}
    assert ("lordship", 5, "Mercury") in claims


def test_a_pending_lord_keeps_its_own_house():
    """"As the 4th lord … in the 1st, the Sun …" makes the Sun the 4th lord. It
    came out as the 1st lord while the pending slot was a single value that a
    later house could overwrite."""
    assert {(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "As the 4th lord (home/happiness) in the 1st, the Sun bestows authority.")} \
        == {("lordship", 4, "Sun")}


def test_a_run_of_lordless_houses_shares_one_lord():
    """"The 2nd/5th Lords (Mercury)" is two lordships. Keeping only the first or
    only the last silently halved the sentence."""
    assert {(c.kind, c.subject, c.value)
            for c in cc.extract_claims("The 2nd/5th Lords (Mercury) sit here.")} \
        == {("lordship", 2, "Mercury"), ("lordship", 5, "Mercury")}


def test_an_axis_places_nothing():
    assert cc.extract_claims("Rahu & Ketu (6th/12th Axis) drive this chart.") == []


def test_an_unnamed_lord_becomes_the_subject():
    """"…and your 6th lord in the 1st" — the thing in the 1st is that lord, not
    the planet named earlier in the sentence."""
    claims = [(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "With Rahu in the 6th and your 6th lord in the 1st, you overcome much.")]
    assert ("placement_house", "Rahu", 6) in claims
    assert ("placement_house", "Rahu", 1) not in claims


def test_a_phrase_word_ends_the_subject():
    """"the Rahu Mahadasha and the Debilitated 7th Lord" — the 7th lord is not
    Rahu. The dignity word between them hid how far apart they were."""
    assert cc.extract_claims(
        "Due to the Rahu Mahadasha and the Debilitated 7th Lord, do not rush.") == []


def test_a_sign_leads_its_own_planet():
    """"the Taurus Lagna, the Leo Moon" put the Lagna in Leo, because the sign
    bound backwards to the previous subject instead of forwards to its own."""
    assert {(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "the Taurus Lagna, the Leo Moon, and a cluster in the 1st House.")} \
        == {("placement_sign", "Lagna", "Taurus"), ("placement_sign", "Moon", "Leo")}


def test_a_lordship_does_not_step_over_a_closed_bracket():
    """"Your Lagna Lord (Venus), the 9th/10th Lord (Saturn)" — Venus's item is
    finished at its closing bracket, so the 9th is Saturn's. An opening bracket
    may be crossed ("Jupiter (11th Lord)"); a closing one may not."""
    claims = {(c.kind, c.subject, c.value) for c in cc.extract_claims(
        "Your Lagna Lord (Venus), the 9th/10th Lord (Saturn), and the 11th Lord "
        "(Jupiter) are placed well.")}
    assert claims == {("lordship", 9, "Saturn"), ("lordship", 10, "Saturn"),
                      ("lordship", 11, "Jupiter")}


def test_an_ordinal_is_not_always_a_house():
    """"in the first half of 2027" is not a placement, and reading it as one is
    the single most likely way to invent a contradiction."""
    assert cc.extract_claims("Saturn matters in the first half of 2027.") == []
    assert cc.extract_claims("Saturn is in the 3rd house.")


def test_a_relation_binds_to_the_nearest_anchor():
    """"Jupiter, lord of the 8th and 11th, aspects the 4th house" must not read
    as Jupiter ruling the 4th — the aspect is a different relation, and the lord
    word belongs to the houses before it."""
    claims = cc.extract_claims(
        "Jupiter, the lord of the 8th and 11th, aspects the 4th house.")
    assert {(c.kind, c.subject, c.value) for c in claims} == {
        ("lordship", 8, "Jupiter"), ("lordship", 11, "Jupiter")}


def test_a_sign_after_a_house_needs_a_bare_copula():
    """"the 9th house is Capricorn" gives the house its sign; "…lord of the 9th,
    is IN Cancer" places a planet. The preposition is the whole difference."""
    assert [(c.kind, c.subject, c.value)
            for c in cc.extract_claims("The 9th house is Capricorn.")] \
        == [("house_sign", 9, "Capricorn")]
    assert ("placement_sign", "Saturn", "Cancer") in [
        (c.kind, c.subject, c.value)
        for c in cc.extract_claims("Saturn, lord of the 9th, is in Cancer.")]


@pytest.mark.parametrize("frame", [
    "In the Navamsa, Mars is in the 5th house.",
    "In D10, Mars is in the 5th house.",
    "Mars is transiting the 5th house.",
    "In the annual chart, Mars is in the 5th house.",
    "From the Moon, Mars is in the 5th house.",
    "In the Varshaphal, Mars is in the 5th house.",
    "Natives with Mars in the 5th house are competitive.",
    "Generally, Mars is in the 5th house for such births.",
    "Mars enters the 5th house next spring.",
])
def test_a_different_frame_of_reference_is_skipped(frame, facts):
    """Each of these is about some chart other than the natal D1 — checking their
    numbers against D1 facts is how a checker earns a reputation for crying wolf."""
    assert cc.check(frame, facts)["contradictions"] == []


def test_checked_counts_only_what_could_be_judged(facts):
    """The rate in the admin console is meaningless without this: a reading with
    no checkable claims is not a clean reading."""
    assert cc.check("Life will bring changes.", facts)["checked"] == 0
    assert cc.check("Mars is in the 3rd house.", facts)["checked"] == 1


# ── The guard: check, regenerate once, annotate what survives ───────────────

FACTS = cc.Facts(planet_house={"Mars": 3}, planet_sign={"Mars": "Cancer"},
                 house_lord={9: "Saturn"}, house_sign={9: "Capricorn"},
                 lords_of={"Saturn": [9, 10]})
WRONG = "Mars is in the 5th house."
RIGHT = "Mars is in the 3rd house."


def _guard(text, mode, regen=None):
    return asyncio.run(cc.guard(text, FACTS, mode, regen))


def test_off_does_nothing():
    text, report = _guard(WRONG, "off")
    assert text == WRONG and report["contradictions"] == []


def test_log_records_but_shows_nothing():
    text, report = _guard(WRONG, "log")
    assert text == WRONG                       # the reader sees no change
    assert len(report["contradictions"]) == 1  # the admin report does


def test_annotate_leaves_the_prose_alone_and_names_the_error():
    text, report = _guard(WRONG, "annotate")
    assert text.startswith(WRONG)              # not a word of it rewritten
    assert cc.CORRECTION_HEADER in text
    assert "Mars is in the 3rd house" in text
    assert not report["regenerated"]


def test_verify_regenerates_and_the_reader_never_sees_the_slip():
    async def regen(instruction):
        assert "You wrote" in instruction and "Mars is in the 5th house" in instruction
        return RIGHT

    text, report = _guard(WRONG, "verify", regen)
    assert text == RIGHT
    assert report["regenerated"] and report["fixed_by_retry"] == 1
    assert cc.CORRECTION_HEADER not in text


def test_a_worse_retry_is_discarded():
    """A model told it was wrong can answer worse the second time. Trading a known
    set of errors for a larger unknown one is not an improvement."""
    async def regen(_):
        return "Mars is in the 5th house and the 9th lord is Jupiter."

    text, report = _guard(WRONG, "verify", regen)
    assert text.startswith(WRONG)                 # the first answer was kept
    assert len(report["contradictions"]) == 1
    assert report["regenerated"] and report["fixed_by_retry"] == 0


def test_a_failed_retry_falls_back_to_annotating():
    """The retry is a best effort on top of an answer we already have; losing it
    must not lose the answer."""
    async def regen(_):
        raise RuntimeError("the GPU is busy")

    text, report = _guard(WRONG, "verify", regen)
    assert text.startswith(WRONG) and cc.CORRECTION_HEADER in text


def test_streaming_degrades_verify_to_annotate():
    """No `regenerate` callable: the reader has already watched the answer arrive,
    so there is nothing to re-do that they have not seen."""
    text, report = _guard(WRONG, "verify")
    assert cc.CORRECTION_HEADER in text and not report["regenerated"]


def test_a_clean_answer_is_returned_untouched():
    text, report = _guard(RIGHT, "verify", None)
    assert text == RIGHT and report["contradictions"] == []


def test_no_facts_means_no_checking():
    """A partial context (a tool-mode seed, an old saved payload) yields partial
    facts and therefore fewer checks — never a contradiction by default."""
    text, report = _guard(WRONG, "verify", None)
    empty, empty_report = asyncio.run(cc.guard(WRONG, cc.Facts(), "verify"))
    assert empty == WRONG and empty_report["contradictions"] == []


def test_the_report_keeps_what_the_model_said_before_it_was_corrected():
    """A reading the retry rescued is still a reading the model got wrong.
    Counting only survivors would report a flawless 0% for a model that gets it
    wrong every time and is rescued every time — which is precisely what the
    first live run of this feature did."""
    async def regen(_):
        return RIGHT

    text, report = _guard(WRONG, "verify", regen)
    assert text == RIGHT
    assert report["contradictions"] == []                  # the reader saw none
    assert [c["kind"] for c in report["initial"]] == ["placement_house"]
