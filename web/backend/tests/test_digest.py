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


def test_offset_clock_shape():
    # The fallback clock (used when no current location is set) must yield the
    # keys the block builder threads into the engine, carrying the given offset.
    clock = digest._offset_clock(5.5)
    assert set(clock) == {"date", "time", "tz"}
    assert clock["tz"] == 5.5
    assert len(clock["date"]) == 10 and clock["date"][4] == "-"
    assert len(clock["time"]) == 5 and clock["time"][2] == ":"


def test_render_no_hoist_when_days_differ_keeps_full_sections():
    other = [h.replace("2026-10-31", "2026-10-30") for h in _HL_A]
    blocks = [_block("A", _HL_A), _block("B", other)]
    text = digest._render_text(blocks, "2026-07-17", "digest")
    assert "Across the sky today" not in text
    # Each section carries its own (different) ingress line.
    assert "Jupiter enters Leo on 2026-10-31" in text
    assert "Jupiter enters Leo on 2026-10-30" in text
