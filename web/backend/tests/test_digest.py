"""Unit tests for the digest's highlight-splitting and shared-sky rendering.

These are the pure pieces of `digest.py` — no DB, no LLM. They pin the two
behaviours that keep a family digest from repeating itself:

* `_split_highlights` sorts each profile's lines into shared "sky" facts (the
  panchanga headline, the retrograde list, upcoming ingresses) versus the
  chart-specific ones (dasha, Sade-Sati, pravesha yogas).
* `_shared_sky` + the renderers hoist the common sky into a single header when
  every profile was computed for the same day, and print only the personal
  lines under each name.
"""
import pytest

import digest


# A realistic mix of the lines the engine emits for one profile.
_HL_A = [
    "Friday · Shukla Tritiya, Magha nakshatra",          # panchanga (sky)
    "Rahu Mahadasha, Rahu Bhukti",                       # dasha (personal)
    "Jupiter transits your 12th from the Moon (Cancer)", # personal
    "Retrograde now: Mercury, Rahu",                     # sky
    "Jupiter enters Leo on 2026-10-31",                  # ingress (sky)
    "Saturn enters Aries on 2027-06-03",                 # ingress (sky)
    "Tajaka yoga — Ithasala (Sun/Jupiter)",              # personal
]
# Same sky, different personal lines — a second family member, same day.
_HL_B = [
    "Friday · Shukla Tritiya, Magha nakshatra",
    "Sun Mahadasha, Rahu Bhukti",
    "⚠ Rahu Bhukti ends in 9 day(s) — a dasha change is near",
    "Jupiter transits your 9th from the Moon (Cancer)",
    "Retrograde now: Mercury, Rahu",
    "Jupiter enters Leo on 2026-10-31",
    "Saturn enters Aries on 2027-06-03",
    "Tajaka yoga — Ithasala (Moon/Venus)",
]


def _block(name, highlights, date="2026-07-17"):
    sky, personal = digest._split_highlights(highlights)
    return {"name": name, "date": date, "highlights": highlights,
            "sky": sky, "personal": personal, "narrative": None}


def test_split_highlights_sorts_sky_from_personal():
    sky, personal = digest._split_highlights(_HL_A)
    assert sky == [
        "Friday · Shukla Tritiya, Magha nakshatra",
        "Retrograde now: Mercury, Rahu",
        "Jupiter enters Leo on 2026-10-31",
        "Saturn enters Aries on 2027-06-03",
    ]
    assert "Rahu Mahadasha, Rahu Bhukti" in personal
    assert "Tajaka yoga — Ithasala (Sun/Jupiter)" in personal
    # A yoga line is never mistaken for an ingress despite the word "enters" absent.
    assert not any("Tajaka" in s for s in sky)


def test_shared_sky_detected_when_days_match():
    blocks = [_block("A", _HL_A), _block("B", _HL_B)]
    shared = digest._shared_sky(blocks)
    assert shared is not None
    assert "Jupiter enters Leo on 2026-10-31" in shared


def test_shared_sky_none_when_days_differ():
    # Anoushka on a different day: the ingress dates shift, so nothing hoists.
    other = [h.replace("2026-10-31", "2026-10-30").replace("Friday", "Thursday")
             .replace("Magha", "Ashlesha") for h in _HL_A]
    blocks = [_block("A", _HL_A), _block("B", other)]
    assert digest._shared_sky(blocks) is None


def test_single_block_never_hoists():
    assert digest._shared_sky([_block("A", _HL_A)]) is None


def test_render_hoists_sky_once_and_keeps_personal_per_name():
    blocks = [_block("Mahendra", _HL_A), _block("Naina", _HL_B)]
    text = digest._render_text(blocks, "2026-07-17", "digest")
    # The shared ingress appears exactly once, under the shared header.
    assert text.count("Jupiter enters Leo on 2026-10-31") == 1
    assert "Across the sky today" in text
    # Personal lines still appear under each name.
    assert "Rahu Mahadasha, Rahu Bhukti" in text
    assert "Sun Mahadasha, Rahu Bhukti" in text


from astrology.compute_digests import _next_good_window

# A synthetic Choghadiya day (sunrise 06:00) then night wrapping past midnight.
_CHOG = [
    {"name": "Udveg", "nature": "bad", "start": "06:00", "end": "07:30", "period": "day"},
    {"name": "Char", "nature": "neutral", "start": "07:30", "end": "09:00", "period": "day"},
    {"name": "Labh", "nature": "good", "start": "09:00", "end": "10:30", "period": "day"},
    {"name": "Amrit", "nature": "good", "start": "10:30", "end": "12:00", "period": "day"},
    {"name": "Kaal", "nature": "bad", "start": "18:00", "end": "20:00", "period": "night"},
    {"name": "Shubh", "nature": "good", "start": "23:00", "end": "01:00", "period": "night"},
]


def test_next_good_window_picks_upcoming():
    assert _next_good_window(_CHOG, 8.0)["name"] == "Labh"


def test_next_good_window_current_still_counts():
    # 09:30 is inside Labh (ends 10:30) — it's still the answer, not skipped.
    assert _next_good_window(_CHOG, 9.5)["name"] == "Labh"


def test_next_good_window_crosses_midnight():
    # After the daytime good windows, the next is the night Shubh at 23:00.
    assert _next_good_window(_CHOG, 13.0)["name"] == "Shubh"


def test_next_good_window_none_left():
    assert _next_good_window(_CHOG, 23.5 + 2) is None  # past the wrapped Shubh end


def test_is_monday():
    assert digest._is_monday({"date": "2026-07-20"}) is True   # a Monday
    assert digest._is_monday({"date": "2026-07-17"}) is False  # a Friday
    assert digest._is_monday(None) is True                      # unknown → don't swallow


def test_favourable_window_is_a_sky_fact():
    sky, personal = digest._split_highlights(
        ["Favourable window today: Amrit 10:30–12:00 (day)", "Rahu Mahadasha, Rahu Bhukti"])
    assert any(s.startswith("Favourable window today:") for s in sky)
    assert "Rahu Mahadasha, Rahu Bhukti" in personal


def test_diff_signals_first_time_is_empty():
    new = digest._extract_signals(
        {"transits": {"retrograde": ["Mercury"], "sade_sati": False},
         "dasha": {"maha_lord": "Rahu", "bhukti": {"lord": "Rahu"}}})
    assert digest._diff_signals(None, new) == []


def test_diff_signals_reports_only_what_moved():
    old = {"retro": ["Mercury"], "maha": "Rahu", "bhukti": "Rahu", "sade_sati": False}
    new = {"retro": ["Mercury", "Saturn"], "maha": "Rahu", "bhukti": "Jupiter",
           "sade_sati": True}
    lines = digest._diff_signals(old, new)
    assert "Saturn has turned retrograde" in lines
    assert "A new Bhukti has begun: Jupiter" in lines
    assert "Sade-Sati has begun" in lines
    # Mercury was already retrograde and the Mahadasha didn't change → not mentioned.
    assert not any("Mercury" in l for l in lines)
    assert not any("Mahadasha" in l for l in lines)


def test_diff_signals_direct_again():
    old = {"retro": ["Mercury", "Mars"], "maha": "Sun", "bhukti": "Sun", "sade_sati": True}
    new = {"retro": ["Mercury"], "maha": "Sun", "bhukti": "Sun", "sade_sati": False}
    lines = digest._diff_signals(old, new)
    assert "Mars is direct again" in lines
    assert "Sade-Sati has lifted" in lines


def test_offset_clock_shape():
    # The fallback clock (used when no current location is set) must yield the
    # keys the block builder threads into the engine, carrying the given offset.
    clock = digest._offset_clock(5.5)
    assert set(clock) == {"date", "time", "tz"}
    assert clock["tz"] == 5.5
    assert len(clock["date"]) == 10 and clock["date"][4] == "-"
    assert len(clock["time"]) == 5 and clock["time"][2] == ":"


def test_zone_clock():
    # None/unknown zone → None (caller falls back to the shared/owner clock).
    assert digest._zone_clock(None) is None
    assert digest._zone_clock("Not/AZone") is None
    # A real zone yields the same shape as the offset clock, DST-correct.
    clock = digest._zone_clock("America/Chicago")
    assert set(clock) == {"date", "time", "tz"}
    assert clock["tz"] in (-5.0, -6.0)  # CDT / CST


def test_render_no_hoist_when_days_differ_keeps_full_sections():
    other = [h.replace("2026-10-31", "2026-10-30") for h in _HL_A]
    blocks = [_block("A", _HL_A), _block("B", other)]
    text = digest._render_text(blocks, "2026-07-17", "digest")
    assert "Across the sky today" not in text
    # Each section carries its own (different) ingress line.
    assert "Jupiter enters Leo on 2026-10-31" in text
    assert "Jupiter enters Leo on 2026-10-30" in text


# ── The focused narrative style (§67) ────────────────────────────────────────
# Two prompts now write digests, chosen by a runtime knob, and the email shape
# follows the prompt that actually wrote the section. These pin the switch, the
# de-duplicated email, and the fallback that keeps a narrative-less section from
# arriving empty.
import html as _html

import runtime_config
from llm.prompts import PromptsMixin, _ordinal_en, _fmt_period_days


def _focused_block(name="Mahen", narrative="A reading.", glance=("Good window — Amrit 07:36–09:09",)):
    return {"name": name, "date": "2026-09-09", "style": "focused",
            "narrative": narrative, "glance": list(glance),
            "highlights": ["Wednesday · Krishna Trayodashi"],
            "sky": [], "personal": ["Rahu Mahadasha, Venus Bhukti"],
            "supports": [{"text": "Tara Bala: Mitra", "scope": "today"}],
            "cautions": [{"text": "Chandra Bala weak", "scope": "today"}],
            "changes": []}


def test_focused_email_drops_the_bullets_the_narrative_was_written_from():
    text = digest._render_text([_focused_block()], "2026-09-09", "digest")
    assert "At a glance:" in text
    assert "Good window — Amrit 07:36–09:09" in text
    # The narrative is built from these, so repeating them says the day twice.
    assert "Working in your favour" not in text
    assert "Take care with" not in text
    assert "Highlights:" not in text


def test_classic_email_keeps_every_section():
    block = _focused_block()
    block["style"] = "classic"
    text = digest._render_text([block], "2026-09-09", "digest")
    assert "Working in your favour" in text
    assert "Take care with" in text
    assert "At a glance" not in text


def test_focused_section_without_a_narrative_falls_back_to_the_bullets():
    """An empty reading must not produce an empty email."""
    block = _focused_block(narrative=None)
    assert digest._is_focused(block) is False
    text = digest._render_text([block], "2026-09-09", "digest")
    assert "Working in your favour" in text


def test_glance_carries_times_and_dates_not_the_verdicts():
    lines = digest._glance_lines({
        "action_window": {"name": "Amrit", "start": "07:36", "end": "09:09"},
        "avoid_windows": [{"name": "Rahu Kalam", "start": "12:14", "end": "13:46"}],
        "transits": {"upcoming": [{"planet": "Jupiter", "to_sign": "Leo",
                                   "date": "2026-10-31"}]},
        "dasha": {"bhukti": {"lord": "Venus", "end_date": "2028-06-17"}},
        "changes": ["Saturn has turned retrograde"],
    }, "daily")
    assert lines[0] == "New today — Saturn has turned retrograde"
    assert "Good window — Amrit 07:36–09:09" in lines
    assert "Keep clear — Rahu Kalam 12:14–13:46" in lines
    assert "Jupiter enters Leo — 2026-10-31" in lines
    assert "Venus Bhukti runs to 2028-06-17" in lines


def test_glance_for_a_period_leads_with_dated_events():
    lines = digest._glance_lines({
        "events": [{"date": "2026-09-02", "text": "Venus enters Libra"}],
        "tarabala": {"best": ["2026-09-10"]},
    }, "fortnightly")
    assert lines[0] == "2026-09-02 — Venus enters Libra"
    assert "Well-starred days — 2026-09-10" in lines


def test_inline_markdown_renders_but_cannot_inject():
    assert digest._inline_md(_html.escape("the **Amrit window**")) == \
        "the <strong>Amrit window</strong>"
    assert digest._inline_md(_html.escape("a * b * c")) == "a * b * c"
    # Escaping happens first, so nothing in the narrative can become markup.
    assert "<script>" not in digest._inline_md(_html.escape("<script> **x**"))


def test_narrative_style_knob_rejects_nonsense_and_defaults_to_focused():
    assert runtime_config.defaults()["digest_narrative_style"] in runtime_config.NARRATIVE_STYLES
    assert runtime_config._coerce("digest_narrative_style", "CLASSIC ") == "classic"
    with pytest.raises(ValueError):
        runtime_config._coerce("digest_narrative_style", "poetic")


def test_digest_angle_is_stable_per_date_but_rotates():
    a = PromptsMixin._digest_angle("2026-09-09")
    assert a == PromptsMixin._digest_angle("2026-09-09")   # same day, same reading
    assert a != PromptsMixin._digest_angle("2026-09-10")   # consecutive days differ
    assert PromptsMixin._digest_angle("nonsense") in PromptsMixin._DIGEST_ANGLES


def test_natal_line_names_the_house_and_what_it_rules():
    natal = {"Venus": {"house": 10, "sign_name": "Aries", "nakshatra": "Bharani",
                       "owns_houses": [11, 4], "retrograde": False},
             "Rahu": {"house": 10, "sign_name": "Aries", "nakshatra": "Bharani",
                      "owns_houses": [], "retrograde": True}}
    venus = PromptsMixin._natal_line("Venus", natal)
    assert "10th house" in venus and "rules your 11th and 4th" in venus
    rahu = PromptsMixin._natal_line("Rahu", natal)
    assert "rules no house of its own" in rahu and "retrograde at birth" in rahu
    assert PromptsMixin._natal_line("Neptune", natal) == ""


def test_ordinals():
    assert [_ordinal_en(n) for n in (1, 2, 3, 4, 11, 12, 13, 21)] == \
        ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st"]


def test_period_days_join_their_tara_label():
    days = [{"date": "2026-09-10", "tarabala": "Parama Mitra"},
            {"date": "2026-09-11", "tarabala": "Vipat"}]
    assert _fmt_period_days(["2026-09-10"], days) == "2026-09-10 (Parama Mitra)"
    # A date with no matching row still prints, rather than vanishing.
    assert _fmt_period_days(["2026-09-99"], days) == "2026-09-99"


# ── When the good hour and a bad hour are the same hour ──────────────────────
from astrology.compute_digests import _clock_overlaps


def test_clock_overlap_detection():
    amrit = {"start": "07:36", "end": "09:09"}
    assert _clock_overlaps(amrit, {"start": "07:36", "end": "09:08"})
    assert _clock_overlaps(amrit, {"start": "09:00", "end": "10:30"})
    assert not _clock_overlaps(amrit, {"start": "09:09", "end": "10:30"})  # touching
    assert not _clock_overlaps(amrit, {"start": "12:14", "end": "13:46"})
    assert not _clock_overlaps(amrit, {"start": "bad", "end": None})


def test_glance_says_when_the_good_window_collides():
    """The digest used to recommend Amrit 07:36–09:09 and warn off Yamaganda
    07:36–09:08 in the same list, as separate advice about the same 90 minutes."""
    lines = digest._glance_lines({
        "action_window": {"name": "Amrit", "start": "07:36", "end": "09:09",
                          "conflicts": ["Yamaganda"]},
        "avoid_windows": [{"name": "Yamaganda", "start": "07:36", "end": "09:08"}],
    }, "daily")
    assert lines[0] == "Good window — Amrit 07:36–09:09 (overlaps Yamaganda)"


def test_glance_leaves_an_uncontested_window_unqualified():
    lines = digest._glance_lines({
        "action_window": {"name": "Amrit", "start": "07:36", "end": "09:09",
                          "conflicts": []},
    }, "daily")
    assert lines[0] == "Good window — Amrit 07:36–09:09"
