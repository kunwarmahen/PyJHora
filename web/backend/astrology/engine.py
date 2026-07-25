"""Engine bootstrap, constants and module-level helpers for the astrology package.

This is the original module-level block of the old single-file `astrology.py`,
moved verbatim: the jhora import + JHora-matching defaults (True Chitra ayanamsa,
mean nodes), the speed patch, every constant table, and the shared helpers.
Kept together because the tables and the jhora-dependent setup interleave;
splitting them further would not be a pure file move.

The compute mixins do `from .engine import *`, so `__all__` below deliberately
exports single-underscore names (_set_ayanamsa, _kp_lords, …) that the moved
method bodies reference by bare name.
"""
#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Dict, Optional, List
import sys
import os

import reference_data as refdata

# Add parent directory to path to import jhora
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

try:
    from jhora.panchanga import drik
    from jhora.horoscope.chart import charts, house, strength, yoga, dosha, arudhas, ashtakavarga
    from jhora.horoscope.match import compatibility as compat_module
    from jhora.horoscope.dhasa.graha import (vimsottari, ashtottari, yogini,
                                             shodasottari, dwadasottari,
                                             panchottari, sataatbika)
    from jhora.horoscope.dhasa.raasi import (narayana, kalachakra, kendradhi_rasi,
                                             sudasa, drig, chara, sthira, trikona)
    # Sudarshana Chakra dasha (§2.7) — lives directly under dhasa/, not graha/raasi,
    # because its "lord" is a *triple* of houses (from Lagna, Moon and Sun) rather
    # than a single graha or rasi.
    from jhora.horoscope.dhasa import sudharsana_chakra
    from jhora import utils, const
    import swisseph as swe

    # Match Jagannatha Hora's default ayanamsa: True Chitra Paksha (Spica fixed
    # at 180°). Jyotir AI defaults to TRUE_PUSHYA. Note True Chitra differs from
    # traditional Lahiri by only ~1', but that's enough to flip a body sitting on
    # a navamsa/varga cusp into the next division vs JHora.
    const._DEFAULT_AYANAMSA_MODE = 'TRUE_CITRA'
    drik.set_ayanamsa_mode('TRUE_CITRA')

    # Match Jagannatha Hora's default lunar nodes (Mean). Jyotir AI defaults to
    # True nodes, which differ from Mean by up to ~1.6°. In wide D1 signs this is
    # invisible, but in finer vargas (e.g. D10's 3° divisions) it flips Rahu/Ketu
    # one division/house off vs JHora. set_planet_list rebuilds the swe planet
    # mapping the chart code actually iterates (const.set_node_mode alone won't).
    drik.set_planet_list(set_rahu_ketu_as_true_nodes=False)

    # ── Speed patch: drik.true_sidereal_year ──────────────────────────────
    #
    # `dhasa_year_duration` (and so EVERY annual/varsha dasha — Mudda, Patyayini,
    # Narayana, Chara, Sudasa …) calls `true_sidereal_year`, which locates the
    # Sun's ingress into sidereal Aries with `previous/next_planet_entry_date`.
    # Those default to **0.01-day micro-steps**, so reaching an ingress up to a
    # year away costs ~36,500 steps — ~36k `sidereal_longitude` calls and ~0.5s
    # for a single Varshaphal (0.95s for Narayana, which calls it twice). On
    # slower hardware that is seconds-to-tens-of-seconds, and the request times
    # out at the gateway. (Same micro-stepping trap already documented for
    # `next_planet_entry_date` elsewhere in this file.)
    #
    # Fix: the Sun moves ~0.9856°/day, so we can predict each ingress to within a
    # day and hand the engine a start point ~5 days short of it. The engine then
    # micro-steps those few days instead of a whole year — its own search, its own
    # tolerance, so the result is **bit-identical** (verified across 1970-2075:
    # 18/18 exact) at ~36x fewer ephemeris calls. Nothing about the astrology
    # changes; only how far we make it walk to get there.
    _SUN_DEG_PER_DAY = 0.985647
    _engine_true_sidereal_year = drik.true_sidereal_year

    def _fast_true_sidereal_year(jd, place, round_to_digits=6):
        try:
            sun_long = drik.sidereal_longitude(jd - place.timezone / 24.0, const._SUN)
            to_next = ((360.0 - sun_long) % 360.0) / _SUN_DEG_PER_DAY
            since_prev = (sun_long % 360.0) / _SUN_DEG_PER_DAY
            # Seed a few days on the near side of each ingress and let the engine
            # walk the rest, exactly as it would have.
            nxt, _ = drik.next_planet_entry_date(
                const.SUN_ID, jd + to_next - 5.0, place, raasi=1)
            prv, _ = drik.previous_planet_entry_date(
                const.SUN_ID, jd - since_prev + 5.0, place, raasi=1)
            return nxt - prv
        except Exception as e:  # never let the shortcut break a dasha
            print(f"[perf] true_sidereal_year fast path failed ({e}); using engine")
            return _engine_true_sidereal_year(jd, place, round_to_digits)

    drik.true_sidereal_year = _fast_true_sidereal_year

    # The compressed annual Tithi Ashtottari (the dasha JHora pairs with the Tithi
    # Pravesha chart). Lives outside this module because it is pure elongation
    # geometry the engine does not ship — see varsha_tithi_ashtottari.
    import varsha_tithi_ashtottari as vta

    ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"Jyotir AI import error: {e}")
    ENGINE_AVAILABLE = False

DEFAULT_AYANAMSA = "TRUE_CITRA"

# Curated, user-facing ayanamsa options (value -> label). Values must exist in
# Jyotir AI's const.available_ayanamsa_modes. True Chitra is listed first as the
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
    for unknown values. Returns the key that was actually applied.

    ⚠️ **MUST run on the main thread.** Swiss Ephemeris keeps its sidereal mode in
    process-global C state, and calling `set_ayanamsa_mode` from a *worker* thread
    corrupts it: every subsequent `swe.calc_ut` then receives a garbage Julian day
    (`jd -0.001010 outside Moshier planet range`) and each compute returns
    `{"status": "failed"}`. Verified: on a worker thread the primitives
    (`swe.julday`, `rasi_chart`, `planets_in_retrograde`) all work *until*
    `_set_ayanamsa` is called, after which they all fail.

    We are safe today only because **every FastAPI endpoint in `main.py` is
    `async def`**, so handlers run on the event loop (the main thread). Declaring
    an endpoint as a plain `def` hands it to Starlette's threadpool and would
    silently break every chart on the site. Same for `run_in_threadpool` /
    `asyncio.to_thread` / `ThreadPoolExecutor` around any AstrologyCompute call.
    (This is also why `TestClient`, which drives the app from a worker thread,
    reports failed transits where a real request succeeds — a harness artifact of
    the same root cause, not a production bug.)
    """
    key = (name or DEFAULT_AYANAMSA).upper()
    if key not in SUPPORTED_AYANAMSAS:
        key = DEFAULT_AYANAMSA
    if ENGINE_AVAILABLE:
        drik.set_ayanamsa_mode(key)
    return key


# Jyotir AI planet indexing: 0=Sun … 8=Ketu.
PLANET_NAMES = {
    0: "Sun", 1: "Moon", 2: "Mars", 3: "Mercury",
    4: "Jupiter", 5: "Venus", 6: "Saturn", 7: "Rahu", 8: "Ketu",
}

# Reverse lookup (name -> index) for resolving a dasha lord-path sent by the UI.
PLANET_INDICES = {v: k for k, v in PLANET_NAMES.items()}

# PyJHora ships message resources (yoga / raja-yoga / dosha names + descriptions) only
# for these languages — see src/jhora/lang/. There is NO Sanskrit file upstream.
ENGINE_LANGUAGES = frozenset({"en", "ta", "te", "hi", "ka", "ml"})


def to_engine_language(lang: Optional[str]) -> str:
    """Map a UI language code onto one PyJHora actually has message files for.

    Sanskrit routes to Hindi rather than English on purpose: upstream has no `sa`
    resources, and Hindi shares both the script and most of this vocabulary with
    Sanskrit, so it lands far closer for a Sanskrit reader than English would.
    Authoring real `sa` lang files upstream is tracked in web/todo.md §5.

    Note this is a per-call argument to PyJHora's get_*_resources(), NOT the global
    utils.set_language() — so it needs no set/reset and is safe under concurrency.

    Design and traps: web/docs/I18N_DATA_LAYER_DESIGN.md. Before using this for a new
    section, read §4.3 there: PyJHora eval()s its message files' KEYS as function names,
    so passing a language into detection changes *which* yogas are found. Detect in
    English, translate by key.
    """
    base = (lang or "en").split("-")[0].lower()
    if base == "sa":
        return "hi"
    return base if base in ENGINE_LANGUAGES else "en"

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

# ── Krishnamurti Paddhati (KP) & Jaimini helpers ───────────────────────────
# Python weekday (0=Mon .. 6=Sun) → KP/vedic day-lord planet index.
_WEEKDAY_LORD = {6: 0, 0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6}


def _kp_lords(planet_key, abs_long):
    """Sign / star (nakshatra) / sub / sub-sub lord names for an absolute
    longitude (0-360), via Jyotir AI's KP micro-lord calculator. Also returns the
    raw star-lord index (for significator maths)."""
    info = utils.kp_lords_for_longitude(
        planet_key, abs_long % 360.0, include_sign_lord=True,
        include_kp_index=True, levels=2)[planet_key]
    kp_no, sign_lord, star_lord, sub_lord, sub_sub_lord = info[:5]
    return {
        "kp_no": int(kp_no),
        "sign_lord": PLANET_NAMES.get(sign_lord, str(sign_lord)),
        "star_lord": PLANET_NAMES.get(star_lord, str(star_lord)),
        "sub_lord": PLANET_NAMES.get(sub_lord, str(sub_lord)),
        "sub_sub_lord": PLANET_NAMES.get(sub_sub_lord, str(sub_sub_lord)),
        "star_lord_idx": int(star_lord),
    }


def _kp_significators(planet_positions):
    """KP four-fold significators from a rasi chart (list of [pid,(sign,long)]
    with the Ascendant 'L' at index 0).

    Returns (per_planet, per_house):
      per_planet[name] = {star_lord, houses[]} — the houses a planet signifies,
        ordered strongest → weakest (its star-lord's occupation, its star-lord's
        ownerships, its own occupation, its own ownerships).
      per_house[h] = {A,B,C,D} — the planets that signify house h grouped by the
        classical KP level:  A = planets in the star of the house's occupant
        (their star-lord occupies h), B = the house's occupants, C = planets in
        the star of the house's owner (their star-lord owns h), D = the owner(s)."""
    lagna_sign = planet_positions[0][1][0]
    house_of = lambda sign: ((sign - lagna_sign) % 12) + 1
    ppos = {pid: (sign, sign * 30.0 + long)
            for pid, (sign, long) in planet_positions[1:] if pid in PLANET_NAMES}
    occ_house = {p: house_of(s) for p, (s, _l) in ppos.items()}
    owned = {p: [] for p in ppos}
    for sign in range(12):
        lord = SIGN_LORD[sign]
        if lord in owned:
            owned[lord].append(house_of(sign))
    star_lord = {p: utils.kp_lords_for_longitude(
        p, ppos[p][1] % 360.0, include_sign_lord=False,
        include_kp_index=False, levels=1)[p][0] for p in ppos}

    per_planet = {}
    for p in ppos:
        sl = star_lord[p]
        houses = []
        for h in ([occ_house[sl]] if sl in occ_house else []) + owned.get(sl, []) \
                + [occ_house[p]] + owned.get(p, []):
            if h not in houses:
                houses.append(h)
        per_planet[PLANET_NAMES[p]] = {
            "star_lord": PLANET_NAMES.get(sl, str(sl)),
            "houses": houses,
        }

    per_house = {}
    for h in range(1, 13):
        per_house[h] = {
            "A": [PLANET_NAMES[p] for p in ppos
                  if star_lord[p] in occ_house and occ_house[star_lord[p]] == h],
            "B": [PLANET_NAMES[p] for p in ppos if occ_house[p] == h],
            "C": [PLANET_NAMES[p] for p in ppos if h in owned.get(star_lord[p], [])],
            "D": [PLANET_NAMES[p] for p in ppos if h in owned.get(p, [])],
        }
    return per_planet, per_house


def _kp_ruling_planets(y, m, d, hh, mm, place_obj):
    """KP Ruling Planets for a moment: the day-lord, the Moon's sign/star/sub
    lords and the Ascendant's sign/star/sub lords, plus the ordered unique set."""
    from datetime import date as _date
    jd = swe.julday(y, m, d, hh + mm / 60.0)
    pp = charts.rasi_chart(jd, place_obj)
    asc_sign, asc_long = pp[0][1]
    moon_sign, moon_long = pp[2][1]  # [Asc, Sun, Moon, ...]
    asc = _kp_lords("L", asc_sign * 30.0 + asc_long)
    moon = _kp_lords(1, moon_sign * 30.0 + moon_long)
    day_lord = PLANET_NAMES[_WEEKDAY_LORD[_date(y, m, d).weekday()]]
    order = [day_lord, moon["star_lord"], moon["sign_lord"],
             asc["star_lord"], asc["sign_lord"], asc["sub_lord"], moon["sub_lord"]]
    rp = []
    for x in order:
        if x not in rp:
            rp.append(x)
    return {
        "day_lord": day_lord,
        "moon": {"sign_lord": moon["sign_lord"], "star_lord": moon["star_lord"],
                 "sub_lord": moon["sub_lord"]},
        "ascendant": {"sign_lord": asc["sign_lord"], "star_lord": asc["star_lord"],
                      "sub_lord": asc["sub_lord"]},
        "planets": rp,
    }


# Curated divisional charts (Parashara's Shodasavarga). Each entry:
#   factor -> (code, name, significance). The factor is passed straight to
#   Jyotir AI's charts.divisional_chart(divisional_chart_factor=...).
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
    # ── Chakra dasha — a triple lord (Lagna / Moon / Sun wheels) ───────────
    "sudharsana_chakra": {
        "name": "Sudarshana Chakra Dasha", "lord_type": "chakra",
        "description": "One-year progression around three wheels at once — the "
                       "active house counted from the Lagna, the Moon and the Sun. "
                       "Read the same year from all three for a fuller verdict.",
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

# ── Sensitive points (§11.1) ───────────────────────────────────────────────
# Sphutas: sensitive longitudes derived from the natal chart (each engine fn
# takes (drik.Date, tob-tuple, place) and returns (sign_index, degree)).
#   label -> (sphuta.<fn>, significance)
SPHUTA_DEFS = [
    ("Tri Sphuta",     "tri_sphuta",     "Longevity / body (Lagna+Moon+Gulika)"),
    ("Chatur Sphuta",  "chatur_sphuta",  "Adds the Sun — vitality & self"),
    ("Pancha Sphuta",  "pancha_sphuta",  "Adds Rahu — overall karmic sum"),
    ("Prana Sphuta",   "prana_sphuta",   "Vital force, the breath of life"),
    ("Deha Sphuta",    "deha_sphuta",    "The physical body"),
    ("Mrityu Sphuta",  "mrityu_sphuta",  "Sensitive point of mortality (handle gently)"),
    ("Beeja Sphuta",   "beeja_sphuta",   "Male reproductive vitality (Sun+Jup+Venus)"),
    ("Kshetra Sphuta", "kshetra_sphuta", "Female reproductive vitality (Moon+Jup+Mars)"),
    ("Sookshma Tri Sphuta", "sookshma_tri_sphuta", "Subtle refinement of Tri Sphuta"),
    ("Tithi Sphuta",   "tithi_sphuta",   "Lunar-day point (Moon−Sun)"),
    ("Yoga Sphuta",    "yoga_sphuta",    "Sun+Moon combined point"),
    ("Rahu Tithi Sphuta", "rahu_tithi_sphuta", "Rahu-based lunar-day point"),
    ("Yogi Sphuta",    "yogi_sphuta",    "The benefic Yogi point"),
    ("Avayogi Sphuta", "avayogi_sphuta", "The malefic Avayogi point"),
]

# ── Special lagnas ─────────────────────────────────────────────────────────
# Two families, distinguished by how they are computed:
#
#   "time"  — the kaala lagnas. All four start from the Sun's longitude at
#             sunrise and advance at a fixed rate with elapsed time, so they are
#             extremely birth-time-sensitive. drik exposes one lambda each.
#   "point" — derived from natal positions (Moon, Rahu, the ascendant), so they
#             move at ordinary speeds. These are the five we already shipped.
#
# Every function here takes (jd, place) and returns [sign_index, degrees].
#   (label, family, drik function name, significance, minutes-per-degree drift)
SPECIAL_LAGNA_DEFS = [
    ("Bhava Lagna",    "time",  "bhava_lagna",
     "The body and physical existence; read with Hora and Ghati Lagna as a trio."),
    ("Hora Lagna",     "time",  "hora_lagna",
     "Wealth and the flow of income. Judge the 2nd and 11th from it."),
    ("Ghati Lagna",    "time",  "ghati_lagna",
     "Power, authority and rise in status. Judge the 10th from it."),
    ("Vighati Lagna",  "time",  "vighati_lagna",
     "Moves ~1 sign per 4 minutes — only meaningful with a second-accurate birth time."),
    ("Sree Lagna",     "point", "sree_lagna",
     "Prosperity and Lakshmi; the flowering of the chart's fortune."),
    ("Indu Lagna",     "point", "indu_lagna",
     "The wealth lagna of the Moon-based kala system."),
    ("Bhrigu Bindu",   "point", "bhrigu_bindhu_lagna",
     "Moon–Rahu midpoint; a karmic trigger point for major life events."),
    ("Pranapada Lagna", "point", "pranapada_lagna",
     "The vital breath; sensitive to birth-time error."),
    ("Kunda Lagna",    "point", "kunda_lagna",
     "A subtle point used in Nadi and event-timing work."),
]

# Only these carry enough classical rule-weight to drive interpretation. The
# rest are computed and displayed, but deliberately not narrated — see the
# Tripataki precedent (draw it, don't invent a verdict).
INTERPRETED_SPECIAL_LAGNAS = ("Bhava Lagna", "Hora Lagna", "Ghati Lagna", "Varnada Lagna")

# ── Upagrahas ──────────────────────────────────────────────────────────────
# Kaala-velas ("sons of Saturn"): each is the ascendant rising at the middle
# (or, for Maandi, the beginning) of a given planet's eighth-part of the day.
# fn(dob_date, tob_tuple, place) -> [sign, degrees].
KAALA_VELA_DEFS = [
    ("Gulika",        "gulika_longitude",
     "The most-used upagraha. Its house and lord mark chronic difficulty."),
    ("Maandi",        "maandi_longitude",
     "Gulika's begin-of-part variant, used in Kerala-tradition timing."),
    ("Kaala",         "kaala_longitude",
     "Upagraha of the Sun — obstruction from authority."),
    ("Mrityu",        "mrityu_longitude",
     "Upagraha of Mars — friction and accident-prone areas (non-literal)."),
    ("Artha Prahara", "artha_praharaka_longitude",
     "Upagraha of Mercury — loss through communication or contracts."),
    ("Yama Ghantaka", "yama_ghantaka_longitude",
     "Upagraha of Jupiter — obstruction to counsel and good fortune."),
]

# Solar upagrahas: fixed offsets from the Sun's longitude.
# drik.solar_upagraha_longitudes(sun_longitude, key) -> [sign, degrees].
SOLAR_UPAGRAHA_DEFS = [
    ("Dhuma",       "dhuma",       "Sun + 133°20′ — smoke; obscuration."),
    ("Vyatipata",   "vyatipaata",  "360° − Dhuma; calamity and reversal."),
    ("Parivesha",   "parivesha",   "Vyatipata + 180° — halo; confinement."),
    ("Indrachapa",  "indrachaapa", "360° − Parivesha — the rainbow; brief promise."),
    ("Upaketu",     "upaketu",     "Indrachapa + 16°40′ — the comet; sudden endings."),
]

# ── Varnada lagna ──────────────────────────────────────────────────────────
# PyJHora implements four published derivations that genuinely disagree. Method 1
# (Sanjay Rath) is the app default: it reproduces Jagannatha Hora's V1..V12
# exactly (12/12 signs, <2″ on degrees) on the owner's reference chart.
# The kaala-vela upagrahas as *time* windows: which planet's eighth-part of the
# day each one rises in. Same planet indices const.day_rulers uses.
# Gulika/Maandi are omitted here — the panchanga already publishes Gulika Kalam
# via drik.trikalam, and two entries for one window would only confuse.
KAALA_VELA_PLANETS = [
    ("Kaala", 0),           # Sun's part
    ("Mrityu", 2),          # Mars' part
    ("Artha Prahara", 3),   # Mercury's part
    ("Yama Ghantaka", 4),   # Jupiter's part
]


def _hours_from_dms(value):
    """'05:25:27' / '05:25:27 AM' → 5.4242 float hours. None when unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    txt = str(value).replace(" AM", "").replace(" PM", "").strip()
    try:
        parts = [float(p) for p in txt.split(":")]
    except ValueError:
        return None
    if not parts:
        return None
    parts += [0.0] * (3 - len(parts))
    return parts[0] + parts[1] / 60.0 + parts[2] / 3600.0


VARNADA_METHODS = {
    1: ("Sanjay Rath", "Matches Jagannatha Hora. The app default."),
    2: ("Jha / Pandey", "Mirrors Rath's result across the Aries–Libra axis."),
    3: ("B. V. Raman", "Raman's Muhurta-tradition derivation."),
    4: ("Santhanam", "Santhanam's commentary derivation."),
}
DEFAULT_VARNADA_METHOD = 1

# The 36 natal Sahams (Arabic-part-like sensitive points). Each engine fn takes
# (planet_positions, night_time_birth); a few take positions only (handled with a
# TypeError fallback). label -> (saham.<fn>, significance).
NATAL_SAHAMS = [
    ("Punya",      "punya_saham",      "Fortune, merit, good deeds"),
    ("Vidya",      "vidya_saham",      "Education, learning"),
    ("Yasas",      "yasas_saham",      "Fame, reputation"),
    ("Mitra",      "mitra_saham",      "Friends, alliances"),
    ("Mahatmaya",  "mahatmaya_saham",  "Greatness, dignity"),
    ("Asha",       "asha_saham",       "Hopes, desires"),
    ("Samartha",   "samartha_saham",   "Capability, competence"),
    ("Bhratri",    "bhratri_saham",    "Siblings, brothers"),
    ("Gaurava",    "gaurava_saham",    "Respect, honour"),
    ("Pithri",     "pithri_saham",     "Father"),
    ("Rajya",      "rajya_saham",      "Authority, kingdom, high office"),
    ("Maathri",    "maathri_saham",    "Mother"),
    ("Puthra",     "puthra_saham",     "Children, progeny"),
    ("Jeeva",      "jeeva_saham",      "Vitality, life force"),
    ("Karma",      "karma_saham",      "Work, action, career"),
    ("Roga",       "roga_saham",       "Illness, health"),
    ("Kali",       "kali_saham",       "Strife, discord"),
    ("Sastra",     "sastra_saham",     "Learning, scriptures, weapons"),
    ("Bandhu",     "bandhu_saham",     "Relatives, kin"),
    ("Mrithyu",    "mrithyu_saham",    "Mortality (handle gently, non-literal)"),
    ("Paradesa",   "paradesa_saham",   "Foreign lands, travel"),
    ("Artha",      "artha_saham",      "Wealth, resources"),
    ("Paradara",   "paradara_saham",   "Relationships outside marriage"),
    ("Vanika",     "vanika_saham",     "Trade, commerce"),
    ("Karyasiddhi","karyasiddhi_saham","Accomplishment of undertakings"),
    ("Vivaha",     "vivaha_saham",     "Marriage"),
    ("Santapa",    "santapa_saham",    "Sorrow, distress"),
    ("Sraddha",    "sraddha_saham",    "Faith, sincerity"),
    ("Preethi",    "preethi_saham",    "Affection, love"),
    ("Jadya",      "jadya_saham",      "Dullness, inertia"),
    ("Vyaapaara",  "vyaapaara_saham",  "Business, enterprise"),
    ("Sathru",     "sathru_saham",     "Enemies, rivals"),
    ("Jalapatna",  "jalapatna_saham",  "Sea voyage, waters"),
    ("Bandhana",   "bandhana_saham",   "Bondage, confinement"),
    ("Apamrithyu", "apamrithyu_saham", "Sudden misfortune (non-literal)"),
    ("Laabha",     "laabha_saham",     "Gains, profit"),
]

# Argala (intervention) / Virodhargala (counter-intervention) houses, from a
# reference house: benefics/planets in the 2nd/4th/5th/11th cause argala, which
# is obstructed by planets in the 12th/10th/9th/3rd respectively. Labels mirror
# const.argala_houses / const.virodhargala_houses.
ARGALA_HOUSE_LABELS = ["2nd", "4th", "5th", "11th"]
VIRODHARGALA_HOUSE_LABELS = ["12th", "10th", "9th", "3rd"]

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
# — the order Jyotir AI's shubha_hora tables return. Benefics vs malefics give the
# hora a supportive/inauspicious tone (Moon/Mercury/Jupiter/Venus vs Sun/Mars/Saturn).
HORA_PLANETS = ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn"]
HORA_BENEFICS = {"Moon", "Mercury", "Jupiter", "Venus"}

# ── Kota Chakra (§2.7) ──────────────────────────────────────────────────────
# The fort: four concentric enclosures, read from the janma nakshatra outward-in.
# Malefics reaching the inner rings (especially Sthamba, the central pillar) are
# the classical danger signal; benefics there protect. Each ring's cells are
# offsets into the 28-star (Abhijit-inclusive) order — see
# const.kota_chakra_star_placement_from_birth_star.
KOTA_RINGS = [
    ("baahya", "Baahya", "Outer wall — the approach; events still at a distance."),
    ("praakaara", "Praakaara", "Rampart — the defences proper; pressure building."),
    ("durgantara", "Durgantara", "Inner fort — the breach point; matters get personal."),
    ("sthamba", "Sthamba", "Central pillar — the heart of the fort; the most sensitive point."),
]
# Malefics for the Kota reading. (The Moon is treated as benefic here; its waxing/
# waning nuance is out of scope for the fort's entry/exit verdict.)
KOTA_MALEFICS = {"Sun", "Mars", "Saturn", "Rahu", "Ketu"}
# The 28-star order the chakra is laid out in: the 27 nakshatras with Abhijit
# spliced in after Uttara Ashadha, matching const.abhijit_order_of_stars.
NAKSHATRA_NAMES_28 = NAKSHATRA_NAMES + ["Abhijit"]

# ── Tripataki Chakra (§2.7) ─────────────────────────────────────────────────
# The twelve rasis laid around the perimeter of a 5x5 grid, crossed by the three
# "pataki" (banner) lines the chakra is named for. Both tables are lifted verbatim
# from the engine's PyQt-only `ui.chakra.Tripataki`, which is the ONLY place it
# exists — the engine ships the *layout* and nothing else, so this is a faithful
# plot of where the grahas fall, not a scored reading (unlike Sarvatobhadra's
# vedha or Kota's rings, we would have to invent any verdict).
# Position i is rasi i (Aries=0 .. Pisces=11); coordinates are 1-5 grid units.
TRIPATAKI_RASI_POSITIONS = [
    (1, 3), (1, 4), (2, 5), (3, 5), (4, 5), (5, 4),
    (5, 3), (5, 2), (4, 1), (3, 1), (2, 1), (1, 2),
]
TRIPATAKI_LINES = {
    (2, 5): [(1, 4), (2, 1), (5, 2)],
    (3, 5): [(1, 3), (3, 1), (5, 3)],
    (4, 5): [(1, 2), (4, 1), (5, 4)],
    (2, 1): [(1, 2), (5, 4)],
    (3, 1): [(1, 3), (5, 3)],
    (4, 1): [(1, 4), (5, 2)],
    (1, 2): [(5, 2)],
    (1, 3): [(5, 3)],
    (1, 4): [(5, 4)],
}

# ── Kaala Chakra (§2.7) ─────────────────────────────────────────────────────
# A DIRECTIONAL chakra: the 28 stars (Abhijit included) sit as 4 inner stars
# around a hub plus 8 outer divisions of 3 stars, and each outer division IS a
# compass direction. A graha lands on its nakshatra's cell, so the chakra reads
# "which graha rules which direction right now" — the classical use is choosing a
# direction to travel/act in. Tables lifted verbatim from the engine's PyQt-only
# `ui.chakra.KaalaChakra`; offsets are counted from a base star.
KAALA_INNER_STARS = [4, 25, 18, 11]
KAALA_OUTER_DIVISIONS = [
    [5, 6, 7], [3, 2, 1], [26, 27, 28], [24, 23, 22],
    [19, 20, 21], [17, 16, 15], [12, 13, 14], [10, 9, 8],
]
# Direction per outer division, in the engine's order (its resource-string list:
# southeast, east, northeast, north, northwest, west, southwest, south).
KAALA_DIRECTIONS = ["Southeast", "East", "Northeast", "North",
                    "Northwest", "West", "Southwest", "South"]
# Degrees each division/inner star is drawn at, kept so the UI can lay out a wheel.
KAALA_INNER_ANGLES = [45, 135, 225, 315]
KAALA_OUTER_ANGLES = [45, 90, 135, 180, 225, 270, 315, 360]


def kaala_star_slot(nakshatra: int) -> int:
    """A 1-27 nakshatra -> its 0-based slot in the 28-star (Abhijit) order.

    Abhijit occupies slot 22 of 28, so every star at or past it shifts up one.
    This is the engine's own rule (`if p_star > const._ABHIJITH_STAR_INDEX:
    p_star += 1`) — grahas only ever carry a 1-27 star, so Abhijit's cell is
    never occupied.
    """
    s = int(nakshatra)
    if s > const._ABHIJITH_STAR_INDEX:
        s += 1
    return s - 1


# Sign classes (0-based rasi): chara (movable), sthira (fixed), dwiswabhava (dual).
MOVABLE_SIGNS = (0, 3, 6, 9)      # Aries, Cancer, Libra, Capricorn
FIXED_SIGNS = (1, 4, 7, 10)       # Taurus, Leo, Scorpio, Aquarius
DUAL_SIGNS = (2, 5, 8, 11)        # Gemini, Virgo, Sagittarius, Pisces


def _tripataki_vedha_map():
    """Which signs obstruct (vedha) which, on the Tripataki Chakra.

    The classical rules (the engine ships only the drawing, so these come from the
    Tajaka literature — see the §2.7 notes):
      • a **movable** sign has vedha with the **dual** signs, EXCEPT the dual sign
        in the 3rd from it;
      • a **fixed** sign has vedha with the other **fixed** signs;
      • a **dual** sign has vedha with the **movable** signs, EXCEPT the movable
        sign in the 11th from it.

    Derived here rather than hardcoded so the rules stay auditable. Note the two
    exclusions are the same four pairs seen from both ends (Aries-Gemini,
    Cancer-Virgo, Libra-Sagittarius, Capricorn-Pisces), which makes the map
    symmetric — vedha is mutual obstruction, and every sign ends up with exactly
    three vedha partners. `test_tripataki_vedha_rules` asserts both invariants.
    """
    def nth(frm, n):  # inclusive Vedic counting: the 1st from X is X itself
        return (frm + n - 1) % 12

    vedha = {s: set() for s in range(12)}
    for m in MOVABLE_SIGNS:
        for d in DUAL_SIGNS:
            if d != nth(m, 3):
                vedha[m].add(d)
    for d in DUAL_SIGNS:
        for m in MOVABLE_SIGNS:
            if m != nth(d, 11):
                vedha[d].add(m)
    for f in FIXED_SIGNS:
        for g in FIXED_SIGNS:
            if f != g:
                vedha[f].add(g)
    return {s: frozenset(v) for s, v in vedha.items()}


TRIPATAKI_VEDHA = _tripataki_vedha_map()

def sign_class(sign0):
    """'movable' | 'fixed' | 'dual' for a 0-based rasi."""
    if sign0 in MOVABLE_SIGNS:
        return "movable"
    if sign0 in FIXED_SIGNS:
        return "fixed"
    return "dual"

# Vakra-gathi (retrograde) epicycle periods, per planet index: (orbital period in
# days, number of synodic loops to draw). Mirrors ui/vakra_gathi_plot's table but
# lets us reimplement the loop with plain numpy (no PyQt/pyqtgraph). -1 = Earth.
RETRO_PERIODS = {
    2: (686.97959, 18), 3: (87.96926, 9), 4: (4332.8201, 12),
    5: (224.7008, 8), 6: (10755.699, 59), -1: (365.25636, 1),
}
# Planets that can be retrograde and have a meaningful station search (Rahu/Ketu
# are perpetually retrograde, handled separately).
RETRO_STATION_PLANETS = [2, 3, 4, 5, 6]

# ── Muhurta (electional astrology, §16) classification tables ──────────────
# Rikta tithis (the 4th/9th/14th of each paksha) are weak for beginnings; the
# absolute-tithi index 30 (Amavasya / new moon) is generally avoided too.
MUHURTA_RIKTA_TITHIS = {4, 9, 14}

# The classical inauspicious yogas to avoid for muhurta (matched by name).
MUHURTA_BAD_YOGAS = {
    "Vishkambha", "Atiganda", "Shula", "Ganda", "Vyaghata",
    "Vajra", "Vyatipata", "Parigha", "Vaidhriti",
}

# Universally benefic nakshatras — the safe default set for "general" work.
MUHURTA_BENEFIC_NAKSHATRAS = {
    "Ashwini", "Rohini", "Mrigashira", "Punarvasu", "Pushya", "Hasta",
    "Chitra", "Swati", "Anuradha", "Shravana", "Dhanishta", "Shatabhisha",
    "Uttara Phalguni", "Uttara Ashadha", "Uttara Bhadrapada", "Revati",
}

# Per-activity favourable nakshatras + weekdays (0=Sunday .. 6=Saturday),
# distilled from classical muhurta texts. `nakshatras` empty → use the benefic
# default set. These bias the day-scoring; they are guidance, not hard rules.
MUHURTA_ACTIVITIES = {
    "general": {
        "label": "General auspicious work",
        "nakshatras": set(),  # → benefic default
        "weekdays": {1, 3, 4, 5},  # Mon, Wed, Thu, Fri
    },
    "marriage": {
        "label": "Marriage / wedding",
        "nakshatras": {"Rohini", "Mrigashira", "Magha", "Uttara Phalguni", "Hasta",
                       "Swati", "Anuradha", "Mula", "Uttara Ashadha",
                       "Uttara Bhadrapada", "Revati"},
        "weekdays": {1, 3, 4, 5},  # Mon, Wed, Thu, Fri (avoid Tue/Sat/Sun)
    },
    "travel": {
        "label": "Travel / journey",
        "nakshatras": {"Ashwini", "Mrigashira", "Punarvasu", "Pushya", "Hasta",
                       "Anuradha", "Shravana", "Dhanishta", "Revati"},
        "weekdays": {1, 3, 4, 5},  # avoid Tue/Sat for setting out
    },
    "business": {
        "label": "New business / venture",
        "nakshatras": {"Ashwini", "Rohini", "Mrigashira", "Pushya", "Hasta",
                       "Chitra", "Swati", "Anuradha", "Uttara Phalguni",
                       "Uttara Ashadha", "Uttara Bhadrapada", "Revati"},
        "weekdays": {1, 3, 4, 5},  # Mon, Wed, Thu, Fri
    },
    "housewarming": {
        "label": "Housewarming (Griha Pravesh)",
        "nakshatras": {"Rohini", "Mrigashira", "Uttara Phalguni", "Hasta", "Chitra",
                       "Swati", "Anuradha", "Uttara Ashadha", "Dhanishta",
                       "Shatabhisha", "Uttara Bhadrapada", "Revati"},
        "weekdays": {1, 3, 4, 5},
    },
    "education": {
        "label": "Education / learning (Vidyarambha)",
        "nakshatras": {"Ashwini", "Punarvasu", "Pushya", "Hasta", "Chitra", "Swati",
                       "Anuradha", "Shravana", "Dhanishta", "Shatabhisha", "Revati",
                       "Uttara Phalguni", "Uttara Ashadha", "Uttara Bhadrapada"},
        "weekdays": {1, 3, 4, 5},  # Mercury/Jupiter/Venus/Moon days
    },
    "medical": {
        "label": "Medical treatment / surgery",
        "nakshatras": {"Ashwini", "Mrigashira", "Punarvasu", "Pushya", "Hasta",
                       "Chitra", "Revati"},
        "weekdays": {2, 6},  # Tue/Sat traditionally for surgery (Mars/Saturn)
    },
}

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

# ── Muhurta sub-tools (Tarabala / Chandrabala / Panchaka / Choghadiya) ──────
# The 9 Taras (from the birth star, counting to the day's star). Index =
# count_stars(birth, today) % 9; each carries a name + quality.
TARABALA_NAMES = [
    ("Parama Mitra", "very_good"),   # 0 (9th, 18th, 27th)
    ("Janma", "caution"),            # 1 (same star)
    ("Sampat", "very_good"),         # 2
    ("Vipat", "bad"),                # 3
    ("Kshema", "good"),              # 4
    ("Pratyak", "caution"),          # 5
    ("Sadhaka", "very_good"),        # 6
    ("Vadha", "bad"),                # 7 (Naidhana)
    ("Mitra", "good"),               # 8
]
# Chandrabala: the Moon's transit sign counted from the natal Moon. 1/3/6/7/10/11
# are favourable, 4/8/12 are to be avoided, the rest are neutral.
CHANDRABALA_GOOD = {1, 3, 6, 7, 10, 11}
CHANDRABALA_BAD = {4, 8, 12}

# Panchaka: the five "sticks" that fall when the Moon is in the last five
# nakshatras (Dhanishta 3rd pada → Revati). The dosha type is read from
# (tithi + nakshatra + vaara + lagna-rasi) mod 9.
PANCHAKA_NAKSHATRAS = {23, 24, 25, 26, 27}  # Dhanishta..Revati (1-based)
PANCHAKA_TYPES = {
    1: ("Mrityu Panchaka", "Risk to health/life — avoid new ventures"),
    2: ("Agni Panchaka", "Fire risk — avoid fire-related work"),
    4: ("Raja Panchaka", "Government/authority matters — actually favourable"),
    6: ("Chora Panchaka", "Theft/loss risk — guard valuables"),
    8: ("Roga Panchaka", "Illness risk — avoid beginnings"),
}
# Choghadiya: the day (sunrise→sunset) and night (sunset→next sunrise) are each
# split into 8 parts. The first part's lord depends on the weekday; the sequence
# then follows a fixed rota. Each choghadiya carries a nature.
CHOGHADIYA_NATURE = {
    "Amrit": "good", "Shubh": "good", "Labh": "good", "Char": "neutral",
    "Rog": "bad", "Kaal": "bad", "Udveg": "bad",
}
# Day sequence starting index per weekday (0=Sun..6=Sat), into this rota:
_CHOG_DAY_ROTA = ["Udveg", "Char", "Labh", "Amrit", "Kaal", "Shubh", "Rog"]
# The daytime first-choghadiya per weekday (classical): Sun→Udveg, Mon→Amrit,
# Tue→Rog, Wed→Labh, Thu→Shubh, Fri→Char, Sat→Kaal.
_CHOG_DAY_START = {0: "Udveg", 1: "Amrit", 2: "Rog", 3: "Labh",
                   4: "Shubh", 5: "Char", 6: "Kaal"}
# Night first-choghadiya per weekday: the 6th from the day-start (classical).
_CHOG_NIGHT_START = {0: "Shubh", 1: "Char", 2: "Kaal", 3: "Udveg",
                     4: "Amrit", 5: "Rog", 6: "Labh"}


def _choghadiya_sequence(start_name):
    """Eight choghadiya names following the fixed rota from `start_name`."""
    i = _CHOG_DAY_ROTA.index(start_name)
    return [_CHOG_DAY_ROTA[(i + k) % 7] for k in range(8)]


# ── Dignity + Remedies (traditional guidance, drawn from dignity/shadbala) ───
# Rasi (sign) lords, 0-based rasi → planet name.
RASI_LORDS = ["Mars", "Venus", "Mercury", "Moon", "Sun", "Mercury",
              "Venus", "Mars", "Jupiter", "Saturn", "Saturn", "Jupiter"]
# Exaltation sign (0-based rasi) per planet; debilitation is the opposite sign.
EXALTATION_SIGN = {"Sun": 0, "Moon": 1, "Mars": 9, "Mercury": 5,
                   "Jupiter": 3, "Venus": 11, "Saturn": 6}
# Own signs (0-based) per planet.
OWN_SIGNS = {
    "Sun": {4}, "Moon": {3}, "Mars": {0, 7}, "Mercury": {2, 5},
    "Jupiter": {8, 11}, "Venus": {1, 6}, "Saturn": {9, 10},
    "Rahu": set(), "Ketu": set(),
}

# ── Nadi karaka method ─────────────────────────────────────────────────────
# The naisargika (fixed natural) significations each graha stands for. This
# reading is built from the karakas and their placements by sign, NOT from
# houses or aspects — conjunctions (planets sharing a sign) carry the weight,
# and the slow movers (Jupiter, Saturn, Rahu) transiting a karaka's sign time
# its events. The signification lists are the traditional karakatwas; the
# life-area phrasing is ours. Spouse karaka is gender-sensitive: Venus is the
# wife-karaka (read for a man) and Jupiter the husband-karaka (read for a
# woman) — both are surfaced and the reader picks by the native's gender.
NADI_KARAKAS = {
    "Sun":     ["soul & vitality", "father", "authority & government", "status & fame", "health"],
    "Moon":    ["mind & emotions", "mother", "home & inner life", "public & the masses", "comforts"],
    "Mars":    ["energy & courage", "younger siblings", "land & property", "engineering & competition", "drive"],
    "Mercury": ["intellect & speech", "business & commerce", "education & analysis", "maternal relatives", "skill"],
    "Jupiter": ["wisdom & dharma", "children", "wealth & fortune", "teacher / guru", "husband-karaka (for a woman)"],
    "Venus":   ["marriage & partner", "love & pleasure", "vehicles & comforts", "arts & beauty", "wife-karaka (for a man)"],
    "Saturn":  ["career & profession", "discipline & labour", "longevity", "delay & detachment", "servants & the masses"],
    "Rahu":    ["worldly desire", "foreign & the unconventional", "sudden gains", "obsession & ambition"],
    "Ketu":    ["spirituality & moksha", "detachment", "loss & separation", "past-life skill"],
}

# Life themes, each headed by the planet that is its natural karaka. Read the
# theme through where that karaka sits, its dispositor, its star-lord and whom
# it sits with. Marriage carries both spouse karakas for the gender note.
NADI_THEMES = [
    ("Self, vitality & father",              ["Sun"]),
    ("Mind, mother & emotional life",        ["Moon"]),
    ("Drive, siblings & property",           ["Mars"]),
    ("Intellect, speech & business",         ["Mercury"]),
    ("Wisdom, children & fortune",           ["Jupiter"]),
    ("Marriage, partner & comforts",         ["Venus", "Jupiter"]),
    ("Career, discipline & longevity",       ["Saturn"]),
    ("Worldly desire & the unconventional",  ["Rahu"]),
    ("Detachment & liberation",              ["Ketu"]),
]
# Curated per-planet remedies (clearly traditional guidance, NOT prescriptive
# advice). Each carries the classical gemstone, beeja mantra, presiding deity,
# weekday, charitable donation and colour.
REMEDIES_TABLE = {
    "Sun": {"gemstone": "Ruby (Manikya)", "metal": "Gold/Copper",
            "mantra": "Om Hraam Hreem Hraum Sah Suryaya Namah", "mantra_count": "7,000",
            "deity": "Surya / Lord Shiva", "day": "Sunday",
            "donation": "Wheat, jaggery, copper to the needy", "color": "Red / Orange"},
    "Moon": {"gemstone": "Pearl (Moti)", "metal": "Silver",
             "mantra": "Om Shraam Shreem Shraum Sah Chandraya Namah", "mantra_count": "11,000",
             "deity": "Parvati / Lord Shiva", "day": "Monday",
             "donation": "Milk, rice, silver, white cloth", "color": "White"},
    "Mars": {"gemstone": "Red Coral (Moonga)", "metal": "Copper/Gold",
             "mantra": "Om Kraam Kreem Kraum Sah Bhaumaya Namah", "mantra_count": "10,000",
             "deity": "Hanuman / Kartikeya", "day": "Tuesday",
             "donation": "Red lentils (masoor), copper, red cloth", "color": "Red"},
    "Mercury": {"gemstone": "Emerald (Panna)", "metal": "Gold",
                "mantra": "Om Braam Breem Braum Sah Budhaya Namah", "mantra_count": "9,000",
                "deity": "Lord Vishnu / Ganesha", "day": "Wednesday",
                "donation": "Green gram (moong), green cloth", "color": "Green"},
    "Jupiter": {"gemstone": "Yellow Sapphire (Pukhraj)", "metal": "Gold",
                "mantra": "Om Graam Greem Graum Sah Gurave Namah", "mantra_count": "19,000",
                "deity": "Brihaspati / Lord Vishnu", "day": "Thursday",
                "donation": "Turmeric, gram dal (chana), gold, yellow cloth", "color": "Yellow"},
    "Venus": {"gemstone": "Diamond (Heera) / White Sapphire", "metal": "Silver/Platinum",
              "mantra": "Om Draam Dreem Draum Sah Shukraya Namah", "mantra_count": "16,000",
              "deity": "Goddess Lakshmi", "day": "Friday",
              "donation": "Curd, white cloth, silver, sugar", "color": "White / Pastel"},
    "Saturn": {"gemstone": "Blue Sapphire (Neelam)", "metal": "Iron/Steel",
               "mantra": "Om Praam Preem Praum Sah Shanaischaraya Namah", "mantra_count": "23,000",
               "deity": "Shani Dev / Hanuman", "day": "Saturday",
               "donation": "Sesame (til), mustard oil, iron, black cloth", "color": "Dark Blue / Black"},
    "Rahu": {"gemstone": "Hessonite (Gomed)", "metal": "Silver/Ashtadhatu",
             "mantra": "Om Bhraam Bhreem Bhraum Sah Rahave Namah", "mantra_count": "18,000",
             "deity": "Goddess Durga", "day": "Saturday",
             "donation": "Coconut, black gram (urad), mustard", "color": "Smoky / Grey"},
    "Ketu": {"gemstone": "Cat's Eye (Lehsunia)", "metal": "Silver/Ashtadhatu",
             "mantra": "Om Sraam Sreem Sraum Sah Ketave Namah", "mantra_count": "17,000",
             "deity": "Lord Ganesha", "day": "Tuesday",
             "donation": "Multicoloured blanket, sesame", "color": "Variegated / Brown"},
}


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


def _iso_datetime(jd):
    """A local Julian day as 'YYYY-MM-DDTHH:MM:SS'.

    Seconds are kept deliberately: the deepest Tithi Ashtottari periods (Deha) run
    well under a minute, and a pravesha instant truncated to the day is what made
    the compressed dasha come out 2.5 days wrong in the first place."""
    y, m, d, h = utils.jd_to_gregorian(jd)
    total = int(round(h * 3600))
    # Rounding 23:59:59.7 up must roll the date, not produce hour 24.
    if total >= 86400:
        y, m, d, _ = utils.jd_to_gregorian(jd + 0.5)
        total -= 86400
    hh, rem = divmod(total, 3600)
    mm, ss = divmod(rem, 60)
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}T{hh:02d}:{mm:02d}:{ss:02d}"


# Islamic (Hijri) month names for the tabular date.
HIJRI_MONTHS = [
    "Muharram", "Safar", "Rabi al-Awwal", "Rabi al-Thani", "Jumada al-Awwal",
    "Jumada al-Thani", "Rajab", "Shaban", "Ramadan", "Shawwal",
    "Dhu al-Qadah", "Dhu al-Hijjah",
]


def _hijri_tabular(jd):
    """Islamic (Hijri) date from a Julian day via the standard *tabular* civil
    calendar — pure arithmetic, place-independent. Reimplemented inline because
    Jyotir AI's `panchanga/hijri.py` imports pyIslam/hijridate (not installed) at
    module top. Returns {year, month, month_name, day} or None on failure."""
    import math
    try:
        days = math.floor(jd + 0.5) - math.floor(1948439.5 + 0.5) + 1
        year = int(math.floor((30 * days + 10646) / 10631))
        first = (year - 1) * 354 + math.floor((3 + 11 * year) / 30)
        month = int(min(12, math.ceil((days - first) / 29.5)))
        day = int(days - first - math.ceil(29.5 * (month - 1)))
        month = max(1, min(12, month))
        day = max(1, min(30, day))
        return {"year": year, "month": month,
                "month_name": HIJRI_MONTHS[month - 1], "day": day}
    except Exception:
        return None


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
# birth tithi & weekday). The grid layout below mirrors Jyotir AI's desktop
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
    _build_sbc_grid() if ENGINE_AVAILABLE else (None, {}, {}, {}, {}))


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
    if val == "L" or (ENGINE_AVAILABLE and val == const._ascendant_symbol):
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


# Export everything (including _single_underscore helpers) to the mixins.
__all__ = [_n for _n in dir() if not _n.startswith('__')]
