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
    from jhora.horoscope.dhasa.graha import vimsottari, ashtottari, yogini
    from jhora.horoscope.dhasa.raasi import narayana, kalachakra
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

            code, name, significance = SUPPORTED_VARGAS[varga_factor]
            return {
                "status": "success",
                "varga": varga_factor,
                "code": code,
                "name": name,
                "significance": significance,
                "lagna": lagna,
                "planets": planets,
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

            # Arudha padas A1..A12 (bhava arudhas), each a sign index.
            ba = arudhas.bhava_arudhas_from_planet_positions(pp)
            arudha_labels = {0: "AL (Arudha Lagna)", 11: "UL (Upapada)"}
            arudha_padas = [
                {"bhava": i + 1,
                 "label": arudha_labels.get(i, f"A{i + 1}"),
                 "sign_name": ZODIAC_NAMES[int(s) % 12]}
                for i, s in enumerate(ba)
            ]

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
                       ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
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

            _set_ayanamsa(ayanamsa)
            import contextlib
            import io
            from jhora.horoscope.transit import tajaka, saham, tajaka_yoga
            from jhora.horoscope.dhasa.annual import mudda

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

            # ── Annual dasha (Mudda / Varsha Vimsottari), maha level ────────
            annual_dasha = {"system": "Mudda (Varsha Vimsottari)", "periods": []}
            try:
                raw = mudda.mudda_dhasa_bhukthi(jd_dob, place_obj, age,
                                                dhasa_level_index=1)
                from datetime import date as _date
                today = _date.today()

                def _iso(t):
                    return f"{int(t[0]):04d}-{int(t[1]):02d}-{int(t[2]):02d}"

                periods = []
                for lords, start_t, dur_days in raw:
                    lord = lords[0]
                    start_jd = swe.julday(int(start_t[0]), int(start_t[1]),
                                          int(start_t[2]), float(start_t[3]))
                    periods.append({
                        "lord": lord,
                        "lord_name": PLANET_NAMES.get(lord, str(lord)),
                        "start": _iso(start_t),
                        "_start_jd": start_jd,
                        "duration_days": round(float(dur_days), 1),
                    })
                for i, p in enumerate(periods):
                    if i + 1 < len(periods):
                        end_jd = periods[i + 1]["_start_jd"]
                    else:
                        end_jd = p["_start_jd"] + float(p["duration_days"])
                    ey2, em2, ed2, _ = utils.jd_to_gregorian(end_jd)
                    p["end"] = f"{int(ey2):04d}-{int(em2):02d}-{int(ed2):02d}"
                    try:
                        p["current"] = (p["start"] <= today.isoformat() < p["end"])
                    except Exception:
                        p["current"] = False
                    del p["_start_jd"]
                annual_dasha["periods"] = periods
            except Exception as e:
                print(f"Varshaphal annual-dasha error: {e}")

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
