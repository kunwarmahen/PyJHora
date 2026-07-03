#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Dict, Optional, List
import sys
import os

# Add parent directory to path to import jhora
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from jhora.panchanga import drik
    from jhora.horoscope.chart import charts, house, strength, yoga, dosha, arudhas, ashtakavarga
    from jhora.horoscope.match import compatibility as compat_module
    from jhora.horoscope.dhasa.graha import (vimsottari, ashtottari, yogini,
                                             shodasottari, dwadasottari,
                                             panchottari, sataatbika)
    from jhora.horoscope.dhasa.raasi import (narayana, kalachakra, kendradhi_rasi,
                                             sudasa, drig, chara, sthira, trikona)
    from jhora import utils, const
    import swisseph as swe

    # Match Jagannatha Hora's default ayanamsa: True Chitra Paksha (Spica fixed
    # at 180°). PyJHora defaults to TRUE_PUSHYA. Note True Chitra differs from
    # traditional Lahiri by only ~1', but that's enough to flip a body sitting on
    # a navamsa/varga cusp into the next division vs JHora.
    const._DEFAULT_AYANAMSA_MODE = 'TRUE_CITRA'
    drik.set_ayanamsa_mode('TRUE_CITRA')

    # Match Jagannatha Hora's default lunar nodes (Mean). PyJHora defaults to
    # True nodes, which differ from Mean by up to ~1.6°. In wide D1 signs this is
    # invisible, but in finer vargas (e.g. D10's 3° divisions) it flips Rahu/Ketu
    # one division/house off vs JHora. set_planet_list rebuilds the swe planet
    # mapping the chart code actually iterates (const.set_node_mode alone won't).
    drik.set_planet_list(set_rahu_ketu_as_true_nodes=False)

    PYJHORA_AVAILABLE = True
except ImportError as e:
    print(f"PyJHora import error: {e}")
    PYJHORA_AVAILABLE = False

DEFAULT_AYANAMSA = "TRUE_CITRA"

# Curated, user-facing ayanamsa options (value -> label). Values must exist in
# PyJHora's const.available_ayanamsa_modes. True Chitra is listed first as the
# default (matches Jagannatha Hora's "True Lahiri/Chitrapaksha").
SUPPORTED_AYANAMSAS = {
    "TRUE_CITRA": "True Chitra Paksha (Lahiri)",
    "LAHIRI": "Lahiri (traditional)",
    "KP": "Krishnamurti (KP)",
    "RAMAN": "B. V. Raman",
    "YUKTESHWAR": "Sri Yukteshwar",
    "TRUE_PUSHYA": "True Pushya",
    "FAGAN": "Fagan / Bradley",
}


def _set_ayanamsa(name):
    """Set the global ayanamsa for the next computation; fall back to the default
    for unknown values. Returns the key that was actually applied."""
    key = (name or DEFAULT_AYANAMSA).upper()
    if key not in SUPPORTED_AYANAMSAS:
        key = DEFAULT_AYANAMSA
    if PYJHORA_AVAILABLE:
        drik.set_ayanamsa_mode(key)
    return key


# PyJHora planet indexing: 0=Sun … 8=Ketu.
PLANET_NAMES = {
    0: "Sun", 1: "Moon", 2: "Mars", 3: "Mercury",
    4: "Jupiter", 5: "Venus", 6: "Saturn", 7: "Rahu", 8: "Ketu",
}

# Reverse lookup (name -> index) for resolving a dasha lord-path sent by the UI.
PLANET_INDICES = {v: k for k, v in PLANET_NAMES.items()}

# Zodiac sign names, index 0 = Aries … 11 = Pisces.
ZODIAC_NAMES = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]


def _format_arudha_padas(ba):
    """Shape a raw bhava-arudha sign list (from
    `arudhas.bhava_arudhas_from_planet_positions`) into the frontend contract:
    each entry has `bhava`, `label` (full), `short` (compact chart label —
    AL for bhava 1, UL for bhava 12, else A2..A11), `sign` (1-based rasi the
    arudha falls in, Aries=1) and `sign_name`."""
    labels = {0: "AL (Arudha Lagna)", 11: "UL (Upapada)"}
    short = {0: "AL", 11: "UL"}
    return [
        {"bhava": i + 1,
         "label": labels.get(i, f"A{i + 1}"),
         "short": short.get(i, f"A{i + 1}"),
         "sign": int(s) % 12 + 1,
         "sign_name": ZODIAC_NAMES[int(s) % 12]}
        for i, s in enumerate(ba)
    ]

# Traditional (7-graha) sign lords, indexed by sign 0=Aries..11=Pisces → planet index.
# Aries/Scorpio→Mars, Tau/Lib→Venus, Gem/Vir→Mercury, Can→Moon, Leo→Sun,
# Sag/Pis→Jupiter, Cap/Aqu→Saturn.
SIGN_LORD = [2, 5, 3, 1, 0, 3, 5, 2, 4, 6, 6, 4]

# Event → classical significators, for the event-based birth-time rectification.
# `houses` = bhavas that signify the event (1-based, counted from the Lagna);
# `karakas` = natural significator planets (by index). A candidate birth time is
# scored by whether the Vimsottari maha/bhukti lord running at the event date is a
# lord of / placed in one of these houses, or is the event's karaka. Because the
# house lords depend on the Lagna (time-sensitive) and the running dasha depends on
# the Moon's natal fraction (also time-sensitive), the score discriminates birth time.
EVENT_SIGNIFICATORS = {
    "marriage":     {"houses": [7, 2, 11],    "karakas": [5]},       # Venus
    "childbirth":   {"houses": [5, 2, 11],    "karakas": [4]},       # Jupiter
    "career":       {"houses": [10, 6, 11],   "karakas": [6, 0, 3]}, # Saturn/Sun/Mercury
    "promotion":    {"houses": [10, 11],      "karakas": [0, 6]},    # Sun/Saturn
    "education":    {"houses": [4, 5, 9],     "karakas": [3, 4]},    # Mercury/Jupiter
    "wealth":       {"houses": [2, 11, 5, 9], "karakas": [4, 5]},    # Jupiter/Venus
    "property":     {"houses": [4, 11],       "karakas": [2, 5]},    # Mars/Venus
    "relocation":   {"houses": [12, 3, 9],    "karakas": [7]},       # Rahu
    "illness":      {"houses": [6, 8, 12],    "karakas": [6, 2, 7]}, # Saturn/Mars/Rahu
    "accident":     {"houses": [6, 8],        "karakas": [2, 7]},    # Mars/Rahu
    "father_death": {"houses": [9, 8],        "karakas": [0, 6]},    # Sun/Saturn
    "mother_death": {"houses": [4, 8],        "karakas": [1, 6]},    # Moon/Saturn
}

# Curated divisional charts (Parashara's Shodasavarga). Each entry:
#   factor -> (code, name, significance). The factor is passed straight to
#   PyJHora's charts.divisional_chart(divisional_chart_factor=...).
SUPPORTED_VARGAS = {
    1:  ("D1",  "Rasi",            "Body, overall life"),
    2:  ("D2",  "Hora",            "Wealth, prosperity"),
    3:  ("D3",  "Drekkana",        "Siblings, courage"),
    4:  ("D4",  "Chaturthamsa",    "Fortune, property, home"),
    7:  ("D7",  "Saptamsa",        "Children, progeny"),
    9:  ("D9",  "Navamsa",         "Spouse, dharma, fortune"),
    10: ("D10", "Dasamsa",         "Career, status, achievements"),
    12: ("D12", "Dwadasamsa",      "Parents, ancestry"),
    16: ("D16", "Shodasamsa",      "Vehicles, comforts, luxuries"),
    20: ("D20", "Vimsamsa",        "Spiritual pursuits, worship"),
    24: ("D24", "Chaturvimsamsa",  "Education, learning"),
    27: ("D27", "Bhamsa",          "Strengths and weaknesses"),
    30: ("D30", "Trimsamsa",       "Misfortunes, adversity"),
    40: ("D40", "Khavedamsa",      "Auspicious & inauspicious effects"),
    45: ("D45", "Akshavedamsa",    "General character, conduct"),
    60: ("D60", "Shashtiamsa",     "Past karma, overall refinement"),
}

# Additional dasha systems beyond Vimsottari (which has its own drill-down page).
# `lord_type` graha => periods are ruled by planets; raasi => ruled by signs.
SUPPORTED_DASHAS = {
    "ashtottari": {
        "name": "Ashtottari Dasha", "lord_type": "graha",
        "description": "108-year conditional nakshatra dasha (graha periods).",
    },
    "yogini": {
        "name": "Yogini Dasha", "lord_type": "graha",
        "description": "36-year nakshatra dasha of the eight Yoginis (graha periods).",
    },
    "narayana": {
        "name": "Narayana Dasha", "lord_type": "raasi",
        "description": "Rasi (sign) dasha from the lagna, key for life-area timing.",
    },
    "kalachakra": {
        "name": "Kalachakra Dasha", "lord_type": "raasi",
        "description": "Wheel-of-time rasi dasha seeded from the Moon's navamsa.",
    },
    # ── Additional graha (nakshatra) dashas ────────────────────────────────
    "shodasottari": {
        "name": "Shodasottari Dasha", "lord_type": "graha",
        "description": "116-year conditional nakshatra dasha (graha periods).",
    },
    "dwadasottari": {
        "name": "Dwadasottari Dasha", "lord_type": "graha",
        "description": "112-year conditional nakshatra dasha (graha periods).",
    },
    "panchottari": {
        "name": "Panchottari Dasha", "lord_type": "graha",
        "description": "105-year conditional nakshatra dasha (graha periods).",
    },
    "shatabdika": {
        "name": "Shatabdika Dasha", "lord_type": "graha",
        "description": "100-year conditional nakshatra dasha (graha periods).",
    },
    # ── Additional raasi (sign) dashas ─────────────────────────────────────
    "kendradhi_rasi": {
        "name": "Kendradhi Rasi Dasha", "lord_type": "raasi",
        "description": "Rasi dasha ordered by the quadrants from the lagna.",
    },
    "sudasa": {
        "name": "Sudasa Dasha", "lord_type": "raasi",
        "description": "Jaimini rasi dasha from Sree Lagna — fortune & prosperity.",
    },
    "drig": {
        "name": "Drig Dasha", "lord_type": "raasi",
        "description": "Jaimini rasi dasha keyed to aspects — spiritual timing.",
    },
    "chara": {
        "name": "Chara Dasha", "lord_type": "raasi",
        "description": "Jaimini's principal movable rasi dasha from the lagna.",
    },
    "sthira": {
        "name": "Sthira Dasha", "lord_type": "raasi",
        "description": "Fixed-duration rasi dasha (7/8/9 years by sign type).",
    },
    "trikona": {
        "name": "Trikona Dasha", "lord_type": "raasi",
        "description": "Jaimini trinal rasi dasha from the lagna.",
    },
}

# Curated Sahams (sensitive points, akin to Western "Arabic parts") surfaced on
# the Varshaphal / annual page. Each entry: (label, saham.py function, meaning).
# The function returns a 0–360° longitude; we convert it to sign + degree.
VARSHAPHAL_SAHAMS = [
    ("Punya",  "punya_saham",  "Fortune, merit, good deeds"),
    ("Vidya",  "vidya_saham",  "Education, learning"),
    ("Yasas",  "yasas_saham",  "Fame, reputation"),
    ("Mitra",  "mitra_saham",  "Friends, alliances"),
    ("Karma",  "karma_saham",  "Work, career, action"),
    ("Roga",   "roga_saham",   "Health, illness"),
    ("Vivaha", "vivaha_saham", "Marriage"),
    ("Puthra", "puthra_saham", "Children, progeny"),
]

# Selectable annual (Varshaphal) dasha systems: key -> (label, lord_type).
# graha => periods ruled by planets; raasi => ruled by signs.
VARSHA_DASHA_SYSTEMS = {
    "mudda":     ("Mudda (Varsha Vimsottari)", "graha"),
    "patyayini": ("Patyayini",                 "graha"),
    "narayana":  ("Varsha Narayana",           "raasi"),
}

# ── Panchanga (daily almanac) name tables ──────────────────────────────────
# Standard Sanskrit names, kept consistent with the chart's nakshatra naming.
NAKSHATRA_NAMES = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
    "Purva Bhadrapada", "Uttara Bhadrapada", "Revati",
]

# 15 tithi names within a paksha; the 15th differs by paksha (Purnima/Amavasya).
TITHI_NAMES_15 = [
    "Pratipada", "Dwitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi", "Purnima",
]

# 27 yogas, index 0 = Vishkambha … 26 = Vaidhriti.
YOGA_NAMES = [
    "Vishkambha", "Priti", "Ayushman", "Saubhagya", "Shobhana", "Atiganda",
    "Sukarma", "Dhriti", "Shula", "Ganda", "Vriddhi", "Dhruva", "Vyaghata",
    "Harshana", "Vajra", "Siddhi", "Vyatipata", "Variyana", "Parigha", "Shiva",
    "Siddha", "Sadhya", "Shubha", "Shukla", "Brahma", "Indra", "Vaidhriti",
]

# 7 movable (chara) karanas cycle through tithi-halves 2..57.
KARANA_CHARA = ["Bava", "Balava", "Kaulava", "Taitila", "Gara", "Vanija", "Vishti"]
WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# ── Almanac (§9.2) name tables ─────────────────────────────────────────────
# The seven graha that rule the planetary hours (hora), indexed 0=Sun .. 6=Saturn
# — the order PyJHora's shubha_hora tables return. Benefics vs malefics give the
# hora a supportive/inauspicious tone (Moon/Mercury/Jupiter/Venus vs Sun/Mars/Saturn).
HORA_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
HORA_BENEFICS = {"Moon", "Mercury", "Jupiter", "Venus"}

# Curated tithi-driven festivals / vrathas. Each entry maps a display key to the
# tithi index/indices (1..30, across both pakshas) the vratha falls on, plus a
# short meaning. tithi_dates() finds every occurrence in a date range.
FESTIVAL_TYPES = {
    "ekadashi":  {"name": "Ekadashi",  "tithis": [11, 26],
                  "meaning": "Vishnu fasting day (11th tithi of each paksha)"},
    "pradosham": {"name": "Pradosham", "tithis": [13, 28],
                  "meaning": "Shiva worship at dusk (13th tithi of each paksha)"},
    "purnima":   {"name": "Purnima",   "tithis": [15],
                  "meaning": "Full moon"},
    "amavasya":  {"name": "Amavasya",  "tithis": [30],
                  "meaning": "New moon"},
    "sankashti": {"name": "Sankashti Chaturthi", "tithis": [19],
                  "meaning": "Ganesha vratha (Krishna Chaturthi)"},
    "chaturthi": {"name": "Vinayaka Chaturthi",  "tithis": [4],
                  "meaning": "Ganesha vratha (Shukla Chaturthi)"},
    "ashtami":   {"name": "Krishna Ashtami", "tithis": [23],
                  "meaning": "8th tithi of Krishna paksha"},
}
DEFAULT_FESTIVAL_TYPES = ["ekadashi", "pradosham", "purnima", "amavasya", "sankashti"]


def _tithi_name(n):
    """Map a 1..30 tithi index to '<Paksha> <Name>'."""
    paksha = "Shukla" if n <= 15 else "Krishna"
    within = n if n <= 15 else n - 15
    name = TITHI_NAMES_15[within - 1]
    if within == 15:
        name = "Purnima" if paksha == "Shukla" else "Amavasya"
    return f"{paksha} {name}", paksha


def _karana_name(k):
    """Map a 1..60 karana index to its name (1 fixed + 7×8 movable + 3 fixed)."""
    if k <= 1:
        return "Kimstughna"
    if k >= 58:
        return ["Shakuni", "Chatushpada", "Naga"][k - 58]
    return KARANA_CHARA[(k - 2) % 7]


def _fmt_hours(h):
    """Format a local-time float-hours value as 'HH:MM', tagging the day roll
    when the panchanga element starts the previous / ends the next day."""
    if h is None:
        return None
    suffix = ""
    if h < 0:
        h = -h
        suffix = " (prev)"
    elif h >= 24:
        h -= 24
        suffix = " (next)"
    hh = int(h) % 24
    mm = int(round((h - int(h)) * 60))
    if mm == 60:
        mm = 0
        hh = (hh + 1) % 24
    return f"{hh:02d}:{mm:02d}{suffix}"


# ── Sarvatobhadra Chakra (SBC) ──────────────────────────────────────────────
# The Sarvatobhadra ("auspicious in every direction") Chakra is a 9×9 grid used
# in muhurta and gochara (transit) analysis. Its rings, from outside in:
#   • the 28 nakshatras (incl. Abhijit) on the outer border (corners are vowels)
#   • the 50 aksharas (Sanskrit syllables) — used to locate a person's name star
#   • the 12 rasis (signs)
#   • a 3×3 centre carrying the five tithi groups (Nanda/Bhadra/Jaya/Rikta/Purna)
#     and the seven weekdays.
# A planet transiting a cell "pierces" (vedha) the cell directly facing it across
# the chakra — the saamne (frontal) vedha — i.e. the cell mirrored through the
# centre. We compute occupation (a planet sitting on a sensitive cell) and that
# facing vedha onto the native's anchor cells (birth star, sign, name star,
# birth tithi & weekday). The grid layout below mirrors PyJHora's desktop
# `jhora.ui.chakra.Sarvatobadra` so the web view is faithful to the library.
#
# Raw grid: ints on the border are nakshatras (1..28); ints inside are rasis
# (1..12); the five `None` cells are the centre tithi/weekday block (filled from
# _SBC_CENTER); every other string is an akshara (syllable) label.
_SBC_RAW = [
    ['ii',  23,   24,    25,    26,    27,   1,    2,    'a'],
    [22,    'rii','g',   's',   'd',   'ch', 'l',  'u',  3],
    [28,    'kh', 'ai',  11,    12,    1,    'lu', 'a',  4],
    [21,    'j',  10,    'ah',  None,  'o',  2,    'v',  5],
    [20,    'bh', 9,     None,  None,  None, 3,    'k',  6],
    [19,    'y',  8,     'am',  None,  'au', 4,    'h',  7],
    [18,    'n',  'e',   7,     6,     5,    'luu','d',  8],
    [17,    'ri', 't',   'r',   'p',   't~', 'm',  'uu', 9],
    ['i',   16,   15,    14,    13,    12,   11,   10,   'aa'],
]

# The five centre cells: tithi group + the weekdays sharing the cell.
_SBC_CENTER = {
    (3, 4): {"group": "Rikta",  "tithis": [4, 9, 14],  "weekdays": ["Friday"]},
    (4, 3): {"group": "Jaya",   "tithis": [3, 8, 13],  "weekdays": ["Thursday"]},
    (4, 4): {"group": "Purna",  "tithis": [5, 10, 15], "weekdays": ["Saturday"]},
    (4, 5): {"group": "Nanda",  "tithis": [1, 6, 11],  "weekdays": ["Sunday", "Tuesday"]},
    (5, 4): {"group": "Bhadra", "tithis": [2, 7, 12],  "weekdays": ["Monday", "Wednesday"]},
}

# 28 nakshatra names including Abhijit (the 28th), inserted between Uttara
# Ashadha (21) and Shravana (22) — its slot on the chakra's outer ring.
_SBC_NAK28 = NAKSHATRA_NAMES[:21] + ["Abhijit"] + NAKSHATRA_NAMES[21:]

# Tithi group order, indexed by (tithi-1) % 5.
_SBC_TITHI_GROUPS = ["Nanda", "Bhadra", "Jaya", "Rikta", "Purna"]

# Grahas split into the classic benefic / malefic camps for a layman read of
# whether a transit over a sensitive cell is supportive or stressful.
_SBC_BENEFICS = {"Jupiter", "Venus", "Mercury", "Moon"}
_SBC_MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}


def _build_sbc_grid():
    """Classify the raw 9×9 grid into typed cells and index the nakshatra / rasi
    / tithi-group / weekday cells so placements can be looked up by value."""
    grid = [[None] * 9 for _ in range(9)]
    nak_cell, rasi_cell = {}, {}
    group_cell, weekday_cell = {}, {}
    for i in range(9):
        for j in range(9):
            raw = _SBC_RAW[i][j]
            on_border = (i == 0 or i == 8 or j == 0 or j == 8)
            if (i, j) in _SBC_CENTER:
                c = _SBC_CENTER[(i, j)]
                cell = {"type": "tithi", "label": c["group"], "group": c["group"],
                        "tithis": c["tithis"], "weekdays": c["weekdays"]}
                group_cell[c["group"]] = (i, j)
                for wd in c["weekdays"]:
                    weekday_cell[wd] = (i, j)
            elif isinstance(raw, int) and on_border:
                cell = {"type": "nakshatra", "label": _SBC_NAK28[raw - 1],
                        "nakshatra": raw, "name": _SBC_NAK28[raw - 1]}
                nak_cell[raw] = (i, j)
            elif isinstance(raw, int):
                cell = {"type": "rasi", "label": ZODIAC_NAMES[raw - 1],
                        "rasi": raw, "name": ZODIAC_NAMES[raw - 1]}
                rasi_cell[raw] = (i, j)
            else:
                cell = {"type": "akshara", "label": raw, "akshara": raw}
            cell["row"], cell["col"] = i, j
            grid[i][j] = cell
    return grid, nak_cell, rasi_cell, group_cell, weekday_cell


_SBC_GRID, _SBC_NAK_CELL, _SBC_RASI_CELL, _SBC_GROUP_CELL, _SBC_WEEKDAY_CELL = (
    _build_sbc_grid() if PYJHORA_AVAILABLE else (None, {}, {}, {}, {}))


def _sbc_nature(planet):
    """'benefic' | 'malefic' for a graha name (used for the layman verdict)."""
    if planet in _SBC_BENEFICS:
        return "benefic"
    if planet in _SBC_MALEFICS:
        return "malefic"
    return "neutral"


def _tithi_group(n):
    """Nanda/Bhadra/Jaya/Rikta/Purna group name for a 1..30 tithi index."""
    return _SBC_TITHI_GROUPS[(n - 1) % 5]


def _varsha_lord_name(system_key, lord_repr):
    """Map an annual-dasha lord to a display name. graha systems use a planet
    index (or 'L' for the Lagna, a valid Patyayini lord); the raasi system
    (Narayana) uses a sign index."""
    val = lord_repr[0] if isinstance(lord_repr, (tuple, list)) else lord_repr
    if system_key == "narayana":
        try:
            return ZODIAC_NAMES[int(val)]
        except (TypeError, ValueError, IndexError):
            return str(val)
    if val == "L" or (PYJHORA_AVAILABLE and val == const._ascendant_symbol):
        return "Lagna"
    try:
        return PLANET_NAMES.get(int(val), str(val))
    except (TypeError, ValueError):
        return str(val)


def _annual_dasha(system_key, jd_dob, place_obj, age, dob_date, tob_tuple):
    """Compute the maha-period list for a Varshaphal dasha system, normalised to
    the flat shape the frontend table consumes: {system, system_key, lord_type,
    periods:[{lord_name, start, end, current}]}.

    Each engine system returns start instants at full precision but expresses
    duration in a different unit (Mudda: days; Patyayini: float years; Narayana:
    an internal weight). We therefore derive every period's END from the *next*
    period's start (only the raw-last period falls back to start+duration), then
    drop any period whose start and end collapse to the same calendar day — this
    removes Patyayini's sub-day slivers for very weak planets and Narayana's
    zero-span second-cycle tail, leaving a clean day-resolution timeline."""
    from datetime import date as _date

    if system_key == "patyayini":
        from jhora.horoscope.dhasa.annual import patyayini
        jd_years = drik.next_solar_date(jd_dob, place_obj, years=age + 1)
        raw = patyayini.get_dhasa_bhukthi(jd_years, place_obj, dhasa_level_index=1)
        dur_unit_days = 365.25  # float years -> days
    elif system_key == "narayana":
        from jhora.horoscope.dhasa.raasi import narayana
        raw = narayana.varsha_narayana_dhasa_bhukthi(
            dob_date, tob_tuple, place_obj, years=age + 1, dhasa_level_index=1)
        dur_unit_days = 30.0  # only used for the raw-last fallback (usually dropped)
    else:  # mudda (default)
        system_key = "mudda"
        from jhora.horoscope.dhasa.annual import mudda
        raw = mudda.mudda_dhasa_bhukthi(jd_dob, place_obj, age, dhasa_level_index=1)
        dur_unit_days = 1.0  # already days

    label, lord_type = VARSHA_DASHA_SYSTEMS[system_key]

    items = []
    for entry in raw:
        lord_repr, start_t, dur = entry[0], entry[1], entry[2]
        start_jd = swe.julday(int(start_t[0]), int(start_t[1]), int(start_t[2]),
                              float(start_t[3]))
        items.append({
            "lord_name": _varsha_lord_name(system_key, lord_repr),
            "start_jd": start_jd,
            "dur_days": float(dur) * dur_unit_days,
        })
    items.sort(key=lambda x: x["start_jd"])

    today = _date.today().isoformat()

    def _iso(jd):
        y, m, d, _ = utils.jd_to_gregorian(jd)
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    periods = []
    for i, it in enumerate(items):
        end_jd = (items[i + 1]["start_jd"] if i + 1 < len(items)
                  else it["start_jd"] + max(it["dur_days"], 1.0))
        start_iso, end_iso = _iso(it["start_jd"]), _iso(end_jd)
        if start_iso == end_iso:
            continue  # sub-day sliver / collapsed tail
        periods.append({
            "lord_name": it["lord_name"],
            "start": start_iso,
            "end": end_iso,
            "current": start_iso <= today < end_iso,
        })

    return {"system": label, "system_key": system_key,
            "lord_type": lord_type, "periods": periods}


class AstrologyCompute:
    """Core astrology calculations using PyJHora"""

    # Expose the module-level availability flag as a class attribute so callers
    # (e.g. the /health endpoint) can read AstrologyCompute.PYJHORA_AVAILABLE.
    PYJHORA_AVAILABLE = PYJHORA_AVAILABLE

    @staticmethod
    def calculate_birth_chart(dob: str, tob: str, place: str,
                             lat: Optional[float] = None, lon: Optional[float] = None,
                             tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Calculate birth chart with planetary positions"""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        try:
            _set_ayanamsa(ayanamsa)
            # Parse date/time
            year, month, day = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            # Default location if not provided
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default

            tz_offset = tz or 5.5  # IST default

            # Calculate JD
            jd = swe.julday(year, month, day, hour + minute/60)

            # Create Place object
            place_obj = drik.Place(place, lat, lon, tz_offset)

            # Calculate D1 (Rasi) chart
            d1_chart = charts.rasi_chart(jd, place_obj)

            # Calculate D9 (Navamsa) chart
            d9_chart = charts.divisional_chart(jd, place_obj, divisional_chart_factor=9)

            # Get ascendant from D1 chart (first element)
            ascendant = d1_chart[0][1]  # [planet_name, (rasi, degrees)]

            # Planet name mapping (PyJHora convention: 0=Sun, 1=Moon, 2=Mars, 3=Mercury, 4=Jupiter, 5=Venus, 6=Saturn, 7=Rahu, 8=Ketu)
            planet_names = {
                0: "Sun", 1: "Moon", 2: "Mars", 3: "Mercury",
                4: "Jupiter", 5: "Venus", 6: "Saturn", 7: "Rahu", 8: "Ketu"
            }

            # Zodiac sign names
            zodiac_names = [
                "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
            ]

            # Nakshatra names
            nakshatra_names = [
                "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
                "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
                "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
                "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
                "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
            ]

            # Helper function to get nakshatra from longitude
            def get_nakshatra_from_longitude(longitude):
                """Calculate nakshatra and pada from absolute longitude"""
                # Each nakshatra is 13°20' (13.333333°)
                nakshatra_span = 360.0 / 27.0
                nakshatra_index = int(longitude / nakshatra_span)
                pada_span = nakshatra_span / 4.0
                pada = int((longitude % nakshatra_span) / pada_span) + 1
                return nakshatra_index, pada

            # Calculate nakshatra for ascendant
            ascendant_longitude = ascendant[0] * 30.0 + ascendant[1]
            ascendant_nakshatra_idx, ascendant_pada = get_nakshatra_from_longitude(ascendant_longitude)

            # Format planetary positions for D1 with nakshatras
            d1_planets = {}
            for planet_index, (rasi, degrees) in d1_chart[1:]:  # Skip ascendant at index 0
                planet_name = planet_names.get(planet_index, f"Planet_{planet_index}")
                # Calculate absolute longitude
                absolute_longitude = rasi * 30.0 + degrees
                nakshatra_idx, pada = get_nakshatra_from_longitude(absolute_longitude)

                d1_planets[planet_name] = {
                    "rasi": rasi,
                    "degrees": round(degrees, 2),
                    "sign_name": zodiac_names[rasi],
                    "nakshatra": nakshatra_names[nakshatra_idx],
                    "nakshatra_pada": pada,
                    "absolute_longitude": round(absolute_longitude, 2)
                }

            # Format planetary positions for D9
            # Include 1-based 'house' so the frontend chart component can render D9
            d9_planets = {}
            for planet_index, (rasi, degrees) in d9_chart[1:]:
                planet_name = planet_names.get(planet_index, f"Planet_{planet_index}")
                d9_planets[planet_name] = {
                    "rasi": rasi,
                    "house": rasi + 1,  # Convert from 0-based rasi to 1-based house
                    "degrees": round(degrees, 2),
                    "sign_name": zodiac_names[rasi]
                }

            # D9 (Navamsa) ascendant / lagna — index 0 of the divisional chart
            d9_ascendant = d9_chart[0][1]  # (rasi, degrees)
            d9_lagna = {
                "house": d9_ascendant[0] + 1,  # 1-based for frontend
                "degrees": round(d9_ascendant[1], 2),
                "sign_name": zodiac_names[d9_ascendant[0]]
            }

            # Format for frontend chart component (expects 'house' which is 1-based instead of 'rasi' which is 0-based)
            planets_for_chart = {}
            for planet_index, (rasi, degrees) in d1_chart[1:]:
                planet_name = planet_names.get(planet_index, f"Planet_{planet_index}")
                planets_for_chart[planet_name] = {
                    "house": rasi + 1,  # Convert from 0-based rasi to 1-based house
                    "degrees": round(degrees, 2),
                    "sign_name": zodiac_names[rasi]
                }

            # Bhava arudhas (AL/UL/A2..) for the Rasi (D1) and Navamsa (D9), each computed
            # on its own positions, so the frontend can overlay them on either chart.
            try:
                d1_arudha_padas = _format_arudha_padas(
                    arudhas.bhava_arudhas_from_planet_positions(d1_chart))
                d9_arudha_padas = _format_arudha_padas(
                    arudhas.bhava_arudhas_from_planet_positions(d9_chart))
            except Exception:
                d1_arudha_padas = []
                d9_arudha_padas = []

            return {
                "status": "success",
                "dob": dob,
                "tob": tob,
                "place": place,
                "ascendant": {
                    "rasi": ascendant[0],
                    "degrees": round(ascendant[1], 2),
                    "sign_name": zodiac_names[ascendant[0]],
                    "nakshatra": nakshatra_names[ascendant_nakshatra_idx],
                    "nakshatra_pada": ascendant_pada,
                    "absolute_longitude": round(ascendant_longitude, 2)
                },
                "lagna": {
                    "house": ascendant[0] + 1,  # Convert from 0-based to 1-based for frontend
                    "degrees": round(ascendant[1], 2),
                    "sign_name": zodiac_names[ascendant[0]],
                    "nakshatra": nakshatra_names[ascendant_nakshatra_idx],
                    "nakshatra_pada": ascendant_pada
                },
                "planets": planets_for_chart,  # For frontend chart component
                "d9_lagna": d9_lagna,  # Navamsa ascendant for D9 chart rendering
                "d1_chart": d1_planets,
                "d9_chart": d9_planets,
                "d1_arudha_padas": d1_arudha_padas,
                "d9_arudha_padas": d9_arudha_padas,
                "d1_houses": [[p[1][0]] for p in d1_chart],  # House-wise planet placement
                "d9_houses": [[p[1][0]] for p in d9_chart]
            }

        except Exception as e:
            print(f"Birth chart calculation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            # Restore the default so other endpoints aren't affected by this request.
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # Alias for backwards compatibility
    get_birth_chart = calculate_birth_chart

    @staticmethod
    def calculate_divisional_chart(dob: str, tob: str, place: str,
                                   varga_factor: int = 9,
                                   lat: Optional[float] = None, lon: Optional[float] = None,
                                   tz: Optional[float] = None,
                                   ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Compute a single divisional (varga) chart, formatted for the frontend
        Kundali component (planets keyed by name with a 1-based `house`, plus a
        `lagna`). `varga_factor` must be one of SUPPORTED_VARGAS."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        if varga_factor not in SUPPORTED_VARGAS:
            return {"error": f"Unsupported varga factor: {varga_factor}", "status": "failed"}

        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz or 5.5  # IST default

            jd = swe.julday(year, month, day, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            chart = charts.divisional_chart(jd, place_obj, divisional_chart_factor=varga_factor)

            # Ascendant / lagna is index 0; planets follow.
            asc_rasi, asc_deg = chart[0][1]
            lagna = {
                "house": asc_rasi + 1,  # 1-based for the frontend
                "degrees": round(asc_deg, 2),
                "sign_name": ZODIAC_NAMES[asc_rasi],
            }

            planets = {}
            for planet_index, (rasi, degrees) in chart[1:]:
                name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
                planets[name] = {
                    "rasi": rasi,
                    "house": rasi + 1,  # 1-based for the frontend
                    "degrees": round(degrees, 2),
                    "sign_name": ZODIAC_NAMES[rasi],
                }

            # Bhava arudhas computed on THIS varga's own positions (not the D1 arudhas)
            # so the frontend can overlay AL/UL/A2.. in the divisional chart's cells.
            try:
                arudha_padas = _format_arudha_padas(
                    arudhas.bhava_arudhas_from_planet_positions(chart)
                )
            except Exception:
                arudha_padas = []

            code, name, significance = SUPPORTED_VARGAS[varga_factor]
            return {
                "status": "success",
                "varga": varga_factor,
                "code": code,
                "name": name,
                "significance": significance,
                "lagna": lagna,
                "planets": planets,
                "arudha_padas": arudha_padas,
            }
        except Exception as e:
            print(f"Divisional chart calculation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_dashas(dob: str, tob: str, place: str, dhasa_type: str = "vimsottari",
                lat: Optional[float] = None, lon: Optional[float] = None, tz: Optional[float] = None) -> Dict:
        """
        Calculate Dasha periods (life periods) using PyJHora's accurate calculations
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        try:
            from datetime import datetime

            # Parse date/time
            year, month, day = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            second = int(time_parts[2]) if len(time_parts) > 2 else 0

            # Default location if not provided
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default

            tz_offset = tz or 5.5  # IST default

            # Calculate JD
            jd = swe.julday(year, month, day, hour + minute/60.0 + second/3600.0)

            # Create Place object
            place_obj = drik.Place(place, lat, lon, tz_offset)

            # Get Mahadasha using PyJHora's built-in function
            mahadashas = vimsottari.vimsottari_mahadasa(jd, place_obj)

            # Planet name mapping (PyJHora standard indexing)
            # 0=Sun, 1=Moon, 2=Mars, 3=Mercury, 4=Jupiter, 5=Venus, 6=Saturn, 7=Rahu, 8=Ketu
            planet_names = {
                0: "Sun",
                1: "Moon",
                2: "Mars",
                3: "Mercury",
                4: "Jupiter",
                5: "Venus",
                6: "Saturn",
                7: "Rahu",
                8: "Ketu"
            }

            # Sort mahadashas by start date to get chronological order
            sorted_mahadashas = sorted(mahadashas.items(), key=lambda x: x[1])

            # Convert to list with dates
            dasha_periods = []
            lords_list = [lord for lord, _ in sorted_mahadashas]

            for i, lord in enumerate(lords_list):
                start_jd = mahadashas[lord]

                # Get end date from next dasha start
                if i + 1 < len(lords_list):
                    next_lord = lords_list[i + 1]
                    end_jd = mahadashas[next_lord]
                else:
                    # Last dasha - add the duration
                    duration_years = vimsottari.vimsottari_dict[lord]
                    end_jd = start_jd + duration_years * vimsottari.year_duration

                # Convert JD to datetime
                start_date_parts = utils.jd_to_gregorian(start_jd)
                start_date = datetime(start_date_parts[0], start_date_parts[1], start_date_parts[2])

                end_date_parts = utils.jd_to_gregorian(end_jd)
                end_date = datetime(end_date_parts[0], end_date_parts[1], end_date_parts[2])

                duration_years = (end_jd - start_jd) / vimsottari.year_duration

                # Calculate bhuktis (sub-periods) using PyJHora
                bhuktis = vimsottari._vimsottari_bhukti(lord, start_jd)
                sub_periods = []
                bhukti_lords = list(bhuktis.keys())

                for j, bhukti_lord in enumerate(bhukti_lords):
                    bhukti_start_jd = bhuktis[bhukti_lord]

                    # Get bhukti end date
                    if j + 1 < len(bhukti_lords):
                        bhukti_end_jd = bhuktis[bhukti_lords[j + 1]]
                    else:
                        bhukti_end_jd = end_jd

                    bhukti_start_parts = utils.jd_to_gregorian(bhukti_start_jd)
                    bhukti_start_date = datetime(bhukti_start_parts[0], bhukti_start_parts[1], bhukti_start_parts[2])

                    bhukti_end_parts = utils.jd_to_gregorian(bhukti_end_jd)
                    bhukti_end_date = datetime(bhukti_end_parts[0], bhukti_end_parts[1], bhukti_end_parts[2])

                    bhukti_duration_years = (bhukti_end_jd - bhukti_start_jd) / vimsottari.year_duration

                    sub_periods.append({
                        "lord": planet_names.get(bhukti_lord, str(bhukti_lord)),
                        "duration_months": round(bhukti_duration_years * 12, 1),
                        "start_date": bhukti_start_date.strftime("%Y-%m-%d"),
                        "end_date": bhukti_end_date.strftime("%Y-%m-%d"),
                        "order": j + 1
                    })

                dasha_periods.append({
                    "lord": planet_names.get(lord, str(lord)),
                    "duration_years": round(duration_years, 2),
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "sub_periods": sub_periods,
                    "order": i + 1
                })

            # Find current dasha and next dasha
            current_datetime = datetime.now()
            current_dasha = None
            next_dasha = None
            current_bhukthi_periods = []

            for i, dasha in enumerate(dasha_periods):
                dasha_start = datetime.strptime(dasha["start_date"], "%Y-%m-%d")
                dasha_end = datetime.strptime(dasha["end_date"], "%Y-%m-%d")

                if dasha_start <= current_datetime <= dasha_end:
                    current_dasha = dasha
                    current_bhukthi_periods = dasha["sub_periods"]
                    if i + 1 < len(dasha_periods):
                        next_dasha = dasha_periods[i + 1]
                    break

            # Get nakshatra for reference
            nakshatra_data = drik.nakshatra(jd, place_obj)
            nakshatra_index = nakshatra_data[0]

            # Prepare response
            response = {
                "status": "success",
                "dob": dob,
                "tob": tob,
                "place": place,
                "dhasa_type": dhasa_type,
                "current_nakshatra_index": nakshatra_index,
                "dasha_sequence": dasha_periods,
                "total_cycle_years": 120,
                "note": "Vimsottari Dasha cycle is 120 years. Calculations based on PyJHora."
            }

            # Add current dasha if found
            if current_dasha:
                response["current_dasha"] = {
                    "lord": current_dasha["lord"],
                    "duration_years": current_dasha["duration_years"],
                    "start_date": current_dasha["start_date"],
                    "end_date": current_dasha["end_date"],
                    "description": f"You are currently in {current_dasha['lord']} Dasha"
                }
                response["current_bhukthi"] = {
                    "description": f"Sub-periods within {current_dasha['lord']} Dasha",
                    "periods": current_bhukthi_periods
                }

            # Add next dasha if found
            if next_dasha:
                response["next_dasha"] = {
                    "lord": next_dasha["lord"],
                    "duration_years": next_dasha["duration_years"],
                    "start_date": next_dasha["start_date"],
                    "end_date": next_dasha["end_date"],
                    "description": f"After current dasha, {next_dasha['lord']} Dasha begins"
                }

            return response

        except Exception as e:
            print(f"Dasha calculation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_dasha_children(dob: str, tob: str, place: str, lords_path: List[str],
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None) -> Dict:
        """Lazily compute the immediate child periods of a Vimsottari node.

        `lords_path` is the chain of planet names from the Maha Dasha down to the
        node whose children we want, e.g. ["Venus"] -> Bhuktis, ["Venus","Saturn"]
        -> Antaras, ["Venus","Saturn","Mercury"] -> Sookshmas. We walk the path
        from the natal chart with PyJHora's `vimsottari_immediate_children` so every
        level is recomputed at full (sub-day) precision rather than from rounded
        dates. Levels: 1=Maha, 2=Bhukti, 3=Antara, 4=Sookshma (leaf)."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        if not lords_path:
            return {"error": "lords_path is required", "status": "failed"}

        try:
            year, month, day = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            second = int(time_parts[2]) if len(time_parts) > 2 else 0

            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz or 5.5

            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            # Resolve the requested lord-path (names -> PyJHora indices).
            try:
                path_idx = [PLANET_INDICES[name] for name in lords_path]
            except KeyError as bad:
                return {"error": f"Unknown dasha lord: {bad}", "status": "failed"}

            if len(path_idx) >= 4:
                # Sookshma is the deepest level we expose — it has no children.
                return {"status": "success", "level": len(path_idx) + 1, "children": []}

            # Level 1: locate the Maha Dasha's precise span.
            mahadashas = vimsottari.vimsottari_mahadasa(jd, place_obj)
            sorted_md = sorted(mahadashas.items(), key=lambda x: x[1])
            lords_list = [lord for lord, _ in sorted_md]

            maha = path_idx[0]
            if maha not in lords_list:
                return {"error": "Invalid maha dasha lord", "status": "failed"}
            mi = lords_list.index(maha)
            start_jd = mahadashas[maha]
            if mi + 1 < len(lords_list):
                end_jd = mahadashas[lords_list[mi + 1]]
            else:
                end_jd = start_jd + vimsottari.vimsottari_dict[maha] * vimsottari.year_duration

            cur_path = [maha]
            cur_start = utils.jd_to_gregorian(start_jd)  # (y, m, d, fractional_hour)
            cur_end = utils.jd_to_gregorian(end_jd)

            # Walk down the path, recomputing each level so spans stay precise.
            for next_lord in path_idx[1:]:
                kids = vimsottari.vimsottari_immediate_children(
                    cur_path, cur_start, parent_end=cur_end)
                match = next((k for k in kids if k[0][-1] == next_lord), None)
                if match is None:
                    return {"error": "Invalid dasha path", "status": "failed"}
                cur_path = list(match[0])
                cur_start, cur_end = match[1], match[2]

            # Children of the resolved node.
            kids = vimsottari.vimsottari_immediate_children(
                cur_path, cur_start, parent_end=cur_end)

            def _tuple_to_jd(t):
                y, m, d, fh = t
                return utils.julian_day_number(drik.Date(y, m, d), (fh, 0, 0))

            def _fmt(t):
                return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"

            child_level = len(cur_path) + 1  # 3=Antara, 4=Sookshma
            children = []
            for child_path, s_t, e_t in kids:
                dur_years = (_tuple_to_jd(e_t) - _tuple_to_jd(s_t)) / vimsottari.year_duration
                children.append({
                    "lord": PLANET_NAMES.get(child_path[-1], str(child_path[-1])),
                    "path": [PLANET_NAMES.get(p, str(p)) for p in child_path],
                    "level": child_level,
                    "start_date": _fmt(s_t),
                    "end_date": _fmt(e_t),
                    "duration_years": round(dur_years, 3),
                    "duration_months": round(dur_years * 12, 2),
                    "duration_days": round(dur_years * 365.25, 1),
                })

            return {
                "status": "success",
                "level": child_level,
                "parent_path": [PLANET_NAMES.get(p, str(p)) for p in cur_path],
                "children": children,
            }

        except Exception as e:
            print(f"Dasha children error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_dasha_periods(dhasa_type: str, dob: str, tob: str, place: str,
                          lat: Optional[float] = None, lon: Optional[float] = None,
                          tz: Optional[float] = None) -> Dict:
        """Maha-level periods for one of the non-Vimsottari dasha systems.

        `dhasa_type` is a key in SUPPORTED_DASHAS. Graha systems (yogini,
        ashtottari) return planet lords; raasi systems (narayana, kalachakra)
        return rasi signs. Output is normalized to a flat list of periods with
        ISO start/end dates so the frontend can render any system uniformly.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        meta = SUPPORTED_DASHAS.get(dhasa_type)
        if not meta:
            return {"error": f"Unsupported dhasa type: {dhasa_type}", "status": "failed"}
        try:
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz or 5.5
            dob_t = (year, month, day)
            tob_t = (hour, minute, second)
            place_obj = drik.Place(place, lat, lon, tz_offset)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)

            # Each branch returns rows shaped [lord_or_(lord,), (Y,M,D,frac), dur_years]
            if dhasa_type == "yogini":
                rows = yogini.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "ashtottari":
                rows = ashtottari.get_ashtottari_dhasa_bhukthi(jd, place_obj, dhasa_level_index=1)
            elif dhasa_type == "narayana":
                rows = narayana.narayana_dhasa_for_rasi_chart(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "kalachakra":
                rows = kalachakra.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            # ── Additional graha (nakshatra) dashas ────────────────────────
            elif dhasa_type == "shodasottari":
                rows = shodasottari.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "dwadasottari":
                rows = dwadasottari.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "panchottari":
                rows = panchottari.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "shatabdika":
                rows = sataatbika.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            # ── Additional raasi (sign) dashas ─────────────────────────────
            elif dhasa_type == "kendradhi_rasi":
                rows = kendradhi_rasi.kendradhi_rasi_dhasa(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "sudasa":
                rows = sudasa.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "drig":
                _pp = charts.rasi_chart(jd, place_obj)
                rows = drig.drig_dhasa(_pp, dob_t, tob_t, dhasa_level_index=1)
            elif dhasa_type == "chara":
                rows = chara.get_dhasa_antardhasa(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "sthira":
                rows = sthira.get_dhasa_antardhasa(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "trikona":
                rows = trikona.get_dhasa_antardhasa(dob_t, tob_t, place_obj, dhasa_level_index=1)
            else:
                return {"error": f"Unsupported dhasa type: {dhasa_type}", "status": "failed"}

            names = ZODIAC_NAMES if meta["lord_type"] == "raasi" else None

            def _lord_name(raw):
                idx = raw[0] if isinstance(raw, (tuple, list)) else raw
                if names is not None:
                    return names[idx % 12]
                return PLANET_NAMES.get(idx, str(idx))

            def _fmt(t):
                return f"{int(t[0]):04d}-{int(t[1]):02d}-{int(t[2]):02d}"

            def _to_jd(t):
                return swe.julday(int(t[0]), int(t[1]), int(t[2]), float(t[3]))

            # Dedupe to maha-level rows (depth=1 already, but guard) and order.
            periods = []
            for i, row in enumerate(rows):
                lord_raw, start_t, dur = row[0], row[1], row[2]
                start_jd = _to_jd(start_t)
                if i + 1 < len(rows):
                    end_t = rows[i + 1][1]
                else:
                    end_jd = start_jd + float(dur) * 365.25
                    y2, m2, d2, _h2 = swe.revjul(end_jd)
                    end_t = (y2, m2, d2, 0)
                periods.append({
                    "lord": _lord_name(lord_raw),
                    "start_date": _fmt(start_t),
                    "end_date": _fmt(end_t),
                    "duration_years": round(float(dur), 2),
                })

            return {
                "status": "success",
                "dhasa_type": dhasa_type,
                "name": meta["name"],
                "lord_type": meta["lord_type"],
                "description": meta["description"],
                "periods": periods,
            }
        except Exception as e:
            print(f"Dasha periods error ({dhasa_type}): {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_ashtakavarga(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None,
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Bhinna (per-contributor) + Sarva (combined) Ashtakavarga bindu tables."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0)
            pp = charts.rasi_chart(jd, place_obj)
            h2p = utils.get_house_planet_list_from_planet_positions(pp)
            bav, sav, _ = ashtakavarga.get_ashtaka_varga(h2p)
            # The 8 BAV contributors, in PyJHora's order.
            contributors = ["Sun", "Moon", "Mars", "Mercury", "Jupiter",
                            "Venus", "Saturn", "Ascendant"]
            bhinna = {
                contributors[i]: [int(x) for x in row]
                for i, row in enumerate(bav)
            }
            return {
                "status": "success",
                "signs": ZODIAC_NAMES,
                "bhinna": bhinna,
                "sarva": [int(x) for x in sav],
                "sarva_total": int(sum(sav)),
            }
        except Exception as e:
            print(f"Ashtakavarga error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_birth_time_rectification(dob: str, tob: str, place: str,
                                     lat: Optional[float] = None, lon: Optional[float] = None,
                                     tz: Optional[float] = None,
                                     ayanamsa: str = DEFAULT_AYANAMSA,
                                     method: str = "nakshatra",
                                     gender: Optional[int] = None) -> Dict:
        """EXPERIMENTAL birth-time rectification (BV Raman suddhi methods).

        PyJHora itself flags these "experimental - accuracy not guaranteed", so the
        result is framed as a *suggestion to verify*, never an authoritative correction.
        Nudges the entered time within +/-(step*loop) minutes until the chosen suddhi
        check is satisfied and returns entered-vs-suggested time, the delta, which rule
        fired, and before/after chart summaries so the caller can render both kundalis.

        method: "nakshatra" (nakshatra suddhi - self-serve, no extra input),
                "lagna" (lagna suddhi) or "janma" (janma suddhi, needs `gender`:
                0=male, 1=female).
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}

        method_labels = {
            "nakshatra": "Nakshatra Suddhi",
            "lagna": "Lagna Suddhi",
            "janma": "Janma Suddhi",
        }
        if method not in method_labels:
            return {"error": f"Unknown method '{method}'", "status": "failed"}
        if method == "janma" and gender not in (0, 1):
            return {"error": "Janma suddhi requires gender (0=male, 1=female)",
                    "status": "failed"}

        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz or 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            base_fh = hour + minute / 60.0 + second / 3600.0
            jd = swe.julday(year, month, day, base_fh)

            step = float(const.birth_rectification_step_minutes)
            loop_count = int(const.birth_rectification_loop_count)
            window_minutes = round(step * loop_count, 2)

            adjust_minutes = None   # None => could not converge within the window
            already_ok = False

            if method == "nakshatra":
                # The engine self-derives the expected janma star from the birth-time
                # ishtakaal and returns: 0 (already matches), a revised (h,m,s) tuple,
                # or [rectification_required, closest_star] when it could not converge.
                res = drik._birthtime_rectification_nakshathra_suddhi(jd, place_obj)
                if isinstance(res, tuple):
                    rh, rm, rs = float(res[0]), float(res[1]), float(res[2])
                    new_fh = rh + rm / 60.0 + rs / 3600.0
                    # The engine returns only a time-of-day (no date), so a converged
                    # time that crossed midnight looks ~24h away. The search is bounded
                    # to +/-window minutes, so wrap the raw diff into the nearest
                    # +/-12h to recover the true (small) signed delta.
                    raw = ((new_fh - base_fh) + 12.0) % 24.0 - 12.0
                    adjust_minutes = round(raw * 60.0, 4)
                elif isinstance(res, (int, float)) and not isinstance(res, bool):
                    adjust_minutes = 0.0
                    already_ok = True
                else:
                    adjust_minutes = None  # did not converge
            else:
                # lagna/janma suddhi only return a bool (True => rectification needed),
                # so wrap them in a symmetric +/- search that mirrors the engine's own
                # nakshatra loop (try +l, then -l; first satisfied time wins).
                def _needs(jdx):
                    if method == "lagna":
                        return drik._birthtime_rectification_lagna_suddhi(jdx, place_obj)
                    return drik._birthtime_rectification_janma_suddhi(jdx, place_obj, gender)

                if not _needs(jd):
                    adjust_minutes = 0.0
                    already_ok = True
                else:
                    for l in range(1, loop_count + 1):
                        found = False
                        for sign in (1, -1):
                            adj = sign * l * step
                            if not _needs(jd + adj / 1440.0):
                                adjust_minutes = round(adj, 4)
                                found = True
                                break
                        if found:
                            break

            def _tob_str(h, m, s):
                return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

            entered = {
                "dob": dob,
                "tob": _tob_str(hour, minute, second),
            }

            suggested = None
            after_chart = None
            if adjust_minutes is not None and abs(adjust_minutes) > 1e-6:
                jd_new = jd + adjust_minutes / 1440.0
                ny, nm, nd, nfh = utils.jd_to_gregorian(jd_new)
                sh, smn, ss = utils.to_dms(nfh, as_string=False)
                suggested = {
                    "dob": f"{int(ny):04d}-{int(nm):02d}-{int(nd):02d}",
                    "tob": _tob_str(sh, smn, ss),
                }

            # Before/after chart summaries (reuse the birth-chart renderer so the page
            # can draw both kundalis with the same component).
            before_chart = AstrologyCompute.calculate_birth_chart(
                dob, entered["tob"], place, lat, lon, tz, ayanamsa)
            if suggested is not None:
                after_chart = AstrologyCompute.calculate_birth_chart(
                    suggested["dob"], suggested["tob"], place, lat, lon, tz, ayanamsa)

            def _moon(chart):
                try:
                    m = chart["d1_chart"]["Moon"]
                    return {"nakshatra": m.get("nakshatra"), "pada": m.get("nakshatra_pada"),
                            "sign_name": m.get("sign_name")}
                except Exception:
                    return None

            def _lagna(chart):
                try:
                    la = chart.get("lagna", {})
                    return {"sign_name": la.get("sign_name"), "nakshatra": la.get("nakshatra"),
                            "pada": la.get("nakshatra_pada")}
                except Exception:
                    return None

            rectified = suggested is not None
            if rectified:
                note = ("Experimental suggestion - the entered time did not satisfy the "
                        f"{method_labels[method]} check; the closest time within "
                        f"+/-{int(window_minutes)} min that does is shown. Verify against "
                        "known life events; this is a heuristic, not authoritative.")
            elif already_ok:
                note = (f"The entered time already satisfies the {method_labels[method]} "
                        "check - no rectification suggested.")
            else:
                note = (f"Could not rectify within +/-{int(window_minutes)} min using "
                        f"{method_labels[method]}. Try another method or a wider review.")

            return {
                "status": "success",
                "experimental": True,
                "method": method,
                "method_label": method_labels[method],
                "gender": gender,
                "entered": entered,
                "suggested": suggested,
                "delta_minutes": adjust_minutes,
                "rectified": rectified,
                "already_consistent": already_ok,
                "converged": adjust_minutes is not None,
                "window_minutes": window_minutes,
                "step_minutes": step,
                "before": {"moon": _moon(before_chart), "lagna": _lagna(before_chart)},
                "after": ({"moon": _moon(after_chart), "lagna": _lagna(after_chart)}
                          if after_chart else None),
                "before_chart": before_chart,
                "after_chart": after_chart,
                "note": note,
            }
        except Exception as e:
            print(f"Birth-time rectification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_event_rectification(dob: str, tob: str, place: str,
                                events: List[Dict],
                                lat: Optional[float] = None, lon: Optional[float] = None,
                                tz: Optional[float] = None,
                                ayanamsa: str = DEFAULT_AYANAMSA,
                                window_minutes: int = 120) -> Dict:
        """EXPERIMENTAL event-based birth-time rectification.

        Given a set of dated life events, scan candidate birth times within the day
        and pick the one whose Vimsottari dasha (maha+bhukti running at each event)
        and Jupiter/Saturn transits best match the events' classical significators.
        Deterministic + auditable: returns the per-event matches behind the score.

        events: [{"type": <EVENT_SIGNIFICATORS key>, "date": "YYYY-MM-DD"}, ...]
        window_minutes: half-window searched around the entered time (clamped to the
                        same calendar day). e.g. 120 => +/-2h; 720 => whole day.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}

        # Validate + normalise events.
        clean_events = []
        for ev in (events or []):
            etype = (ev or {}).get("type")
            edate = (ev or {}).get("date")
            if etype not in EVENT_SIGNIFICATORS or not edate:
                continue
            try:
                ey, em, ed = map(int, str(edate).split("-")[:3])
                clean_events.append({"type": etype, "date": f"{ey:04d}-{em:02d}-{ed:02d}",
                                     "ymd": (ey, em, ed)})
            except Exception:
                continue
        if not clean_events:
            return {"error": "Provide at least one dated life event.", "status": "failed"}

        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz or 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            base_fh = hour + minute / 60.0 + second / 3600.0

            # Precompute each event's JD (noon local) + the transiting Jupiter/Saturn
            # signs on that day (birth-time-independent → computed once per event).
            for ev in clean_events:
                ey, em, ed = ev["ymd"]
                ev_jd = swe.julday(ey, em, ed, 12.0)
                ev["jd"] = ev_jd
                tchart = charts.rasi_chart(ev_jd, place_obj)
                tsigns = {pi: rasi for pi, (rasi, _deg) in tchart[1:]}
                ev["jup_sign"] = tsigns.get(4)
                ev["sat_sign"] = tsigns.get(6)

            yd = vimsottari.year_duration
            vdict = vimsottari.vimsottari_dict

            def _periods_for(jd):
                """Flat Vimsottari maha+bhukti timeline: [(start_jd, end_jd, maha, bhukti)]."""
                mahad = vimsottari.vimsottari_mahadasa(jd, place_obj)
                smd = sorted(mahad.items(), key=lambda x: x[1])
                out = []
                for i, (mlord, mstart) in enumerate(smd):
                    mend = smd[i + 1][1] if i + 1 < len(smd) else mstart + vdict[mlord] * yd
                    bh = vimsottari._vimsottari_bhukti(mlord, mstart)
                    sbh = sorted(bh.items(), key=lambda x: x[1])
                    for j, (blord, bstart) in enumerate(sbh):
                        bend = sbh[j + 1][1] if j + 1 < len(sbh) else mend
                        out.append((bstart, bend, mlord, blord))
                return out

            def _lords_at(periods, ev_jd):
                for (s, e, m, b) in periods:
                    if s <= ev_jd < e:
                        return m, b
                # Before the first / after the last computed period.
                if periods and ev_jd < periods[0][0]:
                    return periods[0][2], periods[0][3]
                return (periods[-1][2], periods[-1][3]) if periods else (None, None)

            def _score_event(etype, maha, bhukti, lagna_sign, planet_signs, jup_sign, sat_sign):
                sig = EVENT_SIGNIFICATORS[etype]
                houses, karakas = sig["houses"], sig["karakas"]
                house_lords = {SIGN_LORD[(lagna_sign + h - 1) % 12] for h in houses}
                in_sig = {pi for pi, ps in planet_signs.items()
                          if (((ps - lagna_sign) % 12) + 1) in houses}
                s = 0.0
                reasons = []
                mn = PLANET_NAMES.get(maha, "?")
                bn = PLANET_NAMES.get(bhukti, "?")
                if maha in house_lords:
                    s += 3.0; reasons.append(f"Mahadasha {mn} rules a house of {etype}")
                if maha in karakas:
                    s += 3.0; reasons.append(f"Mahadasha {mn} is a natural significator of {etype}")
                if maha in in_sig:
                    s += 1.5; reasons.append(f"Mahadasha {mn} occupies a house of {etype}")
                if bhukti in house_lords:
                    s += 1.5; reasons.append(f"Bhukti {bn} rules a house of {etype}")
                if bhukti in karakas:
                    s += 1.5; reasons.append(f"Bhukti {bn} is a natural significator of {etype}")
                if bhukti in in_sig:
                    s += 0.75; reasons.append(f"Bhukti {bn} occupies a house of {etype}")
                if jup_sign is not None and (((jup_sign - lagna_sign) % 12) + 1) in houses:
                    s += 0.5; reasons.append("Jupiter transits a house of " + etype)
                if sat_sign is not None and (((sat_sign - lagna_sign) % 12) + 1) in houses:
                    s += 0.5; reasons.append("Saturn transits a house of " + etype)
                return s, reasons

            def _eval(fh):
                jd = swe.julday(year, month, day, fh)
                d1 = charts.rasi_chart(jd, place_obj)
                lagna_sign = int(d1[0][1][0])
                planet_signs = {pi: int(rasi) for pi, (rasi, _d) in d1[1:]}
                periods = _periods_for(jd)
                total = 0.0
                details = []
                for ev in clean_events:
                    maha, bhukti = _lords_at(periods, ev["jd"])
                    sc, reasons = _score_event(ev["type"], maha, bhukti, lagna_sign,
                                               planet_signs, ev["jup_sign"], ev["sat_sign"])
                    total += sc
                    details.append({
                        "type": ev["type"], "date": ev["date"],
                        "maha": PLANET_NAMES.get(maha), "bhukti": PLANET_NAMES.get(bhukti),
                        "score": round(sc, 2), "matched": reasons,
                    })
                return total, details, lagna_sign

            # Two-pass scan: coarse over the (clamped) window, then fine around the best.
            lo = max(0.0, base_fh - window_minutes / 60.0)
            hi = min(24.0 - 1e-6, base_fh + window_minutes / 60.0)

            def _scan(a, b, step_min):
                best = None
                fh = a
                step = step_min / 60.0
                while fh <= b + 1e-9:
                    total, _details, _lag = _eval(fh)
                    if best is None or total > best[1]:
                        best = (fh, total)
                    fh += step
                return best

            coarse = _scan(lo, hi, 15.0)
            c_fh = coarse[0]
            fine = _scan(max(0.0, c_fh - 0.25), min(24.0 - 1e-6, c_fh + 0.25), 2.0)
            best_fh = fine[0] if fine[1] >= coarse[1] else c_fh

            best_total, best_details, _lag = _eval(best_fh)
            base_total, base_details, _blag = _eval(base_fh)

            sh, sm, ss = utils.to_dms(best_fh, as_string=False)
            suggested_tob = f"{int(sh):02d}:{int(sm):02d}:{int(ss):02d}"
            entered_tob = f"{hour:02d}:{minute:02d}:{second:02d}"
            delta_minutes = round((best_fh - base_fh) * 60.0, 1)
            changed = abs(delta_minutes) > 0.5

            # A rough, honest 0-100 "fit" of the best time (≈6 pts = one strong event).
            n = len(clean_events)
            confidence = max(5, min(95, round(best_total / (n * 6.0) * 100)))

            before_chart = AstrologyCompute.calculate_birth_chart(
                dob, entered_tob, place, lat, lon, tz, ayanamsa)
            after_chart = AstrologyCompute.calculate_birth_chart(
                dob, suggested_tob, place, lat, lon, tz, ayanamsa) if changed else None

            def _moon(chart):
                try:
                    m = chart["d1_chart"]["Moon"]
                    return {"nakshatra": m.get("nakshatra"), "pada": m.get("nakshatra_pada"),
                            "sign_name": m.get("sign_name")}
                except Exception:
                    return None

            def _lagna(chart):
                try:
                    la = chart.get("lagna", {})
                    return {"sign_name": la.get("sign_name"), "nakshatra": la.get("nakshatra"),
                            "pada": la.get("nakshatra_pada")}
                except Exception:
                    return None

            if changed:
                note = (f"Experimental — of the candidate times searched (±{window_minutes} min), "
                        f"{suggested_tob} best matches the {n} event(s) supplied "
                        f"(fit ≈ {confidence}%). This is a heuristic; verify against more events "
                        "and reliable records.")
            else:
                note = (f"The entered time already scores best against the {n} event(s) supplied "
                        f"(fit ≈ {confidence}%). Add more events or widen the window to test further.")

            return {
                "status": "success",
                "experimental": True,
                "method": "events",
                "method_label": "Life-events",
                "entered": {"dob": dob, "tob": entered_tob},
                "suggested": {"dob": dob, "tob": suggested_tob} if changed else None,
                "delta_minutes": delta_minutes,
                "rectified": changed,
                "window_minutes": window_minutes,
                "score": round(best_total, 2),
                "base_score": round(base_total, 2),
                "confidence": confidence,
                "events": best_details,
                "entered_events": base_details,
                "before": {"moon": _moon(before_chart), "lagna": _lagna(before_chart)},
                "after": ({"moon": _moon(after_chart), "lagna": _lagna(after_chart)}
                          if after_chart else None),
                "before_chart": before_chart,
                "after_chart": after_chart,
                "note": note,
            }
        except Exception as e:
            print(f"Event rectification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_arudha_padas(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None,
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Bhava arudhas (AL/UL/A2..A11) of the Rasi (D1) chart — each the sign the
        arudha falls in. Arudha Lagna (AL) reflects the *perceived* self/image/status
        (maya), Upapada (UL) the marriage/spouse; the intermediate A2..A11 mirror the
        arudhas of houses 2-11. A focused slice of `get_chart_details` for the AI to
        pull on demand (and to seed the pass-all context)."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)
            pp = charts.rasi_chart(jd, place_obj)
            return {
                "status": "success",
                "arudha_padas": _format_arudha_padas(
                    arudhas.bhava_arudhas_from_planet_positions(pp)),
                "note": ("AL = Arudha Lagna (perceived image/status), UL = Upapada "
                         "(spouse/marriage); A2..A11 are the arudhas of houses 2-11. "
                         "Each value is the rasi the arudha occupies."),
            }
        except Exception as e:
            print(f"Arudha padas error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_chart_details(dob: str, tob: str, place: str,
                          lat: Optional[float] = None, lon: Optional[float] = None,
                          tz: Optional[float] = None,
                          ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Advanced chart factors: Arudha padas, Chara karakas, Special lagnas, Upagrahas."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)
            dob_d = drik.Date(year, month, day)
            tob_t = (hour, minute, second)
            pp = charts.rasi_chart(jd, place_obj)

            def _sign_deg(pair):
                # functions return [sign_index, longitude_within_sign]
                s, d = int(pair[0]), float(pair[1])
                return {"sign_name": ZODIAC_NAMES[s % 12], "degrees": round(d, 2)}

            # Arudha padas A1..A12 (bhava arudhas) for the rasi chart.
            arudha_padas = _format_arudha_padas(arudhas.bhava_arudhas_from_planet_positions(pp))

            # Chara karakas (Jaimini), 8 planets ordered by longitude.
            karaka_names = ["Atma (AK)", "Amatya (AmK)", "Bhratri (BK)", "Matri (MK)",
                            "Pitri (PiK)", "Putra (PK)", "Jnati (GK)", "Dara (DK)"]
            ck = house.chara_karakas(pp)
            chara_karakas = [
                {"karaka": karaka_names[i], "planet": PLANET_NAMES.get(idx, str(idx))}
                for i, idx in enumerate(ck) if i < len(karaka_names)
            ]

            # Special lagnas (each [sign, deg]).
            special_lagnas = []
            for label, fn in [("Sree Lagna", drik.sree_lagna),
                              ("Indu Lagna", drik.indu_lagna),
                              ("Bhrigu Bindu", drik.bhrigu_bindhu_lagna),
                              ("Pranapada Lagna", drik.pranapada_lagna),
                              ("Kunda Lagna", drik.kunda_lagna)]:
                try:
                    special_lagnas.append({"name": label, **_sign_deg(fn(jd, place_obj))})
                except Exception:
                    pass

            # Upagrahas: Gulika/Maandi (kaala-velas) + the five solar upagrahas.
            upagrahas = []
            for label, fn in [("Gulika", drik.gulika_longitude), ("Maandi", drik.maandi_longitude)]:
                try:
                    upagrahas.append({"name": label, **_sign_deg(fn(dob_d, tob_t, place_obj))})
                except Exception:
                    pass
            try:
                sun_long = swe.calc_ut(jd, 0)[0][0]
                solar_names = {"dhuma": "Dhuma", "vyatipaata": "Vyatipata",
                               "parivesha": "Parivesha", "indrachaapa": "Indrachapa",
                               "upaketu": "Upaketu"}
                for key, label in solar_names.items():
                    upagrahas.append({"name": label,
                                      **_sign_deg(drik.solar_upagraha_longitudes(sun_long, key))})
            except Exception:
                pass

            return {
                "status": "success",
                "arudha_padas": arudha_padas,
                "chara_karakas": chara_karakas,
                "special_lagnas": special_lagnas,
                "upagrahas": upagrahas,
            }
        except Exception as e:
            print(f"Chart details error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_shadbala(dob: str, tob: str, place: str,
                     lat: Optional[float] = None, lon: Optional[float] = None,
                     tz: Optional[float] = None,
                     ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Shadbala (six-fold strength) for the seven planets Sun..Saturn."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0)

            sb = strength.shad_bala(jd, place_obj)
            # shad_bala returns [sthana, kaala, dig, cheshta, naisargika, drik,
            #                    total_shashtiamsa, total_rupa, strength_ratio]
            sthana, kaala, dig, cheshta, naisargika, drik_b = sb[0], sb[1], sb[2], sb[3], sb[4], sb[5]
            total_rupa, ratio = sb[7], sb[8]
            required = list(const.shad_bala_factors)
            planets = []
            for p in range(7):  # Sun..Saturn
                planets.append({
                    "planet": PLANET_NAMES[p],
                    "sthana": round(float(sthana[p]), 1),
                    "kaala": round(float(kaala[p]), 1),
                    "dig": round(float(dig[p]), 1),
                    "cheshta": round(float(cheshta[p]), 1),
                    "naisargika": round(float(naisargika[p]), 1),
                    "drik": round(float(drik_b[p]), 1),
                    "total_rupa": round(float(total_rupa[p]), 2),
                    "required_rupa": round(float(required[p]), 2),
                    "strength_ratio": round(float(ratio[p]), 2),
                    "sufficient": float(ratio[p]) >= 1.0,
                })
            # Rank by total rupa (strongest first).
            ranked = sorted(range(len(planets)), key=lambda i: planets[i]["total_rupa"], reverse=True)
            for rank, i in enumerate(ranked, start=1):
                planets[i]["rank"] = rank
            return {
                "status": "success",
                "components": ["sthana", "kaala", "dig", "cheshta", "naisargika", "drik"],
                "planets": planets,
            }
        except Exception as e:
            print(f"Shadbala error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_aspects(dob: str, tob: str, place: str,
                    lat: Optional[float] = None, lon: Optional[float] = None,
                    tz: Optional[float] = None,
                    ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Graha drishti (planetary aspects) + rasi (sign/Jaimini) drishti, with
        Parashari sphuta aspect strength (virupa, 0-100%).

        For each of the nine grahas this returns the houses and planets it casts
        graha drishti on (including the Mars 4/8, Jupiter 5/9, Saturn 3/10 special
        aspects), the planets it aspects by rasi drishti, and a strength % per
        graha→planet aspect so partial aspects can be weighed against full ones.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)
            pp = charts.rasi_chart(jd, place_obj)
            h2p = utils.get_house_planet_list_from_planet_positions(pp)

            # Graha drishti: arp/ahp/app = aspected rasis / houses (0-based from
            # Lagna) / planets, keyed by planet index 0..8.
            _, ahp, app = house.graha_drishti_from_chart(h2p)
            # Rasi (sign) drishti: planets aspected by each planet's sign.
            _, _, apr = house.raasi_drishti_from_chart(h2p)
            # Sphuta aspect strength table: rows = aspecting planet, cols = aspected
            # planets (0..8) then 12 houses; values are 0-100% (100 = full aspect).
            vt = strength.planet_aspect_relationship_table_pvr(
                pp, include_houses=True, normalize_as_percentage=True)

            # Planets that have special aspects beyond the universal 7th (Mars 4/8,
            # Jupiter 5/9, Saturn 3/10).
            special = {2, 4, 6}

            planets = []
            for p in range(9):
                name = PLANET_NAMES.get(p, str(p))
                strength_row = vt[p] if p < len(vt) else []

                def _str(idx):
                    return int(strength_row[idx]) if idx < len(strength_row) else 0

                aspected_planets = [
                    {"planet": PLANET_NAMES.get(q, str(q)), "strength": _str(q)}
                    for q in app.get(p, [])
                ]
                rasi_planets = [PLANET_NAMES.get(q, str(q)) for q in apr.get(p, [])]
                # Houses are 0-based from Lagna in `ahp`; present 1-based, each with
                # its sphuta strength (the house columns of `vt` start at index 9, so
                # house N is column 9 + (N-1)).
                aspected_houses = [
                    {"house": hn, "strength": _str(9 + hn - 1)}
                    for hn in sorted((h % 12) + 1 for h in ahp.get(p, []))
                ]
                planets.append({
                    "planet": name,
                    "special_aspect": p in special,
                    "aspects_houses": aspected_houses,
                    "aspects_planets": aspected_planets,
                    "rasi_drishti_planets": rasi_planets,
                })

            return {
                "status": "success",
                "planets": planets,
                "note": ("strength is Parashari sphuta graha drishti as a percentage "
                         "(0-100; 100 = a full/exact aspect, lower = partial)."),
            }
        except Exception as e:
            print(f"Aspects error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_varshaphal(dob: str, tob: str, place: str, year: int,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None,
                       ayanamsa: str = DEFAULT_AYANAMSA,
                       dasha_system: str = "mudda") -> Dict:
        """Varshaphal / Tajaka annual (solar-return) horoscope for a target year.

        Returns the annual chart (formatted for the Kundali component), the
        year-entry instant, the Muntha (progressed Ascendant), the year-lord
        (Varsheshwara), a curated set of Sahams, the present Tajaka yogas and the
        annual Mudda (Varsha Vimsottari) maha-dasha periods. Birth details +
        ayanamsa are server-injected; global ayanamsa is reset afterwards.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        try:
            birth_year = int(dob.split("-")[0])
            year = int(year)
            # The native attains `age` in the target year; age 0 = birth year.
            # varsha_pravesh(years=N) yields the solar return in (birth_year+N-1),
            # so the annual chart for `year` uses years = age + 1, while
            # lord_of_the_year / muntha / mudda use `age` (they advance from dob).
            age = year - birth_year
            if age < 0:
                return {"error": "Year must be on or after the birth year",
                        "status": "failed"}

            dasha_key = (dasha_system or "mudda").lower()
            if dasha_key not in VARSHA_DASHA_SYSTEMS:
                dasha_key = "mudda"

            _set_ayanamsa(ayanamsa)
            import contextlib
            import io
            from jhora.horoscope.transit import tajaka, saham, tajaka_yoga

            y, m, d = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz or 5.5

            jd_dob = swe.julday(y, m, d, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            # ── Annual (Tajaka) chart ──────────────────────────────────────
            cht, entry = tajaka.varsha_pravesh(jd_dob, place_obj,
                                               divisional_chart_factor=1,
                                               years=age + 1)
            (ey, em, ed), etime = entry
            year_entry = {
                "date": f"{ey:04d}-{em:02d}-{ed:02d}",
                "time": str(etime),
            }

            asc_rasi, asc_deg = cht[0][1]
            lagna = {
                "house": asc_rasi + 1,
                "degrees": round(asc_deg, 2),
                "sign_name": ZODIAC_NAMES[asc_rasi],
            }
            planets = {}
            for planet_index, (rasi, degrees) in cht[1:]:
                name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
                planets[name] = {
                    "rasi": rasi,
                    "house": rasi + 1,
                    "degrees": round(degrees, 2),
                    "sign_name": ZODIAC_NAMES[rasi],
                }

            # ── Muntha: natal Lagna sign advanced one sign per completed year ─
            natal_chart = charts.divisional_chart(jd_dob, place_obj,
                                                  divisional_chart_factor=1)
            natal_asc = natal_chart[0][1][0]
            muntha_sign = tajaka.muntha_house(natal_asc, age)  # 0-11 sign index
            muntha = {
                "sign": muntha_sign,
                "sign_name": ZODIAC_NAMES[muntha_sign],
                "house": ((muntha_sign - asc_rasi) % 12) + 1,
            }

            # ── Year-lord (Varsheshwara) ───────────────────────────────────
            year_lord = None
            try:
                yl_idx = tajaka.lord_of_the_year(jd_dob, place_obj, age)
                if yl_idx is not None and yl_idx in PLANET_NAMES:
                    year_lord = {"index": yl_idx, "planet": PLANET_NAMES[yl_idx]}
            except Exception as e:
                print(f"Varshaphal year-lord error: {e}")

            # Day/night of the annual entry drives the Sahams' day/night formula.
            night_birth = False
            try:
                ann_jd = drik.next_solar_date(jd_dob, place_obj, years=age + 1)
                entry_hrs = drik.jd_to_gregorian(ann_jd)[3]
                sr = utils.from_dms_str_to_dms(drik.sunrise(ann_jd, place_obj)[1])
                ss = utils.from_dms_str_to_dms(drik.sunset(ann_jd, place_obj)[1])
                sr_h = sr[0] + sr[1] / 60.0 + sr[2] / 3600.0
                ss_h = ss[0] + ss[1] / 60.0 + ss[2] / 3600.0
                night_birth = entry_hrs > ss_h or entry_hrs < sr_h
            except Exception as e:
                print(f"Varshaphal night-birth error: {e}")

            # ── Sahams (sensitive points) ──────────────────────────────────
            sahams = []
            for label, fn_name, significance in VARSHAPHAL_SAHAMS:
                try:
                    fn = getattr(saham, fn_name)
                    try:
                        s_long = fn(cht, night_birth)
                    except TypeError:
                        s_long = fn(cht)  # a few sahams take positions only
                    s_long = float(s_long) % 360
                    s_sign = int(s_long // 30)
                    sahams.append({
                        "name": label,
                        "significance": significance,
                        "sign": s_sign,
                        "sign_name": ZODIAC_NAMES[s_sign],
                        "degrees": round(s_long % 30, 2),
                        "house": ((s_sign - asc_rasi) % 12) + 1,
                    })
                except Exception as e:
                    print(f"Varshaphal saham {label} error: {e}")

            # ── Tajaka yogas (curated) ─────────────────────────────────────
            tajaka_yogas = []
            p2h = utils.get_planet_house_dictionary_from_planet_positions(cht)
            _sink = io.StringIO()  # muffle engine debug prints
            try:
                if tajaka_yoga.ishkavala_yoga(p2h):
                    tajaka_yogas.append({
                        "name": "Ishkavala",
                        "description": "Planets confined to kendras and panapharas — "
                                       "indicates wealth, happiness and good fortune.",
                    })
            except Exception:
                pass
            try:
                if tajaka_yoga.induvara_yoga(p2h):
                    tajaka_yogas.append({
                        "name": "Induvara",
                        "description": "Planets confined to apoklimas — cautions of "
                                       "worries, obstacles and ill health.",
                    })
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ith_pairs = tajaka_yoga.get_ithasala_yoga_planet_pairs(cht)
                for p1, p2, _t in ith_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({
                        "name": "Ithasala",
                        "pair": [a, b],
                        "description": f"Applying aspect between {a} and {b} — the "
                                       "matter they signify tends to fructify this year.",
                    })
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ees_pairs = tajaka_yoga.get_eesarpha_yoga_planet_pairs(cht)
                for p1, p2 in ees_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({
                        "name": "Eesarpha",
                        "pair": [a, b],
                        "description": f"Separating aspect between {a} and {b} — the "
                                       "matter they signify tends to slip away or delay.",
                    })
            except Exception:
                pass

            # ── Annual dasha (selectable system: Mudda / Patyayini / Narayana) ─
            label, lord_type = VARSHA_DASHA_SYSTEMS[dasha_key]
            annual_dasha = {"system": label, "system_key": dasha_key,
                            "lord_type": lord_type, "periods": []}
            dob_date = drik.Date(y, m, d)
            tob_tuple = (hour, minute, 0)
            try:
                annual_dasha = _annual_dasha(dasha_key, jd_dob, place_obj, age,
                                             dob_date, tob_tuple)
            except Exception as e:
                print(f"Varshaphal annual-dasha ({dasha_key}) error: {e}")

            return {
                "status": "success",
                "year": year,
                "age": age,
                "year_entry": year_entry,
                "lagna": lagna,
                "planets": planets,
                "muntha": muntha,
                "year_lord": year_lord,
                "sahams": sahams,
                "tajaka_yogas": tajaka_yogas,
                "annual_dasha": annual_dasha,
                "dasha_systems": [
                    {"key": k, "label": v[0], "lord_type": v[1]}
                    for k, v in VARSHA_DASHA_SYSTEMS.items()
                ],
            }
        except Exception as e:
            print(f"Varshaphal error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_horoscope_predictions(dob: str, tob: str, place: str,
                                  lat: Optional[float] = None, lon: Optional[float] = None,
                                  tz: Optional[float] = None,
                                  ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Return a compact, prediction-ready chart summary.

        Reshapes `calculate_birth_chart` into the lagna / moon_sign / sun_sign /
        planetary_positions structure consumed by the LLM prompt builders and the
        basic-prediction fallback. This is the lightweight natal summary; the AI
        endpoints layer the richer dasha/yoga/dosha/transit context on top via
        `chart_context.build_chart_context`.
        """
        chart = AstrologyCompute.calculate_birth_chart(
            dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz, ayanamsa=ayanamsa
        )
        if chart.get("error"):
            return chart

        d1 = chart.get("d1_chart", {})
        moon = d1.get("Moon", {})
        sun = d1.get("Sun", {})
        return {
            "status": "success",
            "birth_details": {"dob": dob, "tob": tob, "place": place},
            "lagna": chart.get("lagna", {}),
            "moon_sign": {
                "sign_name": moon.get("sign_name", "Unknown"),
                "rasi": moon.get("rasi", 0),
                "nakshatra": moon.get("nakshatra", "Unknown"),
                "nakshatra_pada": moon.get("nakshatra_pada", 0),
            },
            "sun_sign": {
                "sign_name": sun.get("sign_name", "Unknown"),
                "rasi": sun.get("rasi", 0),
                "nakshatra": sun.get("nakshatra", "Unknown"),
                "nakshatra_pada": sun.get("nakshatra_pada", 0),
            },
            "planetary_positions": d1,
        }

    @staticmethod
    def get_doshas(dob: str, tob: str, place: str,
                   lat: Optional[float] = None, lon: Optional[float] = None,
                   tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Detect the common doshas for a birth chart (present/absent + description)."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz or 5.5
            jd = swe.julday(year, month, day, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            pp = charts.rasi_chart(jd, place_obj)
            h2p = utils.get_house_planet_list_from_planet_positions(pp)
            moon_rasi, moon_long = pp[2][1]  # pp[0]=Asc, pp[1]=Sun, pp[2]=Moon
            moon_star = drik.nakshatra_pada(moon_rasi * 30 + moon_long)[0]

            def _present(v):
                if isinstance(v, bool):
                    return v
                if isinstance(v, (list, tuple)):
                    return any(x is True for x in v)
                return bool(v)

            catalog = [
                ("kala_sarpa", "Kala Sarpa Dosha", dosha.kala_sarpa(h2p),
                 "All planets fall on one side of the Rahu–Ketu axis. Can bring delays and obstacles, often with strong results later in life."),
                ("manglik", "Manglik (Kuja) Dosha", dosha.manglik(pp),
                 "Mars in certain houses from the Lagna, Moon or Venus. Traditionally weighed in marriage compatibility."),
                ("pitru", "Pitru Dosha", dosha.pitru_dosha(pp),
                 "Affliction linked to the 9th house and the Sun, associated with ancestral karma."),
                ("guru_chandala", "Guru Chandala Dosha", dosha.guru_chandala_dosha(pp),
                 "Jupiter conjunct Rahu or Ketu. Can affect judgement, ethics and guidance."),
                ("ganda_moola", "Ganda Moola Dosha", dosha.ganda_moola(moon_star),
                 "Moon in a gandanta nakshatra (Ashwini, Ashlesha, Magha, Jyeshtha, Mula, Revati). A sensitive early period; remedies are advised."),
                ("kalathra", "Kalathra Dosha", dosha.kalathra(pp),
                 "Affliction to the 7th house and spouse significators, considered for marriage and partnerships."),
                ("ghata", "Ghata Dosha", dosha.ghata(pp),
                 "Mars–Saturn conjunction. Can bring friction, haste and accidents."),
                ("shrapit", "Shrapit Dosha", dosha.shrapit(pp),
                 "Rahu–Saturn conjunction. Associated with chronic, carried-over difficulties."),
            ]
            doshas = [
                {"key": k, "name": n, "present": _present(v), "description": d}
                for (k, n, v, d) in catalog
            ]
            return {
                "status": "success",
                "doshas": doshas,
                "present_count": sum(1 for x in doshas if x["present"]),
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_yogas(dob: str, tob: str, place: str,
                  lat: Optional[float] = None, lon: Optional[float] = None,
                  tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Detect the yogas present in the Rasi chart (name + description + benefits)."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz or 5.5
            jd = swe.julday(year, month, day, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            results, found, total = yoga.get_yoga_details(
                jd, place_obj, divisional_chart_factor=1, language="en"
            )
            yogas = []
            for key, details in results.items():
                # details = [chartID, name, description, benefits]
                yogas.append({
                    "key": key,
                    "name": details[1] if len(details) > 1 else key,
                    "description": details[2] if len(details) > 2 else "",
                    "benefits": details[3] if len(details) > 3 else "",
                })
            yogas.sort(key=lambda y: y["name"])
            return {"status": "success", "yogas": yogas, "found": found, "total": total}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_panchanga(date: Optional[str] = None, place: str = "",
                      lat: Optional[float] = None, lon: Optional[float] = None,
                      tz: Optional[float] = None) -> Dict:
        """Daily almanac (panchanga) for a date + place: the five limbs
        (tithi, vaara, nakshatra, yoga, karana) plus sunrise/sunset and the
        inauspicious/auspicious periods (rahu kalam, yamaganda, gulika,
        durmuhurtam, abhijit). Elements are resolved at sunrise of the day,
        the traditional reference point. `date` defaults to today at `place`."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            if date:
                year, month, day = map(int, date.split("-"))
            else:
                # "Today" in the place's local time, not the server's.
                local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
                year, month, day = local_now.year, local_now.month, local_now.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)

            # Anchor at local noon, then resolve sunrise/sunset; the panchanga
            # limbs are read at sunrise (the prevailing element for the day).
            jd_noon = swe.julday(year, month, day, 12)
            sr = drik.sunrise(jd_noon, place_obj)
            ss = drik.sunset(jd_noon, place_obj)
            jd = sr[2]  # sunrise julian day

            ti = drik.tithi(jd, place_obj)
            tithi_name, paksha = _tithi_name(ti[0])

            nak = drik.nakshatra(jd, place_obj)

            yog = drik.yogam(jd, place_obj)

            kar = drik.karana(jd, place_obj)

            # Read vaara at local noon, not at sunrise: the vedic weekday compares
            # the time-of-day against sunrise, and evaluating exactly at sunrise
            # lands on a floating-point boundary that can flip to the previous day
            # (notably at western longitudes). Noon is safely within the vedic day.
            weekday = drik.vaara(jd_noon, place_obj)

            def _period(option):
                s, e = drik.trikalam(jd_noon, place_obj, option)
                return {"start": s[:5] if isinstance(s, str) else s,
                        "end": e[:5] if isinstance(e, str) else e}

            durmuhurtam = drik.durmuhurtam(jd_noon, place_obj)  # flat [s,e,(s,e)]
            durm = [{"start": durmuhurtam[i][:5], "end": durmuhurtam[i + 1][:5]}
                    for i in range(0, len(durmuhurtam) - 1, 2)]
            abh = drik.abhijit_muhurta(jd_noon, place_obj)

            return {
                "status": "success",
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "place": place,
                "tithi": {"index": ti[0], "name": tithi_name, "paksha": paksha,
                          "ends": _fmt_hours(ti[2])},
                "nakshatra": {"index": nak[0], "name": NAKSHATRA_NAMES[nak[0] - 1],
                              "pada": nak[1], "ends": _fmt_hours(nak[3])},
                "yoga": {"index": yog[0], "name": YOGA_NAMES[yog[0] - 1],
                         "ends": _fmt_hours(yog[2])},
                "karana": {"index": kar[0], "name": _karana_name(kar[0]),
                           "ends": _fmt_hours(kar[2])},
                "vaara": {"index": weekday, "name": WEEKDAY_NAMES[weekday]},
                "sunrise": sr[1][:5] if isinstance(sr[1], str) else _fmt_hours(sr[0]),
                "sunset": ss[1][:5] if isinstance(ss[1], str) else _fmt_hours(ss[0]),
                "rahu_kalam": _period("raahu kaalam"),
                "yamaganda": _period("yamagandam"),
                "gulika": _period("gulikai"),
                "durmuhurtam": durm,
                "abhijit": {"start": abh[0][:5], "end": abh[1][:5]} if abh else None,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_planetary_hours(date: Optional[str] = None, place: str = "",
                            lat: Optional[float] = None, lon: Optional[float] = None,
                            tz: Optional[float] = None) -> Dict:
        """Planetary hours (hora) for a date + place: the 24 horas of the day
        (12 daytime, from sunrise to sunset, + 12 nighttime, sunset to next
        sunrise), each ruled by one of the seven graha. The day's first hora is
        ruled by the weekday lord; the sequence follows the Chaldean order. Each
        hora is tagged benefic/malefic and, for the current day, the running hora
        is flagged. `date` defaults to today at `place`."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            if date:
                year, month, day = map(int, date.split("-"))
            else:
                local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
                year, month, day = local_now.year, local_now.month, local_now.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            jd_noon = swe.julday(year, month, day, 12)

            # shubha_hora returns 24 tuples (planet_index, start 'HH:MM:SS', end),
            # first 12 daytime then 12 nighttime.
            horas = drik.shubha_hora(jd_noon, place_obj)

            # Is "now" within this day (in the place's timezone)? If so, mark the
            # running hora by comparing the local wall-clock against each window.
            now_local = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            is_today = (now_local.year, now_local.month, now_local.day) == (year, month, day)
            now_minutes = now_local.hour * 60 + now_local.minute if is_today else None

            def _hm(s):
                # 'HH:MM:SS' -> 'HH:MM'
                return s[:5] if isinstance(s, str) else str(s)

            def _to_min(s):
                try:
                    parts = str(s).split(":")
                    return int(parts[0]) * 60 + int(parts[1])
                except Exception:
                    return None

            out = []
            for i, (pidx, start, end) in enumerate(horas):
                name = HORA_PLANETS[pidx] if 0 <= pidx < len(HORA_PLANETS) else str(pidx)
                sm, em = _to_min(start), _to_min(end)
                # Night horas after midnight wrap past 24h; the string is still the
                # clock time, so only flag "current" for the daytime block reliably.
                current = False
                if now_minutes is not None and sm is not None and em is not None and i < 12:
                    current = sm <= now_minutes < em
                out.append({
                    "index": i + 1,
                    "planet": name,
                    "start": _hm(start),
                    "end": _hm(end),
                    "period": "day" if i < 12 else "night",
                    "benefic": name in HORA_BENEFICS,
                    "current": current,
                })

            sr = drik.sunrise(jd_noon, place_obj)
            ss = drik.sunset(jd_noon, place_obj)
            return {
                "status": "success",
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "place": place,
                "sunrise": sr[1][:5] if isinstance(sr[1], str) else _fmt_hours(sr[0]),
                "sunset": ss[1][:5] if isinstance(ss[1], str) else _fmt_hours(ss[0]),
                "horas": out,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_eclipses(place: str = "", lat: Optional[float] = None,
                     lon: Optional[float] = None, tz: Optional[float] = None,
                     from_date: Optional[str] = None, count: int = 3) -> Dict:
        """Upcoming solar and lunar eclipses from a date. Returns the next
        `count` of each (global visibility), with the eclipse type and the key
        instants (begin / maximum / end) in the place's local time. Solar and
        lunar are searched independently, each stepping past the previous
        maximum. `from_date` defaults to today at `place`."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from jhora.panchanga.eclipse import (
                next_solar_eclipse, next_lunar_eclipse, EclipseLocation,
            )

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            if from_date:
                year, month, day = map(int, from_date.split("-"))
            else:
                local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
                year, month, day = local_now.year, local_now.month, local_now.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            count = max(1, min(int(count or 3), 6))

            def _fmt_instant(t):
                # t = (y, m, d, float_hours) local -> {date, time}
                if not t:
                    return None
                y, mo, d, fh = t[0], t[1], t[2], t[3]
                return {"date": f"{y:04d}-{mo:02d}-{d:02d}", "time": _fmt_hours(fh)}

            def _to_jd(t):
                return swe.julday(t[0], t[1], t[2], t[3]) if t else None

            def _midpoint(a, b):
                # Average two local instants -> a normalized (y,m,d,fh) tuple.
                ja, jb = _to_jd(a), _to_jd(b)
                if ja is None or jb is None:
                    return a or b
                return utils.jd_to_gregorian((ja + jb) / 2.0)

            solar = []
            jd = swe.julday(year, month, day, 0)
            for _ in range(count):
                r = next_solar_eclipse(jd, place_obj,
                                       eclipse_location_type=EclipseLocation.GLOBAL)
                if not r:
                    break
                etype, (begin, maximum, end) = r
                solar.append({
                    "type": etype,
                    "date": (_fmt_instant(maximum) or {}).get("date"),
                    "begin": _fmt_instant(begin),
                    "maximum": _fmt_instant(maximum),
                    "end": _fmt_instant(end),
                })
                jd = swe.julday(maximum[0], maximum[1], maximum[2], 0) + 1

            # Lunar: the engine returns [penumbral_begin, partial_begin, max,
            # partial_end, penumbral_end]; its `max` instant omits the tz offset
            # the others carry, so we derive the maximum as the midpoint of the
            # (correctly localized) partial phases, falling back to penumbral.
            lunar = []
            jd = swe.julday(year, month, day, 0)
            for _ in range(count):
                r = next_lunar_eclipse(jd, place_obj,
                                       eclipse_location_type=EclipseLocation.GLOBAL)
                if not r:
                    break
                etype, (pen_begin, par_begin, _bad_max, par_end, pen_end) = r
                begin = par_begin or pen_begin
                end = par_end or pen_end
                maximum = _midpoint(par_begin or pen_begin, par_end or pen_end)
                lunar.append({
                    "type": etype,
                    "date": (_fmt_instant(maximum) or {}).get("date"),
                    "begin": _fmt_instant(pen_begin),
                    "partial_begin": _fmt_instant(par_begin),
                    "maximum": _fmt_instant(maximum),
                    "partial_end": _fmt_instant(par_end),
                    "end": _fmt_instant(pen_end),
                })
                jd = swe.julday(begin[0], begin[1], begin[2], 0) + 1
            return {
                "status": "success",
                "place": place,
                "from_date": f"{year:04d}-{month:02d}-{day:02d}",
                "solar": solar,
                "lunar": lunar,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_festival_dates(place: str = "", lat: Optional[float] = None,
                           lon: Optional[float] = None, tz: Optional[float] = None,
                           start: Optional[str] = None, end: Optional[str] = None,
                           types: Optional[List[str]] = None) -> Dict:
        """Tithi-driven festival / vratha dates in a range. For each requested
        type (Ekadashi, Pradosham, Purnima, Amavasya, Sankashti, …) finds every
        occurrence between `start` and `end` via the tithi finder, returning the
        date, the tithi window, and the vratha's meaning. Defaults to the next
        ~45 days from today at `place`."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from jhora.panchanga import vratha
            from jhora.panchanga.drik import Date

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707

            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            if start:
                sy, sm, sd = map(int, start.split("-"))
            else:
                sy, sm, sd = local_now.year, local_now.month, local_now.day
            if end:
                ey, em, ed = map(int, end.split("-"))
            else:
                _end = local_now + timedelta(days=45)
                ey, em, ed = _end.year, _end.month, _end.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            start_date, end_date = Date(sy, sm, sd), Date(ey, em, ed)

            if not types:
                types = list(DEFAULT_FESTIVAL_TYPES)

            events = []
            for key in types:
                spec = FESTIVAL_TYPES.get(key)
                if not spec:
                    continue
                rows = vratha.tithi_dates(place_obj, start_date, end_date,
                                          tithi_index_list=list(spec["tithis"]))
                for row in rows:
                    (yy, mm, dd), s_fh, e_fh, tag = row[0], row[1], row[2], row[3]
                    events.append({
                        "type": key,
                        "name": spec["name"],
                        "meaning": spec["meaning"],
                        "date": f"{yy:04d}-{mm:02d}-{dd:02d}",
                        "starts": _fmt_hours(s_fh),
                        "ends": _fmt_hours(e_fh),
                        "detail": tag,
                    })
            events.sort(key=lambda e: (e["date"], e["name"]))
            return {
                "status": "success",
                "place": place,
                "start": f"{sy:04d}-{sm:02d}-{sd:02d}",
                "end": f"{ey:04d}-{em:02d}-{ed:02d}",
                "events": events,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_conjunctions(place: str = "", lat: Optional[float] = None,
                         lon: Optional[float] = None, tz: Optional[float] = None,
                         start: Optional[str] = None, end: Optional[str] = None,
                         max_sep: float = 3.0) -> Dict:
        """Planetary conjunctions (Graha Yuddha / 'planetary war') in a range.

        Scans each day and records when two of the five tara grahas (Mars,
        Mercury, Jupiter, Venus, Saturn — Sun/Moon/nodes never engage in Graha
        Yuddha) come within `max_sep` degrees of each other in ecliptic
        longitude. Consecutive in-range days are collapsed into one event with
        the closest approach (minimum separation) and the date it occurs; a
        separation under 1° is flagged as an actual Graha Yuddha (war).
        Defaults to the next ~90 days from today at `place`."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from itertools import combinations

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707

            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            if start:
                sy, sm, sd = map(int, start.split("-"))
            else:
                sy, sm, sd = local_now.year, local_now.month, local_now.day
            if end:
                ey, em, ed = map(int, end.split("-"))
            else:
                _end = local_now + timedelta(days=90)
                ey, em, ed = _end.year, _end.month, _end.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            max_sep = max(0.1, min(float(max_sep or 3.0), 15.0))

            start_jd = swe.julday(sy, sm, sd, 0.0)
            end_jd = swe.julday(ey, em, ed, 0.0)
            # Cap the scan so a runaway range can't compute a chart per day forever.
            n_days = int(min(max(end_jd - start_jd, 0), 400)) + 1

            def _lng(pp, idx):
                # pp[idx+1][1] = [sign(0-11), degrees]; ecliptic longitude 0-360.
                return pp[idx + 1][1][0] * 30 + pp[idx + 1][1][1]

            def _sep(a, b):
                d = abs(a - b) % 360
                return 360 - d if d > 180 else d

            # Mars..Saturn planet indices (Sun=0 .. Saturn=6 in HORA_PLANETS).
            tara = list(range(2, 7))
            active: Dict = {}
            finished = []

            for i in range(n_days):
                jd = start_jd + i
                yy, mm, dd, _ = swe.revjul(jd)
                pp = charts.rasi_chart(jd, place_obj)
                lngs = {p: _lng(pp, p) for p in tara}
                seen = set()
                for p1, p2 in combinations(tara, 2):
                    s = _sep(lngs[p1], lngs[p2])
                    key = (p1, p2)
                    if s < max_sep:
                        seen.add(key)
                        date_t = (int(yy), int(mm), int(dd))
                        if key not in active:
                            active[key] = {"from": date_t, "min": s, "min_date": date_t}
                        elif s < active[key]["min"]:
                            active[key]["min"] = s
                            active[key]["min_date"] = date_t
                        active[key]["to"] = date_t
                # close any pair that dropped out of range today
                for key in [k for k in active if k not in seen]:
                    finished.append((key, active.pop(key)))
            for key, ev in active.items():
                finished.append((key, ev))

            def _d(t):
                return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"

            events = []
            for (p1, p2), ev in finished:
                events.append({
                    "planet1": HORA_PLANETS[p1],
                    "planet2": HORA_PLANETS[p2],
                    "from": _d(ev["from"]),
                    "to": _d(ev["to"]),
                    "closest_date": _d(ev["min_date"]),
                    "separation": round(ev["min"], 2),
                    "war": ev["min"] < 1.0,
                })
            events.sort(key=lambda e: (e["closest_date"], e["planet1"]))
            return {
                "status": "success",
                "place": place,
                "start": f"{sy:04d}-{sm:02d}-{sd:02d}",
                "end": f"{ey:04d}-{em:02d}-{ed:02d}",
                "max_separation": max_sep,
                "events": events,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_transits(dob: str, tob: str, place: str,
                     lat: Optional[float] = None, lon: Optional[float] = None,
                     tz: Optional[float] = None, current_date: Optional[str] = None,
                     current_time: Optional[str] = None, current_tz: Optional[float] = None,
                     ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Current planetary transits (Gochara) over the natal chart.

        Computes where each graha sits *today* (or on `current_date`), the house it
        occupies counted from the natal Lagna and from the natal Moon (the classic
        gochara reference), whether it is retrograde, plus the next sign-ingress
        dates for the slow movers (Jupiter/Saturn/Rahu/Ketu). Transit positions are
        rendered against the natal Lagna so the frontend can draw them on the same
        North/South Kundali component."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        try:
            _set_ayanamsa(ayanamsa)
            from datetime import datetime

            year, month, day = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz or 5.5

            place_obj = drik.Place(place, lat, lon, tz_offset)

            # ── Natal reference (Lagna + Moon) ──────────────────────────────
            natal_jd = swe.julday(year, month, day, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)
            natal_lagna_rasi = natal[0][1][0]
            natal_lagna_deg = natal[0][1][1]
            natal_moon_rasi, natal_moon_deg = natal[2][1]  # row 2 = Moon (planet 1)

            # ── Transit moment ──────────────────────────────────────────────
            # Anchor to the *viewer's* current location: their wall-clock time and
            # timezone, not the birthplace's. This keeps fast movers (especially the
            # Moon, ~0.5°/hr) at the present instant rather than at birthplace noon.
            if current_date:
                ty, tm, td = map(int, current_date.split("-"))
            else:
                now = datetime.now()
                ty, tm, td = now.year, now.month, now.day

            if current_time:
                tparts = current_time.split(":")
                t_hour = int(tparts[0])
                t_min = int(tparts[1]) if len(tparts) > 1 else 0
            else:
                t_hour, t_min = 12, 0  # local noon fallback (stable daily snapshot)

            # PyJHora's drik functions take a *local* JD and subtract place.timezone
            # to reach UT, so the transit place must carry the viewer's current tz for
            # the local→UT conversion to land on the right instant.
            transit_tz = current_tz if current_tz is not None else tz_offset
            transit_place = drik.Place(place, lat, lon, transit_tz)
            transit_jd = swe.julday(ty, tm, td, t_hour + t_min / 60.0)

            transit = charts.rasi_chart(transit_jd, transit_place)
            retro_ids = set(drik.planets_in_retrograde(transit_jd, transit_place))

            nak_span = 360.0 / 27.0
            pada_span = nak_span / 4.0

            def house_from(ref_rasi, rasi):
                return ((rasi - ref_rasi) % 12) + 1

            planets = {}
            for planet_index, (rasi, degrees) in transit[1:]:  # skip ascendant
                name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
                abs_long = rasi * 30.0 + degrees
                nak_idx = int(abs_long / nak_span)
                pada = int((abs_long % nak_span) / pada_span) + 1
                planets[name] = {
                    "house": rasi + 1,  # 1-based sign for the Kundali component
                    "rasi": rasi,
                    "degrees": round(degrees, 2),
                    "sign_name": ZODIAC_NAMES[rasi],
                    "nakshatra": NAKSHATRA_NAMES[nak_idx],
                    "nakshatra_pada": pada,
                    "retrograde": planet_index in retro_ids,
                    "house_from_lagna": house_from(natal_lagna_rasi, rasi),
                    "house_from_moon": house_from(natal_moon_rasi, rasi),
                }

            # ── Upcoming sign ingresses for the slow movers ─────────────────
            # Only Jupiter & Saturn: these are the headline gochara events
            # (Jupiter transit, Saturn Sade Sati). The lunar nodes are skipped —
            # PyJHora's retrograde node-ingress search returns a full ~18yr nodal
            # cycle rather than the next boundary, so its dates aren't trustworthy.
            upcoming = []
            for pidx in (4, 6):  # Jupiter, Saturn
                try:
                    cur_rasi = transit[pidx + 1][1][0]
                    entry_jd, entry_long = drik.next_planet_entry_date(
                        pidx, transit_jd, transit_place, increment_days=1, precision=0.1)
                    ey, em, ed, _ = utils.jd_to_gregorian(entry_jd)
                    to_rasi = int(entry_long // 30) % 12
                    upcoming.append({
                        "planet": PLANET_NAMES[pidx],
                        "from_sign": ZODIAC_NAMES[cur_rasi],
                        "to_sign": ZODIAC_NAMES[to_rasi],
                        "date": f"{ey:04d}-{em:02d}-{ed:02d}",
                    })
                except Exception as ie:
                    print(f"Transit ingress error for planet {pidx}: {ie}")

            upcoming.sort(key=lambda x: x["date"])

            return {
                "status": "success",
                "transit_date": f"{ty:04d}-{tm:02d}-{td:02d}",
                "transit_time": f"{t_hour:02d}:{t_min:02d}",
                "natal": {
                    "lagna": {
                        "house": natal_lagna_rasi + 1,
                        "degrees": round(natal_lagna_deg, 2),
                        "sign_name": ZODIAC_NAMES[natal_lagna_rasi],
                    },
                    "moon": {
                        "house": natal_moon_rasi + 1,
                        "degrees": round(natal_moon_deg, 2),
                        "sign_name": ZODIAC_NAMES[natal_moon_rasi],
                    },
                },
                # Natal lagna drives the Kundali houses; planets are the transits.
                "lagna": {
                    "house": natal_lagna_rasi + 1,
                    "degrees": round(natal_lagna_deg, 2),
                    "sign_name": ZODIAC_NAMES[natal_lagna_rasi],
                },
                "planets": planets,
                "upcoming": upcoming,
            }

        except Exception as e:
            print(f"Transit calculation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_sarvatobhadra_chakra(dob: str, tob: str, place: str,
                                 lat: Optional[float] = None, lon: Optional[float] = None,
                                 tz: Optional[float] = None, name_nakshatra: Optional[int] = None,
                                 current_date: Optional[str] = None, current_time: Optional[str] = None,
                                 current_tz: Optional[float] = None,
                                 ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Sarvatobhadra Chakra with the current transits mapped onto it.

        Builds the 9×9 chakra, places each transiting graha on its nakshatra cell
        AND its rasi cell, then reports — against the native's sensitive points
        (birth/janma star, Moon sign, optional name star, birth tithi group and
        birth weekday) — both *occupation* (a graha sitting on the cell) and
        *facing (saamne) vedha* (a graha on the cell mirrored across the chakra's
        centre). The structured `findings` feed the layman AI reading."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        try:
            _set_ayanamsa(ayanamsa)
            from datetime import datetime

            year, month, day = map(int, dob.split("-"))
            tparts = tob.split(":")
            hour = int(tparts[0])
            minute = int(tparts[1]) if len(tparts) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place or "", lat, lon, tz_offset)

            nak_span = 360.0 / 27.0

            def mirror(cell):
                return (8 - cell[0], 8 - cell[1])

            def cell_meta(cell):
                return _SBC_GRID[cell[0]][cell[1]] if cell else None

            # ── Natal anchors ────────────────────────────────────────────────
            natal_jd = swe.julday(year, month, day, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)
            moon_rasi, moon_deg = natal[2][1]  # row 2 = Moon
            moon_abs = moon_rasi * 30.0 + moon_deg
            janma_nak = int(moon_abs / nak_span) + 1  # 1..27 (27-star system)
            # Map the 27-star janma nakshatra onto the 28-cell ring (Abhijit is
            # cell 28; the 27-star indices ≥22 shift up by one on the ring).
            janma_cell_key = janma_nak if janma_nak <= 21 else janma_nak + 1
            birth_tithi = drik.tithi(natal_jd, place_obj)[0]
            birth_weekday = drik.vaara(natal_jd, place_obj)  # 0=Sun..6=Sat
            birth_group = _tithi_group(birth_tithi)

            anchors = {}
            anchors["janma_nakshatra"] = {
                "label": "Birth star (Janma Nakshatra)",
                "name": _SBC_NAK28[janma_cell_key - 1],
                "cell": list(_SBC_NAK_CELL[janma_cell_key]),
            }
            anchors["moon_sign"] = {
                "label": "Moon sign (Janma Rasi)",
                "name": ZODIAC_NAMES[moon_rasi],
                "cell": list(_SBC_RASI_CELL[moon_rasi + 1]),
            }
            anchors["birth_tithi"] = {
                "label": "Birth tithi group",
                "name": birth_group,
                "cell": list(_SBC_GROUP_CELL[birth_group]),
            }
            anchors["birth_weekday"] = {
                "label": "Birth weekday",
                "name": WEEKDAY_NAMES[birth_weekday],
                "cell": list(_SBC_WEEKDAY_CELL[WEEKDAY_NAMES[birth_weekday]]),
            }
            if name_nakshatra and 1 <= int(name_nakshatra) <= 27:
                nn = int(name_nakshatra)
                nn_key = nn if nn <= 21 else nn + 1
                anchors["name_nakshatra"] = {
                    "label": "Name star (Naama Nakshatra)",
                    "name": _SBC_NAK28[nn_key - 1],
                    "cell": list(_SBC_NAK_CELL[nn_key]),
                }

            # ── Transit moment (viewer's wall clock + tz; see get_transits) ──
            if current_date:
                ty, tm, td = map(int, current_date.split("-"))
            else:
                now = datetime.now()
                ty, tm, td = now.year, now.month, now.day
            if current_time:
                cparts = current_time.split(":")
                t_hour, t_min = int(cparts[0]), (int(cparts[1]) if len(cparts) > 1 else 0)
            else:
                t_hour, t_min = 12, 0
            transit_tz = current_tz if current_tz is not None else tz_offset
            transit_place = drik.Place(place or "", lat, lon, transit_tz)
            transit_jd = swe.julday(ty, tm, td, t_hour + t_min / 60.0)

            transit = charts.rasi_chart(transit_jd, transit_place)
            retro_ids = set(drik.planets_in_retrograde(transit_jd, transit_place))

            # Place each graha on its nakshatra cell + rasi cell.
            placements = {}  # (r,c) -> list of planet names
            planets = []
            for pidx, (rasi, degrees) in transit[1:]:  # skip ascendant
                name = PLANET_NAMES.get(pidx, f"Planet_{pidx}")
                abs_long = rasi * 30.0 + degrees
                nak27 = int(abs_long / nak_span) + 1
                nak_key = nak27 if nak27 <= 21 else nak27 + 1
                nak_c = _SBC_NAK_CELL[nak_key]
                rasi_c = _SBC_RASI_CELL[rasi + 1]
                for c in (nak_c, rasi_c):
                    placements.setdefault(c, []).append(name)
                planets.append({
                    "name": name,
                    "nature": _sbc_nature(name),
                    "retrograde": pidx in retro_ids,
                    "sign_name": ZODIAC_NAMES[rasi],
                    "degrees": round(degrees, 2),
                    "nakshatra": _SBC_NAK28[nak_key - 1],
                    "nakshatra_cell": list(nak_c),
                    "rasi_cell": list(rasi_c),
                })

            # ── Findings: occupation + facing vedha on each anchor ───────────
            findings = []
            for key, a in anchors.items():
                cell = tuple(a["cell"])
                mcell = mirror(cell)
                for planet in placements.get(cell, []):
                    nature = _sbc_nature(planet)
                    findings.append({
                        "anchor": key, "anchor_label": a["label"], "anchor_name": a["name"],
                        "kind": "occupation", "planet": planet, "planet_nature": nature,
                        "tone": "supportive" if nature == "benefic" else "stressful",
                    })
                for planet in placements.get(mcell, []):
                    nature = _sbc_nature(planet)
                    findings.append({
                        "anchor": key, "anchor_label": a["label"], "anchor_name": a["name"],
                        "kind": "vedha", "planet": planet, "planet_nature": nature,
                        "facing": cell_meta(mcell).get("label") if cell_meta(mcell) else None,
                        "tone": "supportive" if nature == "benefic" else "stressful",
                    })

            # ── Transit-day panchanga, with coincidence flags vs the native ──
            t_tithi = drik.tithi(transit_jd, transit_place)[0]
            t_weekday = drik.vaara(transit_jd, transit_place)
            t_group = _tithi_group(t_tithi)
            transit_panchanga = {
                "tithi_group": t_group,
                "same_tithi_group": t_group == birth_group,
                "weekday": WEEKDAY_NAMES[t_weekday],
                "same_weekday": t_weekday == birth_weekday,
            }

            return {
                "status": "success",
                "transit_date": f"{ty:04d}-{tm:02d}-{td:02d}",
                "transit_time": f"{t_hour:02d}:{t_min:02d}",
                "grid": _SBC_GRID,
                "anchors": anchors,
                "planets": planets,
                "placements": {f"{r},{c}": v for (r, c), v in placements.items()},
                "findings": findings,
                "transit_panchanga": transit_panchanga,
            }

        except Exception as e:
            print(f"Sarvatobhadra calculation error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_compatibility(male_dob: str, male_tob: str, male_place: str,
                          female_dob: str, female_tob: str, female_place: str,
                          male_lat: Optional[float] = None, male_lon: Optional[float] = None,
                          female_lat: Optional[float] = None, female_lon: Optional[float] = None,
                          male_tz: Optional[float] = None, female_tz: Optional[float] = None,
                          tz: Optional[float] = 5.5) -> Dict:
        """Ashtakoot (Guna Milan) compatibility between two charts.

        Computes each person's Moon nakshatra+pada and runs PyJHora's North-Indian
        Ashtakoota (the classic 36-point system). Returns the eight kootas with
        their *correct* individual maxima plus a verdict, so the frontend can render
        an accurate breakdown."""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        nakshatra_names = [
            "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
            "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
            "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
            "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
            "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
        ]

        def _moon_nakshatra_pada(dob, tob, place, lat, lon, person_tz):
            """1-based Moon nakshatra number (1-27) and pada (1-4)."""
            year, month, day = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            jd = swe.julday(year, month, day, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, person_tz if person_tz is not None else (tz or 5.5))
            pp = charts.rasi_chart(jd, place_obj)
            moon_rasi, moon_long = pp[2][1]  # pp[0]=Asc, pp[1]=Sun, pp[2]=Moon
            absolute_longitude = moon_rasi * 30.0 + moon_long
            nak, pada = drik.nakshatra_pada(absolute_longitude)[:2]
            return nak, pada

        try:
            boy_nak, boy_pada = _moon_nakshatra_pada(
                male_dob, male_tob, male_place, male_lat, male_lon, male_tz)
            girl_nak, girl_pada = _moon_nakshatra_pada(
                female_dob, female_tob, female_place, female_lat, female_lon, female_tz)

            ak = compat_module.Ashtakoota(boy_nak, boy_pada, girl_nak, girl_pada, method="North")
            # compatibility_score() -> [varna, vasiya, gana, dina(tara), yoni,
            #   raasi_adhipathi(graha maitri), raasi(bhakoot), naadi, total_score, ...]
            scores = ak.compatibility_score()
            varna, vasiya, gana, tara, yoni, maitri, bhakoot, naadi, total = scores[:9]

            kootas = [
                {"key": "varna", "name": "Varna", "score": varna, "max": 1,
                 "description": "Spiritual compatibility and ego balance"},
                {"key": "vashya", "name": "Vashya", "score": vasiya, "max": 2,
                 "description": "Mutual attraction and influence"},
                {"key": "tara", "name": "Tara (Dina)", "score": tara, "max": 3,
                 "description": "Health, longevity and destiny"},
                {"key": "yoni", "name": "Yoni", "score": yoni, "max": 4,
                 "description": "Physical and intimate compatibility"},
                {"key": "maitri", "name": "Graha Maitri", "score": maitri, "max": 5,
                 "description": "Mental affinity and friendship"},
                {"key": "gana", "name": "Gana", "score": gana, "max": 6,
                 "description": "Temperament and nature"},
                {"key": "bhakoot", "name": "Bhakoot (Rasi)", "score": bhakoot, "max": 7,
                 "description": "Love, family welfare and prosperity"},
                {"key": "nadi", "name": "Nadi", "score": naadi, "max": 8,
                 "description": "Health and progeny (genetic harmony)"},
            ]

            if total >= 28:
                status = "Excellent Match"
            elif total >= 24:
                status = "Very Good Match"
            elif total >= 18:
                status = "Good Match"
            elif total >= 14:
                status = "Average — Needs Consideration"
            else:
                status = "Not Recommended"

            return {
                "total_score": round(float(total), 1),
                "max_score": 36,
                "status": status,
                "kootas": kootas,
                "boy": {"nakshatra": nakshatra_names[boy_nak - 1], "pada": boy_pada},
                "girl": {"nakshatra": nakshatra_names[girl_nak - 1], "pada": girl_pada},
            }
        except Exception as e:
            print(f"Compatibility calculation error: {e}")
            return {"error": str(e)}

    @staticmethod
    def get_pancha_pakshi(dob: str, tob: str, place: str,
                          lat: Optional[float] = None, lon: Optional[float] = None,
                          tz: Optional[float] = None,
                          date: Optional[str] = None) -> Dict:
        """Pancha Pakshi Sastra — the bird-cycle daily-timing system.

        Assigns the native a *birth bird* (from the birth nakshatra + paksha),
        then rates the chosen day's activity windows by that bird's state
        (ruling / eating / walking / sleeping / dying) across ten main periods
        (5 daytime from sunrise, 5 nighttime), each split into 5 sub-periods.
        The birth bird is fixed from birth; the timeline is for `date` (defaults
        to today at `place`). This system is independent of ayanamsa.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from jhora.panchanga import pancha_paksha as pp

            # ── Birth bird (fixed from birth star + paksha) ────────────────
            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            b_hour = int(tp[0]); b_min = int(tp[1]) if len(tp) > 1 else 0
            b_sec = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place or "", lat, lon, tz_offset)

            jd_birth = utils.julian_day_number((y, m, d), (b_hour, b_min, b_sec))
            birth_star = pp._get_birth_nakshathra(jd_birth, place_obj)
            birth_paksha = pp._get_paksha(jd_birth, place_obj)
            bird_index = pp._get_birth_bird_from_nakshathra(birth_star, birth_paksha)
            bird_name = pp.pancha_pakshi_birds[bird_index - 1].capitalize()

            # ── Query day ──────────────────────────────────────────────────
            if date:
                qy, qm, qd = map(int, date.split("-"))
            else:
                local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
                qy, qm, qd = local_now.year, local_now.month, local_now.day

            # Anchor the query at local sunrise (the day boundary for this system).
            jd_noon = swe.julday(qy, qm, qd, 12)
            sunrise_jd = drik.sunrise(jd_noon, place_obj)[2]
            weekday_index = drik.vaara(jd_noon, place_obj) + 1
            q_paksha = pp._get_paksha(jd_noon, place_obj)

            day_len = drik.day_length(jd_noon, place_obj)      # hours
            night_len = drik.night_length(jd_noon, place_obj)  # hours
            day_inc = day_len / 5.0
            night_inc = night_len / 5.0

            rows = pp.get_matching_pancha_pakshi_data_from_db(
                bird_index, weekday_index, q_paksha)
            if not rows or len(rows) < 50:
                return {"error": "No Pancha Pakshi data for this day",
                        "status": "failed"}

            # Row columns: wdi,pi,dni,mbi,mai,sbi,sai,df,reli,pf,efi,rtng,ppi,bpi
            ACT = pp.pancha_pakshi_activities   # ruling,eating,walking,sleeping,dying
            REL = pp.pp_relations               # enemy,same,friend
            EFF = pp.pp_effect                  # very_bad..very_good
            # Activity ordering as a coarse strength (ruling best .. dying worst).
            ACT_RANK = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1}

            def _hhmm(jd_val):
                yy, mm, dd, fh = utils.jd_to_gregorian(jd_val)
                hh = int(fh) % 24
                mi = int(round((fh - int(fh)) * 60))
                if mi == 60:
                    hh = (hh + 1) % 24; mi = 0
                return f"{hh:02d}:{mi:02d}"

            segments = []
            best = []
            time_from_jd = sunrise_jd
            now_local = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            is_today = (now_local.year, now_local.month, now_local.day) == (qy, qm, qd)
            now_jd = None
            if is_today:
                # The timeline JDs are built in the same "local-clock-as-UT" frame
                # as jd_noon (swe.julday of the local wall clock), so anchor "now"
                # the same way for the running-window comparison.
                now_jd = swe.julday(qy, qm, qd,
                                    now_local.hour + now_local.minute / 60.0)

            for parent in range(0, len(rows), 5):
                base = rows[parent]
                dni = int(base[2]); mbi = int(base[3]); mai = int(base[4])
                time_inc = (day_inc if dni == 0 else night_inc) / 24.0  # in days
                seg_start_jd = time_from_jd
                seg_end_jd = time_from_jd + time_inc
                subs = []
                sub_from_jd = seg_start_jd
                for irow in range(parent, parent + 5):
                    r = rows[irow]
                    sbi = int(r[5]); sai = int(r[6]); df = float(r[7])
                    reli = int(r[8]); efi = int(r[10]); rtng = r[11]
                    sub_end_jd = sub_from_jd + time_inc * df
                    running = bool(now_jd and sub_from_jd <= now_jd < sub_end_jd)
                    sub = {
                        "start": _hhmm(sub_from_jd),
                        "end": _hhmm(sub_end_jd),
                        "sub_bird": pp.pancha_pakshi_birds[sbi].capitalize(),
                        "sub_activity": ACT[sai].capitalize(),
                        "relation": REL[reli].capitalize(),
                        "effect": EFF[efi].replace("_", " ").title(),
                        "effect_score": efi,        # 0 very-bad .. 4 very-good
                        "rating": rtng,
                        "running": running,
                    }
                    subs.append(sub)
                    best.append({
                        "start": sub["start"], "end": sub["end"],
                        "phase": "day" if dni == 0 else "night",
                        "main_activity": ACT[mai].capitalize(),
                        "sub_activity": sub["sub_activity"],
                        "effect": sub["effect"], "effect_score": efi,
                        "rating": rtng, "running": running,
                    })
                    sub_from_jd = sub_end_jd
                segments.append({
                    "phase": "day" if dni == 0 else "night",
                    "start": _hhmm(seg_start_jd),
                    "end": _hhmm(seg_end_jd),
                    "main_bird": pp.pancha_pakshi_birds[mbi].capitalize(),
                    "main_activity": ACT[mai].capitalize(),
                    "activity_rank": ACT_RANK.get(mai, 3),
                    "sub": subs,
                })
                time_from_jd = sub_from_jd

            # Best & worst windows by effect (then rating), for the summary.
            ranked = sorted(best, key=lambda s: (s["effect_score"],
                                                 float(s["rating"] or 0)), reverse=True)
            best_times = ranked[:5]
            avoid_times = sorted(best, key=lambda s: (s["effect_score"],
                                                      float(s["rating"] or 0)))[:5]

            return {
                "status": "success",
                "date": f"{qy:04d}-{qm:02d}-{qd:02d}",
                "place": place,
                "birth_bird": {
                    "name": bird_name,
                    "index": bird_index,
                    "star": birth_star,
                    "star_name": NAKSHATRA_NAMES[birth_star - 1],
                    "paksha": "Shukla" if birth_paksha == 1 else "Krishna",
                },
                "weekday": WEEKDAY_NAMES[weekday_index - 1],
                "paksha": "Shukla" if q_paksha == 1 else "Krishna",
                "sunrise": _hhmm(sunrise_jd),
                "sunset": _hhmm(sunrise_jd + day_len / 24.0),
                "segments": segments,
                "best_times": best_times,
                "avoid_times": avoid_times,
            }
        except Exception as e:
            print(f"Pancha Pakshi error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_raja_yogas(dob: str, tob: str, place: str,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None,
                       ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Dedicated Raja Yoga analysis for the Rasi (D1) chart.

        Surfaces (a) the fundamental Kendra–Trikona raja yogas — a quadrant lord
        associated with a trine lord — and (b) the named special types
        (Dharma-Karmadhipati, Vipareeta with sub-type, Neecha-Bhanga) with their
        classical descriptions/benefits. A light dignity check labels each pair's
        strength. Birth details + ayanamsa are server-injected; ayanamsa reset.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from jhora.horoscope.chart import raja_yoga as ry

            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(y, m, d, hour + minute / 60.0)

            pp = charts.rasi_chart(jd, place_obj)
            p_to_h = utils.get_planet_house_dictionary_from_planet_positions(pp)

            def _dignity(pidx, sign):
                """Coarse strength from the planet's house-strength in its sign."""
                try:
                    s = const.house_strengths_of_planets[pidx][sign]
                except Exception:
                    return "neutral"
                if s >= const._EXALTED_UCCHAM:
                    return "strong"
                if s <= const._DEBILITATED_NEECHAM:
                    return "weak"
                if s >= const._FRIEND:
                    return "good"
                return "neutral"

            yogas = []

            # (a) Kendra–Trikona raja yoga pairs (association of quadrant &
            #     trine lords). Strength is a blend of both planets' dignity.
            pairs = ry.get_raja_yoga_pairs_from_planet_positions(pp)
            for p1, p2 in pairs:
                d1 = _dignity(p1, p_to_h.get(p1, 0))
                d2 = _dignity(p2, p_to_h.get(p2, 0))
                order = {"strong": 3, "good": 2, "neutral": 1, "weak": 0}
                strength = min([d1, d2], key=lambda x: order[x])
                yogas.append({
                    "name": "Kendra-Trikona Raja Yoga",
                    "type": "kendra_trikona",
                    "planets": [PLANET_NAMES[p1], PLANET_NAMES[p2]],
                    "description": (f"Association of a quadrant (kendra) lord and a "
                                    f"trine (trikona) lord — {PLANET_NAMES[p1]} and "
                                    f"{PLANET_NAMES[p2]} — the core raja yoga that "
                                    f"confers status, authority and success."),
                    "benefits": "Rise in position, recognition and prosperity.",
                    "strength": strength,
                })

            # (b) Named special raja yogas (from the engine's msg resources).
            try:
                details, _cnt, _tot = ry.get_raja_yoga_details(
                    jd, place_obj, divisional_chart_factor=1, language="en")
                for key, val in details.items():
                    # val = [pairs_label, name, description, benefits]
                    label = val[0] if len(val) > 3 else ""
                    name = val[1] if len(val) > 3 else val[0]
                    desc = val[2] if len(val) > 3 else (val[1] if len(val) > 1 else "")
                    benefits = val[3] if len(val) > 3 else (val[2] if len(val) > 2 else "")
                    yogas.append({
                        "name": name,
                        "type": key,
                        "planets": [],
                        "pairs_label": label,
                        "description": desc,
                        "benefits": benefits,
                        "strength": "special",
                    })
            except Exception as inner:
                print(f"Raja yoga named-details skipped: {inner}")

            return {
                "status": "success",
                "count": len(yogas),
                "raja_yogas": yogas,
            }
        except Exception as e:
            print(f"Raja yoga error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_longevity(dob: str, tob: str, place: str,
                      lat: Optional[float] = None, lon: Optional[float] = None,
                      tz: Optional[float] = None,
                      ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Ayu (longevity) *category* from the classical Ayurdaya sign-pair method.

        Returns the ayu band — Alpa (short) / Madhya (medium) / Purna (long) —
        and the three contributing sign-pair verdicts (Lagna-lord vs 8th-lord,
        Lagna vs Moon, Lagna vs Hora-lagna). Deliberately returns a *category*
        and its factors, never a death date or age. Framed as conditional,
        multi-factorial guidance. Ayanamsa server-injected + reset.

        Reimplements the aggregation of the engine's `life_span_range` (which has
        a Py3 `dict.keys()[0]` bug in the all-three-agree branch) while reusing
        its per-pair rule and the same chart inputs.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            import collections

            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(y, m, d, hour + minute / 60.0)

            def _get_aayu(s1, s2):
                """Sign-pair → 0 Alpa / 1 Madhya / 2 Purna (Parashari movable/
                fixed/dual matrix). Mirrors the engine's local helper."""
                mv, fx, dl = const.movable_signs, const.fixed_signs, const.dual_signs
                if s1 in fx and s2 in fx:
                    return 0
                if s1 in mv and s2 in mv:
                    return 2
                if s1 in dl and s2 in dl:
                    return 1
                if (s1 in fx and s2 in mv) or (s1 in mv and s2 in fx):
                    return 1
                if (s1 in dl and s2 in mv) or (s1 in mv and s2 in dl):
                    return 0
                return 2  # fixed+dual

            pp = charts.rasi_chart(jd, place_obj)
            asc_house = pp[0][1][0]
            eighth_house = (asc_house + 7) % 12
            moon_house = pp[2][1][0]
            lagna_lord = house.house_owner_from_planet_positions(pp, asc_house)
            lagna_lord_house = pp[lagna_lord + 1][1][0]
            eighth_lord = house.house_owner_from_planet_positions(pp, eighth_house)
            eighth_lord_house = pp[eighth_lord + 1][1][0]
            hora_lagna = drik.hora_lagna(jd, place_obj)[0]

            group = [
                _get_aayu(lagna_lord_house, eighth_lord_house),
                _get_aayu(asc_house, moon_house),
                _get_aayu(asc_house, hora_lagna),
            ]
            counter = collections.Counter(group)
            if len(counter) == 1:
                category = group[0]
            elif len(counter) == 2:
                category = max(counter, key=counter.get)
            else:
                category = group[-1]
                if moon_house == asc_house or moon_house == (asc_house + 6) % 12:
                    category = group[1]

            AYU = {0: ("Alpa", "Short ayu (conditional)"),
                   1: ("Madhya", "Medium ayu (conditional)"),
                   2: ("Purna", "Long ayu (conditional)")}
            cat_name, cat_desc = AYU[category]

            factor_labels = [
                ("Lagna lord & 8th lord", lagna_lord_house, eighth_lord_house),
                ("Lagna & Moon", asc_house, moon_house),
                ("Lagna & Hora Lagna", asc_house, hora_lagna),
            ]
            factors = []
            for (label, sa, sb), verdict in zip(factor_labels, group):
                factors.append({
                    "pair": label,
                    "signs": [ZODIAC_NAMES[sa], ZODIAC_NAMES[sb]],
                    "verdict": AYU[verdict][0],
                })

            return {
                "status": "success",
                "category": category,          # 0/1/2
                "category_name": cat_name,     # Alpa/Madhya/Purna
                "category_desc": cat_desc,
                "factors": factors,
            }
        except Exception as e:
            print(f"Longevity error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_sudarsana_chakra(dob: str, tob: str, place: str,
                             lat: Optional[float] = None, lon: Optional[float] = None,
                             tz: Optional[float] = None,
                             ayanamsa: str = DEFAULT_AYANAMSA,
                             year_offset: int = 0) -> Dict:
        """Sudarsana Chakra — the three concentric wheels read from the Lagna,
        Moon and Sun as ascendants, for the solar-return year `year_offset` past
        birth (0 = the natal chart itself). Returns one set of planet placements
        plus the three reference lagnas so the frontend can render three Kundalis.
        Ayanamsa server-injected + reset.
        """
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd_dob = swe.julday(y, m, d, hour + minute / 60.0)

            year_offset = max(0, int(year_offset))
            if year_offset == 0:
                jd_year = jd_dob
            else:
                jd_year = drik.next_solar_date(jd_dob, place_obj, years=year_offset)

            pp = charts.divisional_chart(jd_year, place_obj, divisional_chart_factor=1)
            asc_sign = pp[0][1][0]
            moon_sign = pp[2][1][0]
            sun_sign = pp[1][1][0]

            planets = {}
            for pidx, (rasi, degrees) in pp[1:]:
                name = PLANET_NAMES.get(pidx, f"Planet_{pidx}")
                planets[name] = {
                    "rasi": rasi, "house": rasi + 1,
                    "degrees": round(degrees, 2), "sign_name": ZODIAC_NAMES[rasi],
                }

            yy, mm, dd, _fh = utils.jd_to_gregorian(jd_year)
            wheels = [
                {"ref": "Lagna", "lagna_sign": asc_sign,
                 "lagna_house": asc_sign + 1, "sign_name": ZODIAC_NAMES[asc_sign]},
                {"ref": "Chandra (Moon)", "lagna_sign": moon_sign,
                 "lagna_house": moon_sign + 1, "sign_name": ZODIAC_NAMES[moon_sign]},
                {"ref": "Surya (Sun)", "lagna_sign": sun_sign,
                 "lagna_house": sun_sign + 1, "sign_name": ZODIAC_NAMES[sun_sign]},
            ]
            return {
                "status": "success",
                "year_offset": year_offset,
                "year_date": f"{int(yy):04d}-{int(mm):02d}-{int(dd):02d}",
                "planets": planets,
                "wheels": wheels,
            }
        except Exception as e:
            print(f"Sudarsana Chakra error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def search_location(query: str = "", *args, **kwargs):
        """Geocode a free-text place query to [display_name, lat, lon, tz_offset].

        Coordinates come from OpenStreetMap (Nominatim via geopy) and the UTC
        offset from timezonefinder (both already PyJHora dependencies). The tz
        offset reflects the place's *current* rules (incl. DST), which is what
        the form needs when picking a location. Returns None when nothing
        matches so the endpoint can report a friendly "not found"."""
        if not PYJHORA_AVAILABLE:
            return None
        q = (query or "").strip()
        if not q:
            return None
        try:
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent="PyJHoraWeb", timeout=10)
            loc = geolocator.geocode(q, language="en")
            if not loc:
                return None
            lat = round(loc.latitude, 6)
            lon = round(loc.longitude, 6)
            tz = utils.get_place_timezone_offset(lat, lon)
            return [loc.address, lat, lon, round(float(tz), 2)]
        except Exception as e:
            print(f"Location search error: {e}")
            return None

    @staticmethod
    def reverse_geocode(latitude, longitude, *args, **kwargs):
        """Resolve a clicked map point to [display_name, lat, lon, tz_offset].

        Used by the interactive map picker: the lat/long already come from the
        pin, so the timezone is computed offline with timezonefinder (no network
        needed) and Nominatim reverse-geocoding only supplies a friendly place
        name. If the reverse lookup fails we still return coordinates + tz with a
        synthesised label so a clicked point is always usable."""
        if not PYJHORA_AVAILABLE:
            return None
        try:
            lat = round(float(latitude), 6)
            lon = round(float(longitude), 6)
        except (TypeError, ValueError):
            return None
        # Timezone is always derivable from coordinates alone (offline).
        try:
            tz = round(float(utils.get_place_timezone_offset(lat, lon)), 2)
        except Exception as e:
            print(f"Reverse geocode timezone error: {e}")
            tz = 0.0
        place = f"{lat}, {lon}"
        try:
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent="PyJHoraWeb", timeout=10)
            loc = geolocator.reverse((lat, lon), language="en", zoom=10)
            if loc and loc.address:
                place = loc.address
        except Exception as e:
            # Network/rate-limit issues should not break the picker; keep coords.
            print(f"Reverse geocode lookup error: {e}")
        return [place, lat, lon, tz]
