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
