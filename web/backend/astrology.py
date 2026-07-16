#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Dict, Optional, List
import sys
import os

import reference_data as refdata

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
    ("Tithi Sphuta",   "tithi_sphuta",   "Lunar-day point (Moon−Sun)"),
    ("Yoga Sphuta",    "yoga_sphuta",    "Sun+Moon combined point"),
    ("Yogi Sphuta",    "yogi_sphuta",    "The benefic Yogi point"),
    ("Avayogi Sphuta", "avayogi_sphuta", "The malefic Avayogi point"),
]

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


class AstrologyCompute:
    """Core astrology calculations using Jyotir AI"""

    # Expose the module-level availability flag as a class attribute so callers
    # (e.g. the /health endpoint) can read AstrologyCompute.ENGINE_AVAILABLE.
    ENGINE_AVAILABLE = ENGINE_AVAILABLE

    @staticmethod
    def calculate_birth_chart(dob: str, tob: str, place: str,
                             lat: Optional[float] = None, lon: Optional[float] = None,
                             tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Calculate birth chart with planetary positions"""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

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

            # Planet name mapping (Jyotir AI convention: 0=Sun, 1=Moon, 2=Mars, 3=Mercury, 4=Jupiter, 5=Venus, 6=Saturn, 7=Rahu, 8=Ketu)
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

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
        Calculate Dasha periods (life periods) using Jyotir AI's accurate calculations
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

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

            # Get Mahadasha using Jyotir AI's built-in function
            mahadashas = vimsottari.vimsottari_mahadasa(jd, place_obj)

            # Planet name mapping (Jyotir AI standard indexing)
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

                # Calculate bhuktis (sub-periods) using Jyotir AI
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
                "note": "Vimsottari Dasha cycle is 120 years. Calculations based on Jyotir AI."
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
        from the natal chart with Jyotir AI's `vimsottari_immediate_children` so every
        level is recomputed at full (sub-day) precision rather than from rounded
        dates. Levels: 1=Maha, 2=Bhukti, 3=Antara, 4=Sookshma (leaf)."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

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

            # Resolve the requested lord-path (names -> Jyotir AI indices).
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
            # The 8 BAV contributors, in Jyotir AI's order.
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

        Jyotir AI itself flags these "experimental - accuracy not guaranteed", so the
        result is framed as a *suggestion to verify*, never an authoritative correction.
        Nudges the entered time within +/-(step*loop) minutes until the chosen suddhi
        check is satisfied and returns entered-vs-suggested time, the delta, which rule
        fired, and before/after chart summaries so the caller can render both kundalis.

        method: "nakshatra" (nakshatra suddhi - self-serve, no extra input),
                "lagna" (lagna suddhi) or "janma" (janma suddhi, needs `gender`:
                0=male, 1=female).
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}

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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}

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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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

    # House significations for the Bhava Bala display (1-based).
    _BHAVA_SIGNIFICATION = [
        "Self, body, vitality", "Wealth, family, speech", "Courage, siblings",
        "Home, mother, comfort", "Children, mind, learning", "Health, enemies, service",
        "Partner, marriage", "Longevity, change", "Fortune, dharma, father",
        "Career, status", "Gains, friends", "Loss, expense, liberation",
    ]

    @staticmethod
    def get_strength(dob: str, tob: str, place: str,
                     lat: Optional[float] = None, lon: Optional[float] = None,
                     tz: Optional[float] = None,
                     ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """The full strength picture, composed for a dedicated page:

          • **Shadbala** — the six-fold planetary strength (reuses `get_shadbala`):
            the sthana/kaala/dig/cheshta/naisargika/drik breakdown, total vs
            required rupas, ratio and rank for the seven grahas.
          • **Bhava Bala** — the strength of the twelve houses (rupas + ratio).
          • **Vimsopaka Bala** — the varga-based dignity score (0-20) per planet in
            three schemes: Shadvarga (6), Sapthavarga (7) and Shodhasavarga (16)."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        # Shadbala first — it manages (and resets) its own ayanamsa.
        sb = AstrologyCompute.get_shadbala(dob, tob, place, lat, lon, tz, ayanamsa=ayanamsa)
        if sb.get("status") != "success":
            return sb
        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0)

            # Bhava Bala — [shashtiamsa, rupas, ratio] each 12 houses.
            bb = strength.bhava_bala(jd, place_obj)
            bb_rupas, bb_ratio = bb[1], bb[2]
            bhava = []
            for h in range(12):
                bhava.append({
                    "house": h + 1,
                    "signification": AstrologyCompute._BHAVA_SIGNIFICATION[h],
                    "rupa": round(float(bb_rupas[h]), 2),
                    "strength_ratio": round(float(bb_ratio[h]), 2),
                    "sufficient": float(bb_ratio[h]) >= 1.0,
                })
            bhava_ranked = sorted(range(12), key=lambda i: bhava[i]["rupa"], reverse=True)
            for rank, i in enumerate(bhava_ranked, start=1):
                bhava[i]["rank"] = rank

            # Vimsopaka Bala (0-20) per planet, three varga schemes. Each engine
            # call returns {planet_idx: [count, "varga list", score]}.
            shad = charts.vimsopaka_shadvarga_of_planets(jd, place_obj)
            sapt = charts.vimsopaka_sapthavarga_of_planets(jd, place_obj)
            shod = charts.vimsopaka_shodhasavarga_of_planets(jd, place_obj)
            vimsopaka = []
            for p in range(9):  # Sun..Ketu
                vimsopaka.append({
                    "planet": PLANET_NAMES[p],
                    "shadvarga": round(float(shad[p][2]), 2),
                    "sapthavarga": round(float(sapt[p][2]), 2),
                    "shodhasavarga": round(float(shod[p][2]), 2),
                })

            return {
                "status": "success",
                "components": sb.get("components", []),
                "planets": sb.get("planets", []),
                "bhava_bala": bhava,
                "vimsopaka": vimsopaka,
                "vimsopaka_max": 20,
            }
        except Exception as e:
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

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
    def get_masa_pravesh(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None, date: Optional[str] = None,
                         year: Optional[int] = None, month: Optional[int] = None,
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Maasa Pravesha / Tajaka **monthly** (solar-return) horoscope.

        The Tajaka month is 1/12 of a solar-return year (~30.4 days), the Sun
        advancing 30° from its natal longitude per month — *not* a calendar month.
        By default the window containing `date` (today) is selected; pass an
        explicit solar `year` (native's age → year) + `month` (1-12) to target a
        specific window. Returns the monthly chart, the pravesh window
        (start/end instants), the progressed Muntha, the year-lord and the current
        Tajaka yogas — the monthly analogue of :meth:`get_varshaphal`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            import contextlib, io
            from jhora.horoscope.transit import tajaka, saham, tajaka_yoga
            from jhora import const as _const

            _set_ayanamsa(ayanamsa)

            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            jd_dob = swe.julday(y, m, d, hour + minute / 60.0)

            # ── Pick the (years, months) window ────────────────────────────
            birth_year = int(dob.split("-")[0])
            if year is not None and month is not None:
                years_param = int(year) - birth_year + 1
                months_param = max(1, min(12, int(month)))
            else:
                # Which monthly window contains the reference date? Use the
                # linear solar-year fraction from birth (good enough to select
                # the window; the engine then solves the exact pravesh instant).
                tz_now = tz_offset
                if date:
                    ry, rm, rd = map(int, date.split("-"))
                    jd_ref = swe.julday(ry, rm, rd, 12.0)
                else:
                    now = datetime.now(_utc.utc) + timedelta(hours=tz_now)
                    jd_ref = swe.julday(now.year, now.month, now.day, 12.0)
                frac = (jd_ref - jd_dob) / _const.tropical_year
                if frac < 0:
                    return {"error": "Date must be on or after the birth date",
                            "status": "failed"}
                years_elapsed = int(frac)
                month_idx = int((frac - years_elapsed) * 12)  # 0-11

                # The linear fraction is only an *estimate* — the true Maasa
                # Pravesha is where the Sun actually reaches natal-longitude+30°k,
                # which drifts a day or two from an even 1/12 of the year. Snap the
                # estimate onto the window that really contains the date by solving
                # the boundaries and walking the index until it does. Without this
                # the digest could return a window the requested date sits outside
                # of, and stepping back off a window's start would re-select that
                # same window instead of the previous one.
                idx = years_elapsed * 12 + month_idx      # months since birth
                for _ in range(4):
                    yp, mp = idx // 12 + 1, idx % 12 + 1
                    w_start = drik.next_solar_date(jd_dob, place_obj,
                                                   years=yp, months=mp)
                    n_yp, n_mp = (yp + 1, 1) if mp >= 12 else (yp, mp + 1)
                    w_end = drik.next_solar_date(jd_dob, place_obj,
                                                 years=n_yp, months=n_mp)
                    if jd_ref < w_start and idx > 0:
                        idx -= 1
                    elif jd_ref >= w_end:
                        idx += 1
                    else:
                        break
                years_param = idx // 12 + 1
                months_param = idx % 12 + 1
            age = years_param - 1

            # ── Monthly (Tajaka) chart + window boundaries ─────────────────
            cht, entry = tajaka.maasa_pravesh(jd_dob, place_obj,
                                              divisional_chart_factor=1,
                                              years=years_param, months=months_param)
            (ey, em, ed), etime = entry
            start_jd = drik.next_solar_date(jd_dob, place_obj,
                                            years=years_param, months=months_param)
            # Next month's entry closes this window (rolling 12 → next year).
            if months_param >= 12:
                next_yp, next_mp = years_param + 1, 1
            else:
                next_yp, next_mp = years_param, months_param + 1
            end_jd = drik.next_solar_date(jd_dob, place_obj,
                                          years=next_yp, months=next_mp)
            ny, nm, nd, _nf = utils.jd_to_gregorian(end_jd)
            month_entry = {"date": f"{ey:04d}-{em:02d}-{ed:02d}", "time": str(etime)}
            window = {
                "start": f"{ey:04d}-{em:02d}-{ed:02d}",
                "end": f"{ny:04d}-{nm:02d}-{nd:02d}",
                "month_index": months_param,
                "year": birth_year + age,
                "age": age,
            }

            asc_rasi, asc_deg = cht[0][1]
            lagna = {"house": asc_rasi + 1, "degrees": round(asc_deg, 2),
                     "sign_name": ZODIAC_NAMES[asc_rasi]}
            planets = {}
            for planet_index, (rasi, degrees) in cht[1:]:
                name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
                planets[name] = {"rasi": rasi, "house": rasi + 1,
                                 "degrees": round(degrees, 2),
                                 "sign_name": ZODIAC_NAMES[rasi]}

            # ── Muntha (natal Lagna advanced one sign per completed year) ──
            natal_chart = charts.divisional_chart(jd_dob, place_obj,
                                                  divisional_chart_factor=1)
            natal_asc = natal_chart[0][1][0]
            muntha_sign = tajaka.muntha_house(natal_asc, age)
            muntha = {"sign": muntha_sign, "sign_name": ZODIAC_NAMES[muntha_sign],
                      "house": ((muntha_sign - asc_rasi) % 12) + 1}

            year_lord = None
            try:
                yl_idx = tajaka.lord_of_the_year(jd_dob, place_obj, age)
                if yl_idx is not None and yl_idx in PLANET_NAMES:
                    year_lord = {"index": yl_idx, "planet": PLANET_NAMES[yl_idx]}
            except Exception as e:
                print(f"Masa-pravesh year-lord error: {e}")

            # Day/night of the month entry drives the Sahams' day/night formula.
            night_entry = False
            try:
                entry_hrs = drik.jd_to_gregorian(start_jd)[3]
                sr = utils.from_dms_str_to_dms(drik.sunrise(start_jd, place_obj)[1])
                ss = utils.from_dms_str_to_dms(drik.sunset(start_jd, place_obj)[1])
                sr_h = sr[0] + sr[1] / 60.0 + sr[2] / 3600.0
                ss_h = ss[0] + ss[1] / 60.0 + ss[2] / 3600.0
                night_entry = entry_hrs > ss_h or entry_hrs < sr_h
            except Exception as e:
                print(f"Masa-pravesh night-entry error: {e}")

            sahams = []
            for label, fn_name, significance in VARSHAPHAL_SAHAMS:
                try:
                    fn = getattr(saham, fn_name)
                    try:
                        s_long = fn(cht, night_entry)
                    except TypeError:
                        s_long = fn(cht)
                    s_long = float(s_long) % 360
                    s_sign = int(s_long // 30)
                    sahams.append({
                        "name": label, "significance": significance,
                        "sign": s_sign, "sign_name": ZODIAC_NAMES[s_sign],
                        "degrees": round(s_long % 30, 2),
                        "house": ((s_sign - asc_rasi) % 12) + 1,
                    })
                except Exception as e:
                    print(f"Masa-pravesh saham {label} error: {e}")

            tajaka_yogas = []
            p2h = utils.get_planet_house_dictionary_from_planet_positions(cht)
            _sink = io.StringIO()
            try:
                if tajaka_yoga.ishkavala_yoga(p2h):
                    tajaka_yogas.append({"name": "Ishkavala",
                        "description": "Planets confined to kendras and panapharas — "
                                       "wealth, happiness and good fortune this month."})
            except Exception:
                pass
            try:
                if tajaka_yoga.induvara_yoga(p2h):
                    tajaka_yogas.append({"name": "Induvara",
                        "description": "Planets confined to apoklimas — cautions of "
                                       "worries, obstacles and ill health this month."})
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ith_pairs = tajaka_yoga.get_ithasala_yoga_planet_pairs(cht)
                for p1, p2, _t in ith_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({"name": "Ithasala", "pair": [a, b],
                        "description": f"Applying aspect between {a} and {b} — the "
                                       "matter they signify tends to fructify this month."})
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ees_pairs = tajaka_yoga.get_eesarpha_yoga_planet_pairs(cht)
                for p1, p2 in ees_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({"name": "Eesarpha", "pair": [a, b],
                        "description": f"Separating aspect between {a} and {b} — the "
                                       "matter they signify tends to slip away or delay."})
            except Exception:
                pass

            return {
                "status": "success",
                "window": window,
                "month_entry": month_entry,
                "lagna": lagna,
                "planets": planets,
                "muntha": muntha,
                "year_lord": year_lord,
                "sahams": sahams,
                "tajaka_yogas": tajaka_yogas,
            }
        except Exception as e:
            print(f"Masa-pravesh error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # ── Lunar (tithi) pravesha ladder ──────────────────────────────────────
    #
    # Tajaka's *solar* ladder only has chart-bearing rungs at the year
    # (Varshaphal) and the month (Maasa Pravesha) — below that it drops to the
    # ~2.53-day "sixty-hour", so there is no solar week or fortnight.
    #
    # The *lunar* (tithi) ladder — which is the family Jagannatha Hora exposes as
    # daily / fortnightly / monthly / annual — is complete:
    #
    #   tithi (~0.98d) → paksha (~14.8d) → lunar month (~29.5d) → Tithi Pravesha (~354d)
    #
    # Each window is solved off drik's tithi-boundary primitives
    # (`_tithi_number_at_jd` + `_tithi_boundary_jd`, a bisection on the tithi
    # change). NOTE: `drik.next_tithi` is marked UNDER EXPERIMENTATION and its
    # backward branch is wrong (it sums the indices instead of differencing), so
    # we never use it — we walk boundaries ourselves.

    @staticmethod
    def _tithi_num(jd: float, place_obj) -> int:
        """Instantaneous tithi number (1-30) at `jd`."""
        return int(drik._tithi_number_at_jd(jd, place_obj))

    @staticmethod
    def _tithi_bound(jd: float, place_obj, direction: int) -> float:
        """Nearest tithi boundary before (-1) or after (+1) `jd`."""
        return drik._tithi_boundary_jd(jd, place_obj, direction=direction)

    @staticmethod
    def _walk_tithi(jd: float, place_obj, steps: int) -> float:
        """Advance `steps` tithi boundaries from `jd` (negative walks backwards)."""
        direction = 1 if steps >= 0 else -1
        cur = jd
        for _ in range(abs(int(steps))):
            cur = AstrologyCompute._tithi_bound(cur, place_obj, direction)
        return cur

    @staticmethod
    def _tithi_window(jd: float, place_obj) -> Dict:
        """The running tithi's window: {index, start_jd, end_jd}."""
        return {
            "index": AstrologyCompute._tithi_num(jd, place_obj),
            "start_jd": AstrologyCompute._tithi_bound(jd, place_obj, -1),
            "end_jd": AstrologyCompute._tithi_bound(jd, place_obj, +1),
        }

    @staticmethod
    def _paksha_window(jd: float, place_obj) -> Dict:
        """The running paksha (lunar fortnight): Shukla = tithis 1-15, Krishna =
        16-30. The window runs from *this* paksha's first tithi to the *next*
        paksha's first tithi — i.e. Shukla opens at tithi 1 and closes at 16,
        Krishna opens at 16 and closes at (the next) 1. Both boundaries are found
        with the direct tithi-index solver rather than by walking every tithi in
        between. Returns {paksha, tithi_index, start_jd, end_jd}."""
        n = AstrologyCompute._tithi_num(jd, place_obj)
        shukla = n <= 15
        opens, closes = (1, 16) if shukla else (16, 1)
        return {
            "paksha": "Shukla" if shukla else "Krishna",
            "tithi_index": n,
            "start_jd": AstrologyCompute._tithi_index_start(jd, place_obj, opens, -1),
            "end_jd": AstrologyCompute._tithi_index_start(jd, place_obj, closes, +1),
        }

    # Mean synodic month — the period over which a tithi index recurs.
    _SYNODIC_MONTH = 29.530588

    @staticmethod
    def _tithi_index_start(jd: float, place_obj, target: int, direction: int) -> Optional[float]:
        """Start-JD of the nearest tithi whose index == `target`, searching
        backwards (-1) or forwards (+1).

        A tithi index recurs once per synodic month, so we **jump straight to the
        estimated recurrence** (each tithi is 1/30 of a lunation) and then settle
        onto the exact boundary, correcting at most a couple of tithis for the
        Moon's non-uniform motion. Walking every boundary in between instead would
        cost ~30 bisections — ~1250 `tithi()` calls, each an inverse-Lagrange over
        17 lunar-phase samples — which is fast enough on a dev box but times out
        the request on slower hardware."""
        step = AstrologyCompute._SYNODIC_MONTH / 30.0  # ~one tithi
        cur = AstrologyCompute._tithi_num(jd, place_obj)
        if direction < 0:
            # Most recent occurrence at/before jd. If we are already inside the
            # target tithi, that occurrence is the one we're in.
            est = jd - ((cur - target) % 30) * step
        else:
            # The *next* occurrence strictly after jd. If we are already inside
            # the target tithi, it does not count — skip a full lunation to the
            # next recurrence (a tithi can run past 1 day, so "already in it" is
            # reachable even a day out from its start).
            ahead = (target - cur) % 30 or 30
            est = jd + ahead * step

        # Settle: the estimate lands within a tithi or two of the target.
        for _ in range(8):
            n = AstrologyCompute._tithi_num(est, place_obj)
            if n == target:
                return AstrologyCompute._tithi_bound(est, place_obj, -1)
            # Signed shortest distance (in tithis) from n to target.
            d = (target - n) % 30
            if d > 15:
                d -= 30
            if d > 0:  # step forward into the next tithi
                est = AstrologyCompute._tithi_bound(est, place_obj, +1) + 1e-3
            else:      # step back into the previous tithi
                est = AstrologyCompute._tithi_bound(est, place_obj, -1) - 1e-3
        return None

    @staticmethod
    def _lunar_month_window(jd: float, place_obj, birth_tithi: int) -> Optional[Dict]:
        """The lunar month as a *birth-tithi return*: from the most recent
        recurrence of the natal tithi at/before `jd` to its next recurrence
        (~29.5 days). Returns {tithi_index, start_jd, end_jd}."""
        start = AstrologyCompute._tithi_index_start(jd, place_obj, birth_tithi, -1)
        if start is None:
            return None
        end = AstrologyCompute._tithi_index_start(start + 1.0, place_obj, birth_tithi, +1)
        if end is None:
            return None
        return {"tithi_index": birth_tithi, "start_jd": start, "end_jd": end}

    @staticmethod
    def _pravesha_block(cht, jd_dob, place_obj, age: int,
                        with_sahams: bool = False, jd_event: Optional[float] = None) -> Dict:
        """The standard progressed-chart block shared by every pravesha rung
        (solar or lunar): Lagna, planets, Muntha, year-lord and the Tajaka yogas
        present in the cast chart. `cht` is a D1 planet-positions list.

        `with_sahams` additionally derives the curated Sahams from the cast chart
        (needs `jd_event`, the pravesha instant, for the day/night formula). Only
        the *annual* rungs surface Sahams — on a fortnight or a single tithi they
        are noise."""
        import contextlib, io
        from jhora.horoscope.transit import tajaka, tajaka_yoga

        asc_rasi, asc_deg = cht[0][1]
        lagna = {"house": asc_rasi + 1, "degrees": round(asc_deg, 2),
                 "sign_name": ZODIAC_NAMES[asc_rasi]}
        planets = {}
        for planet_index, (rasi, degrees) in cht[1:]:
            name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
            planets[name] = {"rasi": rasi, "house": rasi + 1,
                             "degrees": round(degrees, 2),
                             "sign_name": ZODIAC_NAMES[rasi]}

        natal_chart = charts.divisional_chart(jd_dob, place_obj, divisional_chart_factor=1)
        natal_asc = natal_chart[0][1][0]
        muntha_sign = tajaka.muntha_house(natal_asc, age)
        muntha = {"sign": muntha_sign, "sign_name": ZODIAC_NAMES[muntha_sign],
                  "house": ((muntha_sign - asc_rasi) % 12) + 1}

        year_lord = None
        try:
            yl_idx = tajaka.lord_of_the_year(jd_dob, place_obj, age)
            if yl_idx is not None and yl_idx in PLANET_NAMES:
                year_lord = {"index": yl_idx, "planet": PLANET_NAMES[yl_idx]}
        except Exception as e:
            print(f"[pravesha] year-lord error: {e}")

        yogas = []
        p2h = utils.get_planet_house_dictionary_from_planet_positions(cht)
        _sink = io.StringIO()
        try:
            if tajaka_yoga.ishkavala_yoga(p2h):
                yogas.append({"name": "Ishkavala",
                              "description": "Planets confined to kendras and panapharas — "
                                             "wealth, happiness and good fortune."})
        except Exception:
            pass
        try:
            if tajaka_yoga.induvara_yoga(p2h):
                yogas.append({"name": "Induvara",
                              "description": "Planets confined to apoklimas — cautions of "
                                             "worries, obstacles and ill health."})
        except Exception:
            pass
        for fn, label, blurb in (
            (tajaka_yoga.get_ithasala_yoga_planet_pairs, "Ithasala",
             "Applying aspect between {a} and {b} — the matter they signify tends to fructify."),
            (tajaka_yoga.get_eesarpha_yoga_planet_pairs, "Eesarpha",
             "Separating aspect between {a} and {b} — the matter they signify tends to slip away."),
        ):
            try:
                with contextlib.redirect_stdout(_sink):
                    pairs = fn(cht)
                for pair in pairs:
                    p1, p2 = pair[0], pair[1]
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    yogas.append({"name": label, "pair": [a, b],
                                  "description": blurb.format(a=a, b=b)})
            except Exception:
                pass

        block = {"lagna": lagna, "planets": planets, "muntha": muntha,
                 "year_lord": year_lord, "tajaka_yogas": yogas}

        if with_sahams:
            # Sahams are sensitive points derived from the cast chart's planetary
            # positions, so they are well-defined on any pravesha chart. Their
            # day/night formula keys off whether the pravesha instant is by day.
            from jhora.horoscope.transit import saham

            night_entry = False
            try:
                entry_hrs = drik.jd_to_gregorian(jd_event)[3]
                sr = utils.from_dms_str_to_dms(drik.sunrise(jd_event, place_obj)[1])
                ss = utils.from_dms_str_to_dms(drik.sunset(jd_event, place_obj)[1])
                sr_h = sr[0] + sr[1] / 60.0 + sr[2] / 3600.0
                ss_h = ss[0] + ss[1] / 60.0 + ss[2] / 3600.0
                night_entry = entry_hrs > ss_h or entry_hrs < sr_h
            except Exception as e:
                print(f"[pravesha] night-entry error: {e}")

            sahams = []
            for slabel, fn_name, significance in VARSHAPHAL_SAHAMS:
                try:
                    fn = getattr(saham, fn_name)
                    try:
                        s_long = fn(cht, night_entry)
                    except TypeError:
                        s_long = fn(cht)
                    s_long = float(s_long) % 360
                    s_sign = int(s_long // 30)
                    sahams.append({
                        "name": slabel, "significance": significance,
                        "sign": s_sign, "sign_name": ZODIAC_NAMES[s_sign],
                        "degrees": round(s_long % 30, 2),
                        "house": ((s_sign - asc_rasi) % 12) + 1,
                    })
                except Exception as e:
                    print(f"[pravesha] saham {slabel} error: {e}")
            block["sahams"] = sahams

        return block

    @staticmethod
    def _ta_rows(rows: List[Dict], level: int) -> List[Dict]:
        """Shape `varsha_tithi_ashtottari` periods for the API.

        `start_jd` / `span_deg` are handed back verbatim because the drill-down
        endpoint needs them to subdivide a period without re-deriving the whole
        tree from the pravesha instant."""
        from datetime import datetime as _dt

        now = _dt.now().isoformat(timespec="seconds")
        out = []
        for r in rows:
            start = _iso_datetime(r["start_jd"])
            end = _iso_datetime(r["end_jd"])
            out.append({
                "lord": r["lord"],
                "lord_name": PLANET_NAMES.get(r["lord"], str(r["lord"])),
                "start": start,
                "end": end,
                "span_days": round(r["span_days"], 4),
                "span_deg": r["span_deg"],
                "start_jd": r["start_jd"],
                "level": level,
                "level_name": vta.LEVEL_NAMES[min(level, vta.MAX_LEVEL)],
                "has_children": level < vta.MAX_LEVEL,
                "current": start <= now < end,
            })
        return out

    # What window each lunar rung's dasha is compressed into, for the label.
    _TA_WINDOW_LABEL = {
        "tithi": "this tithi",
        "paksha": "this fortnight",
        "month": "this lunar month",
        "annual": "this lunar year",
    }

    @staticmethod
    def get_varsha_tithi_ashtottari(anchor_jd: float, place_obj, cycle_deg: float,
                                    rung: str = "annual") -> Dict:
        """**Varsha Tithi Ashtottari** — the compressed dasha Jagannatha Hora shows
        beside the Tithi Pravesha chart ("Tithi Ashtottari Dasa of Janma tithi in
        D-1"). The whole 108-unit Ashtottari cycle is squeezed into the pravesha
        window, exactly as Mudda squeezes Vimsottari into the solar year.

        The compression is in **Moon−Sun elongation**, not in days: `cycle_deg` is
        the elongation the window sweeps (a tithi 12°, a fortnight 180°, a lunar
        month 360°, a pravesha year N × 360°) and each lord takes `allotment/108` of
        it. Because it is angular, the same construction serves every rung of the
        lunar ladder — a day is compressed exactly as a year is. See
        `varsha_tithi_ashtottari` for the algorithm and for why the engine's own
        Tithi Ashtottari functions cannot be used.

        Nine maha rows come back, not eight: the first is the balance of the period
        already running when the window opens (JHora lists it too), so a full cycle
        of eight still follows it."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            rows = vta.maha_periods(anchor_jd, place_obj, cycle_deg)
            window = AstrologyCompute._TA_WINDOW_LABEL.get(rung, "this window")
            return {
                "status": "success",
                "system": f"Tithi Ashtottari (compressed into {window})",
                "system_key": "varsha_tithi_ashtottari",
                "lord_type": "planet",
                "level": "maha",
                "rung": rung,
                "cycle_deg": cycle_deg,
                "lunar_months": vta.lunar_months_in(cycle_deg),
                "expandable": True,
                "periods": AstrologyCompute._ta_rows(rows, 0),
            }
        except Exception as e:
            print(f"Varsha-Tithi-Ashtottari error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_tithi_ashtottari_children(start_jd: float, lord: int, span_deg: float,
                                      level: int, lat: float, lon: float,
                                      tz: float, place: str = "") -> Dict:
        """The eight sub-periods of one Varsha Tithi Ashtottari period — the lazy
        drill-down behind the expandable dasha tree.

        Expanded on demand rather than served whole: six levels (Maha → Antara →
        Pratyantara → Sookshma → Prana → Deha) is 8⁶ ≈ 262k rows, and the deepest
        are under a minute long. A period is fully described by its start instant,
        lord and **degree** span, so a child level needs no other state — it
        subdivides that span by allotment, starting on the lord after the parent."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        if level >= vta.MAX_LEVEL:
            return {"status": "success", "periods": []}
        if int(lord) not in vta.ORDER:
            return {"error": f"Unknown dasha lord '{lord}'", "status": "failed"}
        # A period always has positive extent. A zero or negative span would walk
        # the elongation backwards and hand back periods that end before they
        # start, so refuse it rather than emit nonsense.
        if not span_deg or span_deg <= 0:
            return {"error": "A period's span must be positive", "status": "failed"}
        try:
            place_obj = drik.Place(place or "", lat, lon, tz)
            rows = vta.children(start_jd, int(lord), span_deg, place_obj)
            return {
                "status": "success",
                "level": level + 1,
                "level_name": vta.LEVEL_NAMES[level + 1],
                "periods": AstrologyCompute._ta_rows(rows, level + 1),
            }
        except Exception as e:
            print(f"Tithi-Ashtottari children error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def _tithi_pravesha_dates(by: int, bm: int, bd: int, hour: int, minute: int,
                              place_obj, year_number: int) -> List:
        """`vratha.tithi_pravesha`, but leap-day safe.

        The engine centres its ±30-day search on `Date(year_number, birth_month,
        birth_day)`. For a **29-February birth** that date does not exist in a
        non-leap target year, and the call dies converting it to a numpy datetime
        — so Tithi Pravesha was broken outright for leap-day natives.

        The anchor only *centres* the search window, so clamping 29 Feb → 28 Feb
        cannot change which date is found (the true TP is located by matching the
        birth tithi + lunar month inside that window). The birth tithi and lunar
        month are still taken from the real birth date, so nothing else shifts.
        Non-leap births take the engine's own path untouched."""
        from jhora.panchanga import vratha

        birth_date = drik.Date(by, bm, bd)
        birth_time = (hour, minute, 0)

        if not (bm == 2 and bd == 29):
            return vratha.tithi_pravesha(birth_date, birth_time, place_obj, year_number)

        window = 30
        anchor = drik.Date(year_number, 2, 28)  # 29 Feb may not exist in year_number
        start = utils.previous_panchanga_day(anchor, window)
        end = utils.next_panchanga_day(start, 2 * window)

        jd = utils.julian_day_number(birth_date, birth_time)
        _, _, _, bt_hours = utils.jd_to_gregorian(jd)
        t = drik.tithi(jd, place_obj)
        tm = drik.tamil_solar_month_and_date(birth_date, place_obj)
        t_frac = utils.get_fraction(t[1], t[2], bt_hours)

        results = vratha.search(place_obj, start, end,
                                tithi_index=t[0], tamil_month_index=tm[0] + 1)
        out = []
        for s_date, s_start, s_end, s_desc in results:
            t_len = s_end - s_start
            if s_start > 23.99:
                t_len += 24
            out.append((s_date, s_end - t_frac * t_len, s_end, s_desc))
        return out

    @staticmethod
    def get_lunar_pravesha(rung: str, dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None, date: Optional[str] = None,
                           year: Optional[int] = None,
                           ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A chart on the **lunar (tithi) pravesha ladder**, cast at the moment the
        window opens. `rung` is one of:

          * ``"tithi"``   — the running tithi (~0.98 days)
          * ``"paksha"``  — the running lunar fortnight, Shukla or Krishna (~14.8 days)
          * ``"month"``   — the birth-tithi return, i.e. the lunar month (~29.5 days)
          * ``"annual"``  — **Tithi Pravesha**: the natal tithi *and* lunar month
                            recurring (~354 days). This is Jagannatha Hora's TP chart,
                            the lunar-return counterpart of the solar Varshaphal.

        Returns the pravesha window (start/end), the chart cast at its opening
        instant, and the standard Muntha / year-lord / Tajaka-yoga block."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from jhora.panchanga import vratha

            _set_ayanamsa(ayanamsa)

            y, m, d = map(int, dob.split("-"))
            tp_ = tob.split(":")
            hour = int(tp_[0]); minute = int(tp_[1]) if len(tp_) > 1 else 0
            # Seconds are honoured here (they are ignored elsewhere) because the
            # compressed Tithi Ashtottari is unusually sensitive to them: the
            # balance rule winds the elongation back by up to a maha span, so the
            # whole table moves ~5.7 days per degree of birth elongation — about
            # 75 seconds of dasha for every 1 second of birth time.
            second = int(float(tp_[2])) if len(tp_) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            jd_dob = swe.julday(y, m, d, hour + minute / 60.0 + second / 3600.0)

            if date:
                ry, rm, rd = map(int, date.split("-"))
            else:
                now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
                ry, rm, rd = now.year, now.month, now.day
            jd_ref = swe.julday(ry, rm, rd, 12.0)

            birth_tithi = AstrologyCompute._tithi_num(jd_dob, place_obj)
            label = None
            paksha = None

            if rung == "annual":
                # Tithi Pravesha: find the date in `year` where the natal tithi +
                # lunar month recur, then take the window to the next year's.
                target_year = int(year) if year else ry
                birth_elongation = vta.elongation(jd_dob, place_obj)

                def tp_for(yr):
                    """The pravesha *instant*, exact in elongation.

                    The engine's search gives the right day but interpolates the
                    time linearly between the tithi's start and end, landing ~45-50
                    minutes early. Refining to the moment the Moon-Sun elongation
                    actually regains its birth value matters twice over: the chart
                    is cast at this instant (50 minutes is ~12 deg of ascendant),
                    and the compressed dasha winds its balance back by up to a full
                    maha span, which amplifies the error ~50x into a 2.5-day shift
                    of every period in the table."""
                    rows = AstrologyCompute._tithi_pravesha_dates(
                        y, m, d, hour, minute, place_obj, yr)
                    if not rows:
                        return None, None
                    (ty, tm, td), t_time, _t1, tp_label = rows[0]
                    seed = (utils.julian_day_number(drik.Date(ty, tm, td), (0, 0, 0))
                            + t_time / 24.0)
                    exact = vta.refine_pravesha(seed, birth_elongation, place_obj)
                    return (exact if exact is not None else seed), tp_label

                start_jd, tp_label = tp_for(target_year)
                if start_jd is None:
                    return {"error": "Tithi Pravesha could not be resolved for that year",
                            "status": "failed"}
                if not year and start_jd > jd_ref:
                    # This year's TP hasn't happened yet — we're still in last year's window.
                    prev_jd, prev_label = tp_for(target_year - 1)
                    if prev_jd is not None:
                        target_year -= 1
                        start_jd, tp_label = prev_jd, prev_label

                end_jd, _ = tp_for(target_year + 1)
                if end_jd is None:
                    # Next year's TP couldn't be resolved — close the window with a
                    # mean lunar year rather than failing the whole reading.
                    end_jd = start_jd + 354.367
                label = (tp_label or "").strip(" /")
                age = target_year - y
                window_extra = {"tp_year": target_year}
            else:
                if rung == "tithi":
                    w = AstrologyCompute._tithi_window(jd_ref, place_obj)
                    label = f"Tithi {w['index']}"
                elif rung == "paksha":
                    w = AstrologyCompute._paksha_window(jd_ref, place_obj)
                    paksha = w["paksha"]
                    label = f"{w['paksha']} Paksha"
                elif rung == "month":
                    w = AstrologyCompute._lunar_month_window(jd_ref, place_obj, birth_tithi)
                    if not w:
                        return {"error": "Could not resolve the lunar month window",
                                "status": "failed"}
                    label = f"Birth-tithi ({birth_tithi}) return"
                else:
                    return {"error": f"Unknown lunar rung '{rung}'", "status": "failed"}
                start_jd, end_jd = w["start_jd"], w["end_jd"]
                age = max(0, int((jd_ref - jd_dob) / 365.2425))
                window_extra = {"tithi_index": w.get("tithi_index")}

            sy_, sm_, sd_, _sf = utils.jd_to_gregorian(start_jd)
            ey_, em_, ed_, _ef = utils.jd_to_gregorian(end_jd)

            # Cast the D1 chart at the instant the window opens. The annual rung
            # (Tithi Pravesha) is the full-dress chart: it also carries the Sahams
            # and its own dasha, so the Solar/Lunar annual views are symmetrical.
            is_annual = rung == "annual"
            cht = charts.divisional_chart(start_jd, place_obj, divisional_chart_factor=1)
            block = AstrologyCompute._pravesha_block(
                cht, jd_dob, place_obj, age,
                with_sahams=is_annual, jd_event=start_jd)

            # Jagannatha Hora pairs the Tithi Pravesha chart with **Tithi Ashtottari**
            # — a tithi-reckoned dasha for a tithi-reckoned chart. (The Tajaka annual
            # dashas — Mudda/Patyayini/Narayana — belong to the *solar* return and are
            # not carried over here.)
            #
            # It is the *compressed* form: the whole 108-unit cycle squeezed into this
            # window, as Mudda squeezes Vimsottari into the solar year. Every rung of
            # the ladder gets one, not just the annual — the compression is in
            # elongation, and each rung is a clean fraction or multiple of a turn
            # (tithi 12 deg, paksha 180, month 360, year N x 360), so the same dasha
            # tiles a day exactly as it tiles a year.
            cycle_deg = vta.cycle_degrees(start_jd, end_jd, place_obj)
            ta = AstrologyCompute.get_varsha_tithi_ashtottari(
                start_jd, place_obj, cycle_deg, rung=rung)
            tithi_ashtottari = ta if ta.get("status") == "success" else None

            return {
                "status": "success",
                "basis": "lunar",
                "rung": rung,
                "label": label,
                "paksha": paksha,
                "birth_tithi": birth_tithi,
                "window": {
                    "start": f"{sy_:04d}-{sm_:02d}-{sd_:02d}",
                    "end": f"{ey_:04d}-{em_:02d}-{ed_:02d}",
                    # The chart is cast at the instant, not the day — surface it, so
                    # the lagna can be checked against JHora's own TP chart.
                    "start_at": _iso_datetime(start_jd),
                    "end_at": _iso_datetime(end_jd),
                    "span_days": round(end_jd - start_jd, 2),
                    "age": age,
                    **window_extra,
                },
                # `tithi_ashtottari` on every rung; `annual_dasha` stays as the
                # annual rung's alias so the Varshaphal page can read the same key
                # for the solar (Mudda/Patyayini/Narayana) and lunar sides.
                "tithi_ashtottari": tithi_ashtottari,
                "annual_dasha": tithi_ashtottari if is_annual else None,
                **block,
            }
        except Exception as e:
            print(f"Lunar-pravesha ({rung}) error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_tithi_pravesha(dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None, year: Optional[int] = None,
                           date: Optional[str] = None,
                           ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """**Tithi Pravesha** — the annual *lunar*-return chart (the natal tithi and
        lunar month recurring, ~354 days). The lunar counterpart of Varshaphal's
        solar return, and the chart Jagannatha Hora calls the TP chart."""
        return AstrologyCompute.get_lunar_pravesha(
            "annual", dob, tob, place, lat=lat, lon=lon, tz=tz, date=date,
            year=year, ayanamsa=ayanamsa)

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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
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
                      tz: Optional[float] = None, system: str = "drik") -> Dict:
        """Daily almanac (panchanga) for a date + place: the five limbs
        (tithi, vaara, nakshatra, yoga, karana) plus sunrise/sunset and the
        inauspicious/auspicious periods (rahu kalam, yamaganda, gulika,
        durmuhurtam, abhijit). Elements are resolved at sunrise of the day,
        the traditional reference point. `date` defaults to today at `place`.

        `system` selects the ephemeris/ayanamsa engine: "drik" (default, the
        modern Drik-ganita under the app ayanamsa) or "surya_siddhanta" (the
        classical Surya-Siddhanta ayanamsa mode). Also includes the Hijri
        (Islamic tabular) date for the day."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        # Surya-Siddhanta = compute the limbs under the SURYASIDDHANTA ayanamsa
        # (the vendored surya_sidhantha.py module itself is buggy). Reset after.
        use_ss = (system or "drik").lower() in ("surya_siddhanta", "surya-siddhanta", "ss")
        try:
            from datetime import datetime, timezone as _utc, timedelta

            if use_ss:
                drik.set_ayanamsa_mode("SURYASIDDHANTA")

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
                "system": "surya_siddhanta" if use_ss else "drik",
                "hijri": _hijri_tabular(jd_noon),
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
        finally:
            if use_ss:
                drik.set_ayanamsa_mode(DEFAULT_AYANAMSA)

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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
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

    # ── Muhurta (electional astrology, §16) ────────────────────────────────
    @staticmethod
    def get_muhurta(activity: str = "general", start_date: Optional[str] = None,
                    end_date: Optional[str] = None, place: str = "",
                    lat: Optional[float] = None, lon: Optional[float] = None,
                    tz: Optional[float] = None, max_days: int = 31) -> Dict:
        """Find auspicious windows for an activity over a date range.

        For each day in [start_date, end_date] (capped at `max_days`) the day is
        scored from its Panchanga — nakshatra (per-activity favourable list),
        vaara (weekday), tithi (Rikta/Amavasya penalised) and yoga (the nine
        inauspicious yogas penalised). Qualifying days then contribute concrete
        time windows: the Abhijit muhurta and the benefic planetary horas
        (Moon/Mercury/Jupiter/Venus) that do NOT overlap Rahu Kalam, Yamaganda or
        Gulika. Returns the per-day summaries plus a ranked `best_windows` list.
        Location-driven (not birth-chart bound); reuses `get_panchanga` and
        `get_planetary_hours`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            act_key = (activity or "general").lower()
            act = MUHURTA_ACTIVITIES.get(act_key, MUHURTA_ACTIVITIES["general"])
            good_naks = act["nakshatras"] or MUHURTA_BENEFIC_NAKSHATRAS
            good_days = act["weekdays"]

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707

            # Default range: today .. +14 days, in the place's local time.
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            if start_date:
                sy, sm, sd = map(int, start_date.split("-"))
                start = datetime(sy, sm, sd)
            else:
                start = datetime(local_now.year, local_now.month, local_now.day)
            if end_date:
                ey, em, ed = map(int, end_date.split("-"))
                end = datetime(ey, em, ed)
            else:
                end = start + timedelta(days=14)
            if end < start:
                end = start
            n_days = min((end - start).days + 1, max_days)

            def _to_min(hhmm):
                try:
                    h, m = str(hhmm).split(":")[:2]
                    return int(h) * 60 + int(m)
                except Exception:
                    return None

            def _overlaps(a1, a2, periods):
                """True if window [a1,a2) overlaps any inauspicious [s,e)."""
                for s, e in periods:
                    if s is None or e is None:
                        continue
                    if a1 < e and s < a2:
                        return True
                return False

            days_out = []
            all_windows = []
            for i in range(n_days):
                d = start + timedelta(days=i)
                date_str = f"{d.year:04d}-{d.month:02d}-{d.day:02d}"
                panch = AstrologyCompute.get_panchanga(
                    date=date_str, place=place, lat=lat, lon=lon, tz=tz_offset)
                if panch.get("status") != "success":
                    continue

                nak_name = panch["nakshatra"]["name"]
                tithi_idx = panch["tithi"]["index"]
                yoga_name = panch["yoga"]["name"]
                weekday = panch["vaara"]["index"]
                within_paksha = tithi_idx if tithi_idx <= 15 else tithi_idx - 15

                # ── Score the day ──────────────────────────────────────────
                score = 0
                reasons = []
                if nak_name in good_naks:
                    score += 3
                    reasons.append(f"{nak_name} nakshatra favours this")
                elif nak_name in MUHURTA_BENEFIC_NAKSHATRAS:
                    score += 1
                    reasons.append(f"{nak_name} is a benefic nakshatra")
                else:
                    reasons.append(f"{nak_name} is not among the preferred stars")

                if weekday in good_days:
                    score += 1
                    reasons.append(f"{WEEKDAY_NAMES[weekday]} is a favourable weekday")

                if tithi_idx == 30:
                    score -= 2
                    reasons.append("Amavasya (new moon) — avoid for beginnings")
                elif within_paksha in MUHURTA_RIKTA_TITHIS:
                    score -= 2
                    reasons.append(f"{panch['tithi']['name']} is a Rikta tithi (weak)")
                else:
                    score += 1

                if yoga_name in MUHURTA_BAD_YOGAS:
                    score -= 2
                    reasons.append(f"{yoga_name} yoga is inauspicious")
                else:
                    score += 1

                if panch.get("karana", {}).get("name") == "Vishti":
                    score -= 1
                    reasons.append("Vishti (Bhadra) karana — avoid")

                rating = ("excellent" if score >= 5 else "good" if score >= 3
                          else "average" if score >= 1 else "avoid")

                # ── Build candidate windows for a non-"avoid" day ─────────
                windows = []
                if rating != "avoid":
                    bad_periods = []
                    for key in ("rahu_kalam", "yamaganda", "gulika"):
                        p = panch.get(key) or {}
                        bad_periods.append((_to_min(p.get("start")), _to_min(p.get("end"))))

                    # Abhijit muhurta (midday) — strong for most activities
                    # except marriage/travel where tradition is cautious.
                    abh = panch.get("abhijit")
                    if abh and act_key not in ("marriage", "travel"):
                        a1, a2 = _to_min(abh["start"]), _to_min(abh["end"])
                        if a1 is not None and not _overlaps(a1, a2, bad_periods):
                            windows.append({
                                "date": date_str, "start": abh["start"], "end": abh["end"],
                                "label": "Abhijit Muhurta", "quality": "excellent",
                                "reason": "Abhijit — the auspicious midday muhurta",
                                "day_score": score,
                            })

                    # Benefic daytime horas clear of the inauspicious periods.
                    hrs = AstrologyCompute.get_planetary_hours(
                        date=date_str, place=place, lat=lat, lon=lon, tz=tz_offset)
                    for h in (hrs.get("horas", []) if hrs.get("status") == "success" else []):
                        if h["period"] != "day" or not h["benefic"]:
                            continue
                        h1, h2 = _to_min(h["start"]), _to_min(h["end"])
                        if h1 is None or _overlaps(h1, h2, bad_periods):
                            continue
                        windows.append({
                            "date": date_str, "start": h["start"], "end": h["end"],
                            "label": f"{h['planet']} hora",
                            "quality": rating,
                            "reason": f"{h['planet']} (benefic) planetary hour",
                            "day_score": score,
                        })

                    all_windows.extend(windows)

                days_out.append({
                    "date": date_str,
                    "weekday": WEEKDAY_NAMES[weekday],
                    "score": score,
                    "rating": rating,
                    "tithi": panch["tithi"],
                    "nakshatra": panch["nakshatra"],
                    "yoga": panch["yoga"],
                    "karana": panch["karana"],
                    "sunrise": panch.get("sunrise"),
                    "sunset": panch.get("sunset"),
                    "rahu_kalam": panch.get("rahu_kalam"),
                    "reasons": reasons,
                    "windows": windows,
                })

            # Rank the best windows: Abhijit first, then higher day-score, then date.
            _q = {"excellent": 0, "good": 1, "average": 2, "avoid": 3}
            all_windows.sort(key=lambda w: (
                _q.get(w["quality"], 4),
                0 if w["label"] == "Abhijit Muhurta" else 1,
                -w["day_score"], w["date"], w["start"]))

            return {
                "status": "success",
                "activity": act_key,
                "activity_label": act["label"],
                "start_date": f"{start.year:04d}-{start.month:02d}-{start.day:02d}",
                "end_date": days_out[-1]["date"] if days_out else None,
                "place": place,
                "days": days_out,
                "best_windows": all_windows[:12],
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    # ── Muhurta sub-tools: Tarabala, Chandrabala, Panchaka, Choghadiya ──────
    @staticmethod
    def get_muhurta_subtools(date: Optional[str] = None, place: str = "",
                             lat: Optional[float] = None, lon: Optional[float] = None,
                             tz: Optional[float] = None,
                             birth_dob: Optional[str] = None,
                             birth_tob: Optional[str] = None,
                             birth_lat: Optional[float] = None,
                             birth_lon: Optional[float] = None,
                             birth_tz: Optional[float] = None) -> Dict:
        """Day-level muhurta helpers for a date + place: the Choghadiya table
        (day + night, each part with its nature), the Panchaka status, and — if
        birth details are supplied — the personal Tarabala (from the birth star)
        and Chandrabala (the transit Moon counted from the natal Moon). These are
        the small classical "should I act today?" checks that sit alongside the
        electional (muhurta) search. `date` defaults to today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
            date_str = f"{year:04d}-{month:02d}-{day:02d}"

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            jd_noon = swe.julday(year, month, day, 12)
            sr = drik.sunrise(jd_noon, place_obj)
            ss = drik.sunset(jd_noon, place_obj)
            jd_sr = sr[2]  # sunrise jd (for the day's limbs)

            weekday = drik.vaara(jd_noon, place_obj)  # 0=Sun..6=Sat
            nak = drik.nakshatra(jd_sr, place_obj)
            nak_idx = nak[0]  # 1..27
            tithi_idx = drik.tithi(jd_sr, place_obj)[0]  # 1..30
            # Transit Moon sign (0-based) at sunrise.
            moon_long = drik.lunar_longitude(jd_sr - tz_offset / 24.0)
            moon_rasi0 = int(moon_long // 30) % 12

            sr_h = sr[0]; ss_h = ss[0]
            # Next sunrise (end of night) — in hours past this day's sunrise.
            nsr = drik.sunrise(jd_noon + 1, place_obj)
            next_sr_h = nsr[0] + 24.0  # normalise onto the same 0..48 axis

            def _fmt_clock(h):
                h = h % 24
                hh = int(h); mm = int(round((h - hh) * 60))
                if mm == 60:
                    hh, mm = (hh + 1) % 24, 0
                return f"{hh:02d}:{mm:02d}"

            # ── Choghadiya (8 day + 8 night parts) ─────────────────────────
            day_len = (ss_h - sr_h) / 8.0
            night_len = (next_sr_h - ss_h) / 8.0
            day_seq = _choghadiya_sequence(_CHOG_DAY_START[weekday])
            night_seq = _choghadiya_sequence(_CHOG_NIGHT_START[weekday])
            now_local = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            is_today = (now_local.year, now_local.month, now_local.day) == (year, month, day)
            now_h = now_local.hour + now_local.minute / 60.0 if is_today else None

            def _build_chog(seq, base, length, period):
                out = []
                for k, name in enumerate(seq):
                    s = base + k * length
                    e = base + (k + 1) * length
                    current = (now_h is not None and s <= (now_h if period == "day" else now_h + (0 if now_h >= sr_h else 24)) < e)
                    out.append({
                        "name": name, "period": period,
                        "start": _fmt_clock(s), "end": _fmt_clock(e),
                        "nature": CHOGHADIYA_NATURE.get(name, "neutral"),
                        "current": bool(current),
                    })
                return out

            choghadiya = (_build_chog(day_seq, sr_h, day_len, "day")
                          + _build_chog(night_seq, ss_h, night_len, "night"))

            # ── Panchaka ───────────────────────────────────────────────────
            # The classical day-panchaka dosha: (tithi + nakshatra + vaara +
            # lagna-rasi) mod 9; a result of 1/2/4/6/8 names an active dosha,
            # otherwise the day is Panchaka-rahita (free). A separate almanac
            # "Panchak" marks the Moon in the last five nakshatras.
            asc_rasi = drik.ascendant(jd_sr, place_obj)[0] + 1  # 1-based lagna sign
            rem = (tithi_idx + nak_idx + (weekday + 1) + asc_rasi) % 9
            ptype, pmeaning = PANCHAKA_TYPES.get(rem, (None, None))
            active = ptype is not None
            panchaka = {
                "active": active,
                "type": ptype,
                "meaning": pmeaning if active
                else "Panchaka-rahita — free of the Panchaka dosha today",
                "moon_in_panchaka_nakshatra": nak_idx in PANCHAKA_NAKSHATRAS,
                "nakshatra": NAKSHATRA_NAMES[nak_idx - 1],
            }

            result = {
                "status": "success",
                "date": date_str,
                "place": place,
                "weekday": WEEKDAY_NAMES[weekday],
                "sunrise": _fmt_clock(sr_h),
                "sunset": _fmt_clock(ss_h),
                "choghadiya": choghadiya,
                "panchaka": panchaka,
                "today_nakshatra": NAKSHATRA_NAMES[nak_idx - 1],
                "moon_sign": ZODIAC_NAMES[moon_rasi0],
                "tarabala": None,
                "chandrabala": None,
            }

            # ── Personal Tarabala + Chandrabala (need the natal Moon) ──────
            if birth_dob and birth_tob:
                try:
                    by, bm, bd = map(int, birth_dob.split("-"))
                    btp = birth_tob.split(":")
                    bh = int(btp[0]); bmin = int(btp[1]) if len(btp) > 1 else 0
                    blat = birth_lat if birth_lat else lat
                    blon = birth_lon if birth_lon else lon
                    btz = birth_tz if birth_tz is not None else tz_offset
                    bplace = drik.Place(place or "", blat, blon, btz)
                    bjd = swe.julday(by, bm, bd, bh + bmin / 60.0)
                    b_moon_long = drik.lunar_longitude(bjd - btz / 24.0)
                    birth_star = int(b_moon_long // (360.0 / 27.0)) + 1  # 1..27
                    birth_moon_rasi0 = int(b_moon_long // 30) % 12

                    # Tarabala: count from birth star to today's star.
                    tb_div = utils.count_stars(birth_star, nak_idx) % 9
                    tname, tquality = TARABALA_NAMES[tb_div]
                    result["tarabala"] = {
                        "birth_star": NAKSHATRA_NAMES[birth_star - 1],
                        "today_star": NAKSHATRA_NAMES[nak_idx - 1],
                        "tara": tname,
                        "quality": tquality,
                        "count": utils.count_stars(birth_star, nak_idx),
                    }

                    # Chandrabala: transit Moon sign from the natal Moon sign.
                    pos = utils.count_rasis(birth_moon_rasi0 + 1, moon_rasi0 + 1)
                    cb_quality = ("good" if pos in CHANDRABALA_GOOD
                                  else "bad" if pos in CHANDRABALA_BAD else "neutral")
                    result["chandrabala"] = {
                        "birth_moon_sign": ZODIAC_NAMES[birth_moon_rasi0],
                        "transit_moon_sign": ZODIAC_NAMES[moon_rasi0],
                        "position": pos,
                        "quality": cb_quality,
                    }
                except Exception:
                    import traceback
                    traceback.print_exc()

            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    # ── Prashna / horary (§16) ─────────────────────────────────────────────
    @staticmethod
    def get_prashna(question: Optional[str] = None, date: Optional[str] = None,
                    time: Optional[str] = None, place: str = "",
                    lat: Optional[float] = None, lon: Optional[float] = None,
                    tz: Optional[float] = None,
                    ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Cast a Prashna (horary) chart for the *moment the question is asked* —
        no birth data needed. The Ascendant and Moon at that instant are the
        querent and the mind/question; the rest of the chart answers it. Reuses
        the natal compute at "now + current location" and layers the day's
        Panchanga + running planetary hour on top for classical horary context."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707

            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            if date:
                y, m, dd = map(int, date.split("-"))
            else:
                y, m, dd = local_now.year, local_now.month, local_now.day
            if time:
                tp = time.split(":")
                hh = int(tp[0]); mi = int(tp[1]) if len(tp) > 1 else 0
            else:
                hh, mi = local_now.hour, local_now.minute
            date_str = f"{y:04d}-{m:02d}-{dd:02d}"
            time_str = f"{hh:02d}:{mi:02d}"

            chart = AstrologyCompute.calculate_birth_chart(
                dob=date_str, tob=time_str, place=place,
                lat=lat, lon=lon, tz=tz_offset, ayanamsa=ayanamsa)
            if "error" in chart:
                return {"error": chart["error"], "status": "failed"}

            d1 = chart.get("d1_chart", {})
            lagna = chart.get("lagna", {})
            moon = d1.get("Moon", {})
            sun = d1.get("Sun", {})

            # Day panchanga + the running planetary hour (hora) — horary context.
            panch = AstrologyCompute.get_panchanga(
                date=date_str, place=place, lat=lat, lon=lon, tz=tz_offset)
            hrs = AstrologyCompute.get_planetary_hours(
                date=date_str, place=place, lat=lat, lon=lon, tz=tz_offset)
            hora_lord = None
            for h in (hrs.get("horas", []) if hrs.get("status") == "success" else []):
                if h.get("current"):
                    hora_lord = h.get("planet")
                    break

            return {
                "status": "success",
                "question": question or "",
                "moment": {"date": date_str, "time": time_str, "tz": tz_offset},
                "place": place,
                "lagna": lagna,
                "moon": moon,
                "sun": sun,
                "planets": d1,
                "navamsa": chart.get("d9_chart", {}),
                "d9_lagna": chart.get("d9_lagna", {}),
                "panchanga": panch if panch.get("status") == "success" else None,
                "hora_lord": hora_lord,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    # ── Krishnamurti Paddhati (KP) (§16) ───────────────────────────────────
    @staticmethod
    def get_kp_details(dob: str, tob: str, place: str,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None, ayanamsa: str = "KP") -> Dict:
        """Krishnamurti Paddhati view of a natal chart: the sign / star (nakshatra)
        / sub / sub-sub lord of the Ascendant and every graha, the 12 Placidus
        (KP) cuspal sub-lords, the four-fold house significators, and the current
        Ruling Planets. KP always reads on the Krishnamurti ayanamsa, so this
        endpoint forces it regardless of the app's selected ayanamsa."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa("KP")
            from datetime import datetime, timezone as _utc, timedelta
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_off = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_off)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)
            pp = charts.rasi_chart(jd, place_obj)
            lagna_sign = pp[0][1][0]

            def _body(label, pid, sign, long):
                d = _kp_lords(pid, sign * 30.0 + long)
                return {"body": label, "sign_name": ZODIAC_NAMES[sign % 12],
                        "degrees": round(long, 2),
                        "house": ((sign - lagna_sign) % 12) + 1,
                        "kp_no": d["kp_no"], "sign_lord": d["sign_lord"],
                        "star_lord": d["star_lord"], "sub_lord": d["sub_lord"],
                        "sub_sub_lord": d["sub_sub_lord"]}

            asc_sign, asc_long = pp[0][1]
            planets = [_body("Ascendant", "L", asc_sign, asc_long)]
            for pid, (sign, long) in pp[1:]:
                if pid in PLANET_NAMES:
                    planets.append(_body(PLANET_NAMES[pid], pid, sign, long))

            # 12 Placidus (KP) house cusps with their sub-lords.
            cusps = []
            try:
                for i, cl in enumerate(drik.bhaava_madhya_kp(jd, place_obj)):
                    sign = int(cl // 30) % 12
                    d = _kp_lords("C%d" % (i + 1), cl)
                    cusps.append({"house": i + 1, "sign_name": ZODIAC_NAMES[sign],
                                  "degrees": round(cl % 30, 2), "sign_lord": d["sign_lord"],
                                  "star_lord": d["star_lord"], "sub_lord": d["sub_lord"]})
            except Exception:
                pass

            per_planet, per_house = _kp_significators(pp)
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_off)
            rp = _kp_ruling_planets(local_now.year, local_now.month, local_now.day,
                                    local_now.hour, local_now.minute, place_obj)
            return {"status": "success", "ayanamsa": "KP", "planets": planets,
                    "cusps": cusps, "significators": per_planet,
                    "house_significators": per_house, "ruling_planets": rp,
                    "ruling_time": local_now.strftime("%Y-%m-%d %H:%M")}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_kp_horary(number: int, date: Optional[str] = None,
                      time: Optional[str] = None, place: str = "",
                      lat: Optional[float] = None, lon: Optional[float] = None,
                      tz: Optional[float] = None) -> Dict:
        """KP horary (Prasna) for a number 1-249. The querent picks a number; the
        classical 249-fold table fixes the Ascendant's sign/star/sub division, the
        rest of the chart is cast for the moment (defaults to now + here), and the
        Ruling Planets are read for the same instant. Uses the KP ayanamsa."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            number = int(number)
            if number < 1 or number > 249:
                return {"error": "Horary number must be between 1 and 249", "status": "failed"}
            _set_ayanamsa("KP")
            from datetime import datetime, timezone as _utc, timedelta
            tz_off = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_off)
            if date:
                y, m, dd = map(int, date.split("-"))
            else:
                y, m, dd = local_now.year, local_now.month, local_now.day
            if time:
                tpp = time.split(":"); hh = int(tpp[0]); mi = int(tpp[1]) if len(tpp) > 1 else 0
            else:
                hh, mi = local_now.hour, local_now.minute
            date_str = f"{y:04d}-{m:02d}-{dd:02d}"; time_str = f"{hh:02d}:{mi:02d}"
            place_obj = drik.Place(place, lat, lon, tz_off)
            jd = swe.julday(y, m, dd, hh + mi / 60.0)

            # 249 table: [rasi, nakshatra, start_deg, end_deg, sign_lord, star_lord, sub_lord]
            rasi, nak, start, end, sl, stl, subl = const.prasna_kp_249_dict[number]
            asc_deg = (float(start) + float(end)) / 2.0
            ascendant = {"number": number, "sign_name": ZODIAC_NAMES[int(rasi) % 12],
                         "degrees": round(asc_deg, 2), "sign_lord": PLANET_NAMES.get(sl, str(sl)),
                         "star_lord": PLANET_NAMES.get(stl, str(stl)),
                         "sub_lord": PLANET_NAMES.get(subl, str(subl))}

            # Planet sub-lords at the moment (rendered on the horary Ascendant sign).
            pp = charts.rasi_chart(jd, place_obj)
            planets, planets_for_chart = [], {}
            for pid, (sign, long) in pp[1:]:
                if pid not in PLANET_NAMES:
                    continue
                name = PLANET_NAMES[pid]
                d = _kp_lords(pid, sign * 30.0 + long)
                planets.append({"body": name, "sign_name": ZODIAC_NAMES[sign % 12],
                                "degrees": round(long, 2), "house": ((sign - int(rasi)) % 12) + 1,
                                "sign_lord": d["sign_lord"], "star_lord": d["star_lord"],
                                "sub_lord": d["sub_lord"], "retrograde": long < 0})
                planets_for_chart[name] = {"house": sign + 1, "degrees": round(long, 2),
                                           "sign_name": ZODIAC_NAMES[sign % 12]}

            rp = _kp_ruling_planets(y, m, dd, hh, mi, place_obj)
            return {"status": "success", "number": number, "ascendant": ascendant,
                    "planets": planets, "ruling_planets": rp,
                    "moment": {"date": date_str, "time": time_str, "tz": tz_off},
                    "place": place,
                    "chart": {"planets": planets_for_chart,
                              "lagna": {"house": int(rasi) + 1, "degrees": round(asc_deg, 2),
                                        "sign_name": ZODIAC_NAMES[int(rasi) % 12]}}}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # ── Jaimini deep-dive (§16) ────────────────────────────────────────────
    @staticmethod
    def get_jaimini(dob: str, tob: str, place: str,
                    lat: Optional[float] = None, lon: Optional[float] = None,
                    tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Jaimini toolkit: the 8 Chara Karakas (with sign/house), the Karakamsa
        (the Atmakaraka's Navamsa sign) and Swamsa (D9 Lagna) with their occupants
        and Jaimini (rasi-drishti) aspects, plus the Argala (intervention) on the
        Lagna and 7th house. Grounded in Jyotir AI's house/arudha engine."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
            d9 = charts.divisional_chart(jd, place_obj, divisional_chart_factor=9)
            lagna_sign = pp[0][1][0]

            karaka_names = ["Atma (AK)", "Amatya (AmK)", "Bhratri (BK)", "Matri (MK)",
                            "Pitri (PiK)", "Putra (PK)", "Jnati (GK)", "Dara (DK)"]
            ck = house.chara_karakas(pp)
            # sign each planet occupies in the D1
            d1_sign = {pid: sign for pid, (sign, _l) in pp[1:] if pid in PLANET_NAMES}
            chara_karakas = []
            for i, idx in enumerate(ck):
                if i >= len(karaka_names):
                    break
                sign = d1_sign.get(idx)
                chara_karakas.append({
                    "karaka": karaka_names[i], "planet": PLANET_NAMES.get(idx, str(idx)),
                    "sign_name": ZODIAC_NAMES[sign % 12] if sign is not None else "—",
                    "house": (((sign - lagna_sign) % 12) + 1) if sign is not None else None,
                })
            atma = ck[0]  # Atmakaraka planet index

            # Karakamsa = the Navamsa sign of the Atmakaraka. Swamsa = D9 Lagna.
            d9_sign = {pid: sign for pid, (sign, _l) in d9[1:] if pid in PLANET_NAMES}
            karakamsa_sign = d9_sign.get(atma)
            swamsa_sign = d9[0][1][0]
            h2p_d9 = utils.get_house_planet_list_from_planet_positions(d9)

            def _occ_and_aspects(target_sign):
                if target_sign is None:
                    return {"sign_name": "—", "occupants": [], "aspecting_planets": []}
                occ = [PLANET_NAMES[pid] for pid, s in d9_sign.items() if s == target_sign]
                asp = house.aspected_planets_of_the_raasi(h2p_d9, target_sign)
                asp_names = [PLANET_NAMES.get(int(p), str(p)) for p in asp]
                return {"sign_name": ZODIAC_NAMES[target_sign % 12], "occupants": occ,
                        "aspecting_planets": asp_names}

            karakamsa = {"planet": PLANET_NAMES.get(atma, str(atma)), **_occ_and_aspects(karakamsa_sign)}
            swamsa = _occ_and_aspects(swamsa_sign)

            # Argala (intervention) on the Lagna (1st) and 7th house, from the D1.
            h2p = utils.get_house_planet_list_from_planet_positions(pp)
            argala_all, virodha_all = house.get_argala(h2p)

            def _clean(lst):
                out = []
                for cell in lst:
                    for p in str(cell).replace("/", " ").split():
                        if p.isdigit() and int(p) in PLANET_NAMES:
                            out.append(PLANET_NAMES[int(p)])
                return out

            argala = []
            for h in (1, 7):
                r = (lagna_sign + h - 1) % 12
                argala.append({"house": h, "sign_name": ZODIAC_NAMES[r],
                               "argala": _clean(argala_all[r]),
                               "virodhargala": _clean(virodha_all[r])})

            return {"status": "success", "chara_karakas": chara_karakas,
                    "atmakaraka": PLANET_NAMES.get(atma, str(atma)),
                    "karakamsa": karakamsa, "swamsa": swamsa, "argala": argala}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # ── Chart-of-the-moment / "now" chart (§16) ────────────────────────────
    @staticmethod
    def get_now_chart(place: str = "", lat: Optional[float] = None,
                      lon: Optional[float] = None, tz: Optional[float] = None,
                      current_time: Optional[str] = None,
                      current_tz: Optional[float] = None,
                      ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """The current sky cast as a chart for this instant + location (defaults to
        now + here). Reuses the natal compute at the present moment and layers the
        day's Panchanga + running planetary-hour lord. Powers the Dashboard
        'chart of the moment' widget and the standalone Now page."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            tz_off = current_tz if current_tz is not None else (tz if tz is not None else 5.5)
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_off)
            if current_time:
                # ISO 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DD HH:MM'
                s = current_time.replace("T", " ")
                dpart, _, tpart = s.partition(" ")
                y, m, dd = map(int, dpart.split("-"))
                tps = tpart.split(":") if tpart else [str(local_now.hour), str(local_now.minute)]
                hh = int(tps[0]); mi = int(tps[1]) if len(tps) > 1 else 0
            else:
                y, m, dd, hh, mi = (local_now.year, local_now.month, local_now.day,
                                    local_now.hour, local_now.minute)
            date_str = f"{y:04d}-{m:02d}-{dd:02d}"; time_str = f"{hh:02d}:{mi:02d}"

            chart = AstrologyCompute.calculate_birth_chart(
                dob=date_str, tob=time_str, place=place, lat=lat, lon=lon,
                tz=tz_off, ayanamsa=ayanamsa)
            if "error" in chart:
                return {"error": chart["error"], "status": "failed"}

            panch = AstrologyCompute.get_panchanga(
                date=date_str, place=place, lat=lat, lon=lon, tz=tz_off)
            hrs = AstrologyCompute.get_planetary_hours(
                date=date_str, place=place, lat=lat, lon=lon, tz=tz_off)
            hora_lord = None
            for h in (hrs.get("horas", []) if hrs.get("status") == "success" else []):
                if h.get("current"):
                    hora_lord = h.get("planet")
                    break

            return {
                "status": "success",
                "moment": {"date": date_str, "time": time_str, "tz": tz_off},
                "place": place,
                "lagna": chart.get("lagna", {}),
                "planets": chart.get("planets", {}),
                "d1_chart": chart.get("d1_chart", {}),
                "panchanga": panch if panch.get("status") == "success" else None,
                "hora_lord": hora_lord,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    # ── Daily digest (§16) ─────────────────────────────────────────────────
    @staticmethod
    def get_daily_digest(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None, date: Optional[str] = None,
                         current_time: Optional[str] = None,
                         current_tz: Optional[float] = None,
                         basis: str = "solar",
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A personalized "Today" card: the day's Panchanga at the person's place,
        their running Vimsottari dasha (flagging a change if the current Bhukti
        ends within ~30 days), the headline transits (Sade-Sati / Jupiter's house
        from natal Moon, retrograde grahas, next Jupiter/Saturn ingress), and a
        list of plain highlight strings. Assembled from the existing panchanga /
        dasha / transit computes.

        With `basis="lunar"` the card also carries the **tithi pravesha** chart —
        the D1 cast at the moment the running tithi opened, with its Muntha and
        Tajaka yogas. (The solar ladder has no daily rung, so `basis="solar"`
        leaves the card chart-less, exactly as before.)"""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            tz_offset = tz if tz is not None else 5.5
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            date_str = date or f"{local_now.year:04d}-{local_now.month:02d}-{local_now.day:02d}"

            panch = AstrologyCompute.get_panchanga(
                date=date_str, place=place, lat=lat, lon=lon, tz=tz_offset)
            transits = AstrologyCompute.get_transits(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                current_date=date_str, current_time=current_time,
                current_tz=current_tz, ayanamsa=ayanamsa)
            dashas = AstrologyCompute.get_dashas(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz)

            highlights = []

            # Panchanga headline.
            if panch.get("status") == "success":
                # tithi['name'] already carries the paksha prefix (e.g. "Krishna Tritiya").
                highlights.append(
                    f"{panch['vaara']['name']} · {panch['tithi']['name']}, "
                    f"{panch['nakshatra']['name']} nakshatra")

            # Dasha snapshot + imminent change.
            dasha_block = None
            if dashas.get("status") != "failed" and dashas.get("current_dasha"):
                cur = dashas["current_dasha"]
                bhukti_periods = (dashas.get("current_bhukthi") or {}).get("periods", [])
                today = datetime.strptime(date_str, "%Y-%m-%d")
                running_bhukti = None
                for b in bhukti_periods:
                    try:
                        bs = datetime.strptime(b["start_date"], "%Y-%m-%d")
                        be = datetime.strptime(b["end_date"], "%Y-%m-%d")
                    except Exception:
                        continue
                    if bs <= today <= be:
                        running_bhukti = b
                        break
                dasha_block = {
                    "maha_lord": cur["lord"],
                    "maha_end": cur["end_date"],
                    "bhukti": running_bhukti,
                    "next_maha": (dashas.get("next_dasha") or {}).get("lord"),
                }
                highlights.append(
                    f"{cur['lord']} Mahadasha"
                    + (f", {running_bhukti['lord']} Bhukti" if running_bhukti else ""))
                # Bhukti change within 30 days?
                if running_bhukti:
                    try:
                        be = datetime.strptime(running_bhukti["end_date"], "%Y-%m-%d")
                        days_left = (be - today).days
                        if 0 <= days_left <= 30:
                            highlights.append(
                                f"⚠ {running_bhukti['lord']} Bhukti ends in {days_left} "
                                f"day(s) — a dasha change is near")
                    except Exception:
                        pass

            # Transit highlights: Sade-Sati, Jupiter from Moon, retrogrades, ingresses.
            transit_block = None
            if transits.get("status") == "success":
                planets = transits.get("planets", {})
                sat = planets.get("Saturn", {})
                jup = planets.get("Jupiter", {})
                if sat.get("house_from_moon") in (12, 1, 2):
                    phase = {12: "first (rising)", 1: "peak (janma)",
                             2: "final (setting)"}[sat["house_from_moon"]]
                    highlights.append(f"Saturn is in your {sat['house_from_moon']}th from "
                                      f"the Moon — Sade-Sati {phase} phase")
                if jup:
                    highlights.append(
                        f"Jupiter transits your {jup.get('house_from_moon')}th from the Moon "
                        f"({jup.get('sign_name')})")
                retro = [name for name, p in planets.items() if p.get("retrograde")]
                if retro:
                    highlights.append("Retrograde now: " + ", ".join(retro))
                transit_block = {
                    "planets": planets,
                    "upcoming": transits.get("upcoming", []),
                    "natal": transits.get("natal", {}),
                    "retrograde": retro,
                    "sade_sati": sat.get("house_from_moon") in (12, 1, 2),
                }
                for u in transits.get("upcoming", []):
                    highlights.append(
                        f"{u['planet']} enters {u['to_sign']} on {u['date']}")

            # On the lunar basis the day carries its tithi-pravesha chart.
            pravesh = None
            if basis == "lunar":
                tp = AstrologyCompute.get_lunar_pravesha(
                    "tithi", dob, tob, place, lat=lat, lon=lon, tz=tz,
                    date=date_str, ayanamsa=ayanamsa)
                if tp.get("status") == "success":
                    pravesh = tp
                    # No Muntha here: it advances one sign per YEAR of age, so it is
                    # the same value all year and says nothing about *this day*.
                    # (Same reason it is hidden on the short rungs of the TP page.)
                    highlights.append(
                        f"Tithi Pravesha lagna: {tp['lagna']['sign_name']}")
                    for yg in tp.get("tajaka_yogas", [])[:3]:
                        pair = f" ({'/'.join(yg['pair'])})" if yg.get("pair") else ""
                        highlights.append(f"Tajaka yoga — {yg['name']}{pair}")

            return {
                "status": "success",
                "date": date_str,
                "place": place,
                "basis": basis,
                "panchanga": panch if panch.get("status") == "success" else None,
                "dasha": dasha_block,
                "transits": transit_block,
                "pravesh": pravesh,
                "highlights": highlights,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    # Grahas scanned for window events. Moon is excluded (it changes sign every
    # ~2.3 days — pure noise at these horizons); Rahu/Ketu are excluded from the
    # station scan because as Mean nodes they are perpetually retrograde.
    _EVENT_PLANETS = (0, 2, 3, 4, 5, 6)      # Sun, Mars, Mercury, Jupiter, Venus, Saturn
    _STATION_PLANETS = (2, 3, 4, 5, 6)       # the Sun never retrogrades

    @staticmethod
    def _transit_events_in_window(place: str, lat: Optional[float], lon: Optional[float],
                                  tz_offset: float, start_date: str, end_jd: float) -> List[Dict]:
        """Sign-ingress and retrograde-station events falling **inside** a date
        window, across the visible grahas. Powers the fortnightly/monthly digests,
        where fast movers (Sun/Mercury/Venus/Mars) matter — unlike the daily
        digest, which only surfaces the slow Jupiter/Saturn ingresses.

        Implementation: sample each graha's sign + retrograde flag once a day
        across the window, then bisect any change to the hour. Both sampling
        primitives are cheap (`rasi_chart` ~0.04ms, `planets_in_retrograde`
        ~0.01ms), so the whole scan is bounded by the window — a few ms.

        We deliberately do NOT use `drik.next_planet_entry_date` /
        `next_planet_retrograde_change_date` here: those search *forward until they
        find the event*, which for a slow graha can mean stepping months (Saturn:
        most of a 29-year cycle). That made this function ~2.8s locally and tens of
        seconds on slower hardware — enough to time the request out at the gateway.
        Sampling also catches *several* events per graha in one window (e.g.
        Mercury stationing twice), which the "next event" helpers structurally
        cannot."""
        events: List[Dict] = []
        try:
            sy, sm, sd = map(int, start_date.split("-"))
            tplace = drik.Place(place, lat or 13.0827, lon or 80.2707, tz_offset)
            start_jd = swe.julday(sy, sm, sd, 0.0)
            if end_jd <= start_jd:
                return []

            def state(jd):
                """(sign per graha, retrograde set) at an instant."""
                cht = charts.rasi_chart(jd, tplace)
                signs = {pidx: cht[pidx + 1][1][0] for pidx in AstrologyCompute._EVENT_PLANETS}
                retro = set(drik.planets_in_retrograde(jd, tplace))
                return signs, retro

            def bisect(lo, hi, changed):
                """Narrow [lo, hi] to the instant `changed(jd)` flips. ~20 halvings
                of a 1-day bracket lands inside a minute — far finer than the day
                we report."""
                for _ in range(20):
                    mid = (lo + hi) / 2.0
                    if changed(mid):
                        hi = mid
                    else:
                        lo = mid
                return hi

            def as_date(jd):
                y, m, d, _ = utils.jd_to_gregorian(jd)
                return f"{y:04d}-{m:02d}-{d:02d}"

            # Daily samples across the window (plus the exact end). No scanned graha
            # can cross a whole 30° sign in under a day, so nothing is missed.
            steps = [start_jd + i for i in range(int(end_jd - start_jd) + 1)]
            if steps[-1] < end_jd:
                steps.append(end_jd)

            prev_jd = steps[0]
            prev_signs, prev_retro = state(prev_jd)
            for jd in steps[1:]:
                signs, retro = state(jd)

                for pidx in AstrologyCompute._EVENT_PLANETS:
                    # ── Sign ingress ──
                    if signs[pidx] != prev_signs[pidx]:
                        to_rasi = signs[pidx]
                        exact = bisect(
                            prev_jd, jd,
                            lambda t, p=pidx, s=prev_signs[pidx]:
                                charts.rasi_chart(t, tplace)[p + 1][1][0] != s)
                        events.append({
                            "date": as_date(exact),
                            "planet": PLANET_NAMES[pidx], "type": "ingress",
                            "text": f"{PLANET_NAMES[pidx]} enters {ZODIAC_NAMES[to_rasi]}",
                        })

                    # ── Retrograde station ──
                    if pidx in AstrologyCompute._STATION_PLANETS:
                        was, now = pidx in prev_retro, pidx in retro
                        if was != now:
                            exact = bisect(
                                prev_jd, jd,
                                lambda t, p=pidx, w=was:
                                    (p in drik.planets_in_retrograde(t, tplace)) != w)
                            events.append({
                                "date": as_date(exact),
                                "planet": PLANET_NAMES[pidx], "type": "station",
                                "text": f"{PLANET_NAMES[pidx]} turns "
                                        f"{'retrograde' if now else 'direct'}",
                            })

                prev_jd, prev_signs, prev_retro = jd, signs, retro
        except Exception as e:
            print(f"[digest] window-event scan failed: {e}")
        events.sort(key=lambda x: x["date"])
        return events

    @staticmethod
    def _period_digest(period: str, dob: str, tob: str, place: str,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None, date: Optional[str] = None,
                       basis: str = "solar",
                       ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Shared builder for the fortnightly and monthly readings — a
        longer-horizon cousin of :meth:`get_daily_digest`. Blends the running
        Vimsottari dasha/bhukti with the transit events (ingresses + retrograde
        stations) landing inside the window, plus the window's opening Panchanga,
        and anchors the whole reading to a **progressed (pravesha) chart**.

        Which chart — and therefore which window — depends on `basis`:

          * ``period="fortnight"`` → always the **Paksha Pravesha** (the running
            Shukla/Krishna fortnight, ~14.8d). The solar ladder has no fortnight
            rung, so this rung is lunar by definition.
          * ``period="month"``, ``basis="solar"`` → **Maasa Pravesha** (Tajaka
            monthly solar return, ~30.4d).
          * ``period="month"``, ``basis="lunar"`` → the **birth-tithi return**
            (lunar month, ~29.5d).
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            tz_offset = tz if tz is not None else 5.5
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            today_str = date or f"{local_now.year:04d}-{local_now.month:02d}-{local_now.day:02d}"

            # The **scan window** (events + header dates) is the pravesha window the
            # day falls in; the **snapshot** (live positions/dasha) stays anchored to
            # today. The fortnight rung is lunar-only — there is no solar fortnight.
            if period == "fortnight":
                basis = "lunar"
            pravesh = None

            if period == "fortnight":
                pravesh = AstrologyCompute.get_lunar_pravesha(
                    "paksha", dob, tob, place, lat=lat, lon=lon, tz=tz,
                    date=today_str, ayanamsa=ayanamsa)
            elif basis == "lunar":
                pravesh = AstrologyCompute.get_lunar_pravesha(
                    "month", dob, tob, place, lat=lat, lon=lon, tz=tz,
                    date=today_str, ayanamsa=ayanamsa)
            else:
                pravesh = AstrologyCompute.get_masa_pravesh(
                    dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                    date=today_str, ayanamsa=ayanamsa)

            if pravesh and pravesh.get("status") == "success":
                start_str = pravesh["window"]["start"]
                end_str = pravesh["window"]["end"]
            else:
                # Pravesha failed — fall back to a plain forward window so the
                # reading still renders (transits + dasha remain valid).
                pravesh = None
                start_str = today_str
                _sy, _sm, _sd = map(int, start_str.split("-"))
                _fallback = 14 if period == "fortnight" else 30
                ey, em, ed, _ = utils.jd_to_gregorian(
                    swe.julday(_sy, _sm, _sd, 12.0) + _fallback)
                end_str = f"{ey:04d}-{em:02d}-{ed:02d}"

            sy, sm, sd = map(int, start_str.split("-"))
            start_jd = swe.julday(sy, sm, sd, 12.0)
            ey, em, ed = map(int, end_str.split("-"))
            end_jd = swe.julday(ey, em, ed, 12.0)
            span_days = int(round(end_jd - start_jd))

            # Live snapshot is anchored to today; Panchanga to the window's opening.
            panch = AstrologyCompute.get_panchanga(
                date=start_str, place=place, lat=lat, lon=lon, tz=tz_offset)
            transits = AstrologyCompute.get_transits(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                current_date=today_str, ayanamsa=ayanamsa)
            dashas = AstrologyCompute.get_dashas(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz)
            events = AstrologyCompute._transit_events_in_window(
                place, lat, lon, tz_offset, start_str, end_jd)

            # What the window is *called* — this is what the reading leads with.
            if period == "fortnight":
                when = f"{(pravesh or {}).get('paksha') or 'lunar'} Paksha (fortnight)"
            elif basis == "lunar":
                when = "lunar month (birth-tithi return)"
            else:
                when = "solar month (Maasa Pravesha)"
            highlights: List[str] = [
                f"Your {when}: {start_str} → {end_str} ({span_days} days)"]

            # Panchanga headline at the window's opening.
            if panch.get("status") == "success":
                verb = "Opened on"
                highlights.append(
                    f"{verb} {panch['vaara']['name']} · {panch['tithi']['name']}, "
                    f"{panch['nakshatra']['name']} nakshatra")

            # Dasha snapshot + any change inside the window.
            dasha_block = None
            if dashas.get("status") != "failed" and dashas.get("current_dasha"):
                cur = dashas["current_dasha"]
                bhukti_periods = (dashas.get("current_bhukthi") or {}).get("periods", [])
                today = datetime.strptime(today_str, "%Y-%m-%d")
                running_bhukti = None
                for b in bhukti_periods:
                    try:
                        bs = datetime.strptime(b["start_date"], "%Y-%m-%d")
                        be = datetime.strptime(b["end_date"], "%Y-%m-%d")
                    except Exception:
                        continue
                    if bs <= today <= be:
                        running_bhukti = b
                        break
                dasha_block = {
                    "maha_lord": cur["lord"],
                    "maha_end": cur["end_date"],
                    "bhukti": running_bhukti,
                    "next_maha": (dashas.get("next_dasha") or {}).get("lord"),
                }
                highlights.append(
                    f"{cur['lord']} Mahadasha"
                    + (f", {running_bhukti['lord']} Bhukti" if running_bhukti else ""))
                if running_bhukti:
                    try:
                        be = datetime.strptime(running_bhukti["end_date"], "%Y-%m-%d")
                        days_left = (be - today).days
                        days_to_end = (datetime.strptime(end_str, "%Y-%m-%d") - today).days
                        if 0 <= days_left <= max(0, days_to_end):
                            period_noun = "fortnight" if period == "fortnight" else "month"
                            highlights.append(
                                f"⚠ {running_bhukti['lord']} Bhukti ends {running_bhukti['end_date']} "
                                f"— a dasha change falls within this {period_noun}")
                    except Exception:
                        pass

            # Transit snapshot (positions/retro now) + all window events.
            transit_block = None
            if transits.get("status") == "success":
                planets = transits.get("planets", {})
                sat = planets.get("Saturn", {})
                jup = planets.get("Jupiter", {})
                if sat.get("house_from_moon") in (12, 1, 2):
                    phase = {12: "first (rising)", 1: "peak (janma)",
                             2: "final (setting)"}[sat["house_from_moon"]]
                    highlights.append(f"Saturn in your {sat['house_from_moon']}th from the "
                                      f"Moon — Sade-Sati {phase} phase")
                if jup:
                    highlights.append(
                        f"Jupiter transits your {jup.get('house_from_moon')}th from the Moon "
                        f"({jup.get('sign_name')})")
                retro = [name for name, p in planets.items() if p.get("retrograde")]
                if retro:
                    highlights.append("Retrograde now: " + ", ".join(retro))
                transit_block = {
                    "planets": planets,
                    "natal": transits.get("natal", {}),
                    "retrograde": retro,
                    "sade_sati": sat.get("house_from_moon") in (12, 1, 2),
                }
            for ev in events:
                highlights.append(f"{ev['text']} on {ev['date']}")

            # Progressed-chart headline, named for the rung it was actually cast on.
            if pravesh:
                if period == "fortnight":
                    chart_name = f"{pravesh.get('paksha', 'Paksha')} Paksha Pravesha"
                elif basis == "lunar":
                    chart_name = "Lunar-month (birth-tithi return)"
                else:
                    chart_name = "Maasa Pravesha"
                # No Muntha: it advances one sign per YEAR of age, so it is identical
                # for every fortnight and every month of a given year — a constant
                # dressed up as news. Hidden on the TP page's short rungs for the
                # same reason.
                highlights.append(
                    f"{chart_name} lagna: {pravesh['lagna']['sign_name']}")
                for yg in pravesh.get("tajaka_yogas", [])[:3]:
                    pair = f" ({'/'.join(yg['pair'])})" if yg.get("pair") else ""
                    highlights.append(f"Tajaka yoga — {yg['name']}{pair}")

            return {
                "status": "success",
                "period": period,
                "basis": basis,
                "window_label": when,
                "start_date": start_str,
                "end_date": end_str,
                "span_days": span_days,
                "place": place,
                "panchanga": panch if panch.get("status") == "success" else None,
                "dasha": dasha_block,
                "transits": transit_block,
                "events": events,
                "pravesh": pravesh,
                "highlights": highlights,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_fortnightly_digest(dob: str, tob: str, place: str,
                               lat: Optional[float] = None, lon: Optional[float] = None,
                               tz: Optional[float] = None, date: Optional[str] = None,
                               basis: str = "lunar",
                               ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A personalized "This Fortnight" reading: dasha context + the transit
        events across the running **paksha** (Shukla or Krishna, ~14.8 days),
        anchored to that paksha's Pravesha chart. The fortnight is a lunar-only
        rung — Tajaka's solar ladder has no fortnight — so `basis` is ignored."""
        return AstrologyCompute._period_digest(
            "fortnight", dob, tob, place, lat=lat, lon=lon, tz=tz, date=date,
            basis="lunar", ayanamsa=ayanamsa)

    @staticmethod
    def get_monthly_digest(dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None, date: Optional[str] = None,
                           basis: str = "solar",
                           ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A personalized "This Month" reading: dasha context + the month's transit
        events, anchored to a progressed monthly chart. `basis="solar"` uses the
        **Maasa Pravesha** (Tajaka monthly solar return, ~30.4d); `basis="lunar"`
        uses the **birth-tithi return** (lunar month, ~29.5d). The chosen window
        defines the reading's start/end."""
        return AstrologyCompute._period_digest(
            "month", dob, tob, place, lat=lat, lon=lon, tz=tz, date=date,
            basis=basis, ayanamsa=ayanamsa)

    # ── Nadi / Bhrigu-style yearly markers ─────────────────────────────────
    @staticmethod
    def get_bhrigu_markers(dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None, from_age: Optional[int] = None,
                           years: int = 12,
                           ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Bhrigu / Nadi-style yearly markers for a birth chart.

        Two grounded, clearly-labelled classical devices:
          1. **Annual progression** — the Nadi one-sign-per-year progression from
             the natal Moon: age 0 = the Moon's sign, and each year the "marker
             sign" advances by one rasi. The natal planets sitting in that sign
             (and its lord) are what the year is said to activate.
          2. **Bhrigu Bindu activation** — the natal Bhrigu Bindu (the Rahu–Moon
             midpoint, a Nadi sensitive point). The next transits of Jupiter and
             Saturn into the Bhrigu Bindu sign and the Moon sign are the concrete
             "trigger" dates for the milestone years.

        This is a traditional predictive aid, not a deterministic forecast."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            _set_ayanamsa(ayanamsa)

            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            jd = swe.julday(year, month, day, hour + minute / 60.0)

            pp = charts.rasi_chart(jd, place_obj)
            # planet index -> 0-based rasi (skip lagna at index 0).
            planet_sign = {}
            for pidx, (rasi, _deg) in pp[1:]:
                planet_sign[pidx] = rasi
            moon_rasi0 = planet_sign.get(1, 0)  # 1 = Moon

            # Natal Bhrigu Bindu (Rahu-Moon midpoint), D1.
            bb = drik.bhrigu_bindhu_lagna(jd, place_obj)  # [sign0, deg]
            bb_sign0 = int(bb[0]) % 12
            bb_deg = round(float(bb[1]), 2)
            # House of the Bhrigu Bindu from the Lagna (1-based).
            lagna_rasi0 = pp[0][1][0]
            bb_house = ((bb_sign0 - lagna_rasi0) % 12) + 1

            # Sign -> natal planets in it (names), for annotating progressed years.
            signs_planets = {s: [] for s in range(12)}
            for pidx, rasi in planet_sign.items():
                signs_planets[rasi].append(PLANET_NAMES.get(pidx, str(pidx)))

            # Current age (integer years since birth).
            today = datetime.now()
            age_now = today.year - year - ((today.month, today.day) < (month, day))
            if from_age is None:
                from_age = max(0, age_now)
            years = max(1, min(int(years or 12), 40))

            # ── Annual progression table ───────────────────────────────────
            progression = []
            for a in range(from_age, from_age + years):
                sign0 = (moon_rasi0 + a) % 12
                planets_here = signs_planets.get(sign0, [])
                progression.append({
                    "age": a,
                    "year": year + a,
                    "sign_name": ZODIAC_NAMES[sign0],
                    "sign_lord": RASI_LORDS[sign0],
                    "planets": planets_here,
                    "is_bhrigu_bindu": sign0 == bb_sign0,
                    "is_moon_sign": sign0 == moon_rasi0,
                })

            # ── Bhrigu Bindu / Moon activations (Jupiter + Saturn ingresses) ─
            # NB: the engine's next_planet_entry_date micro-steps 0.01 day at a
            # time, so finding Saturn's *next* entry into a sign it just left can
            # take ~29 years of stepping (10-15 s per call). We instead coarse-scan
            # (1-day steps — safe for slow grahas, they move <0.25°/day) then
            # bisect to the hour, capped at one Saturn cycle (~36 yr).
            def _next_sign_entry(pl_idx, jd_start, tgt_sign0, max_years=36):
                pl = drik.ephemeris_planet_index(pl_idx)

                def sign_at(j):
                    return int(drik.sidereal_longitude(j - tz_offset / 24.0, pl) // 30) % 12

                jd0 = jd_start
                prev = sign_at(jd0)
                limit = jd_start + max_years * 365.25
                while jd0 < limit:
                    jd1 = jd0 + 1.0
                    s = sign_at(jd1)
                    if s == tgt_sign0 and prev != tgt_sign0:
                        lo, hi = jd0, jd1  # entry is inside (jd0, jd1]
                        for _ in range(40):
                            mid = (lo + hi) / 2.0
                            if sign_at(mid) == tgt_sign0:
                                hi = mid
                            else:
                                lo = mid
                            if hi - lo < 1.0 / 24.0:
                                break
                        return hi
                    prev = s
                    jd0 = jd1
                return None

            activations = []
            jd_now = swe.julday(today.year, today.month, today.day, 12)
            for pl_idx, pl_name in ((4, "Jupiter"), (6, "Saturn")):
                for tgt_sign0, tgt_label in ((bb_sign0, "Bhrigu Bindu"),
                                             (moon_rasi0, "Moon")):
                    try:
                        ejd = _next_sign_entry(pl_idx, jd_now, tgt_sign0)
                        if ejd is None:
                            continue
                        g = utils.jd_to_gregorian(ejd)
                        activations.append({
                            "planet": pl_name,
                            "target": tgt_label,
                            "sign_name": ZODIAC_NAMES[tgt_sign0],
                            "date": f"{g[0]:04d}-{g[1]:02d}-{g[2]:02d}",
                        })
                    except Exception:
                        pass
            activations.sort(key=lambda x: x["date"])

            return {
                "status": "success",
                "dob": dob,
                "age_now": age_now,
                "moon_sign": ZODIAC_NAMES[moon_rasi0],
                "bhrigu_bindu": {
                    "sign_name": ZODIAC_NAMES[bb_sign0],
                    "degrees": bb_deg,
                    "house_from_lagna": bb_house,
                    "sign_lord": RASI_LORDS[bb_sign0],
                },
                "from_age": from_age,
                "years": years,
                "progression": progression,
                "activations": activations,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # ── Remedies (traditional guidance from dignity + shadbala) ─────────────
    @staticmethod
    def get_remedies(dob: str, tob: str, place: str,
                     lat: Optional[float] = None, lon: Optional[float] = None,
                     tz: Optional[float] = None,
                     ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Classical remedial suggestions per weak / afflicted planet.

        A planet is flagged when it is **debilitated**, **shadbala-deficient**
        (six-fold strength ratio < 1.0), or sits in a **dusthana** (6th/8th/12th
        from the Lagna). For each flagged graha the curated traditional remedy
        (gemstone, beeja mantra, presiding deity, weekday, charity, colour) is
        returned. This is traditional guidance drawn from the chart's own dignity
        and strength — NOT medical, legal or financial advice, and gemstones in
        particular should be taken up only after qualified consultation."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
            lagna_rasi0 = pp[0][1][0]
            planet_sign = {pidx: rasi for pidx, (rasi, _d) in pp[1:]}

            # Shadbala ratio per planet (Sun..Saturn); Rahu/Ketu have no shadbala.
            ratios = {}
            sb = AstrologyCompute.get_shadbala(dob, tob, place, lat, lon, tz, ayanamsa=ayanamsa)
            if sb.get("status") == "success":
                for row in sb.get("planets", []):
                    ratios[row["planet"]] = row.get("strength_ratio")

            def _dignity(name, sign0):
                if name in EXALTATION_SIGN:
                    if sign0 == EXALTATION_SIGN[name]:
                        return "exalted"
                    if sign0 == (EXALTATION_SIGN[name] + 6) % 12:
                        return "debilitated"
                if sign0 in OWN_SIGNS.get(name, set()):
                    return "own"
                return "neutral"

            DUSTHANAS = {6, 8, 12}
            all_planets = []
            remedies = []
            # Assess the seven grahas + Rahu/Ketu (0..8).
            for pidx in range(9):
                name = PLANET_NAMES.get(pidx, str(pidx))
                if pidx not in planet_sign:
                    continue
                sign0 = planet_sign[pidx]
                dignity = _dignity(name, sign0)
                house = ((sign0 - lagna_rasi0) % 12) + 1
                ratio = ratios.get(name)
                reasons = []
                if dignity == "debilitated":
                    reasons.append("debilitated (fallen dignity)")
                if ratio is not None and ratio < 1.0:
                    reasons.append(f"shadbala-deficient (strength {ratio:.2f} < required)")
                if house in DUSTHANAS:
                    reasons.append(f"in a dusthana (house {house} from Lagna)")
                entry = {
                    "planet": name,
                    "sign_name": ZODIAC_NAMES[sign0],
                    "house": house,
                    "dignity": dignity,
                    "strength_ratio": ratio,
                    "weak": bool(reasons),
                    "reasons": reasons,
                }
                all_planets.append(entry)
                if reasons and name in REMEDIES_TABLE:
                    rem = dict(REMEDIES_TABLE[name])
                    rem["planet"] = name
                    rem["reason"] = "; ".join(reasons)
                    rem["dignity"] = dignity
                    rem["house"] = house
                    remedies.append(rem)

            return {
                "status": "success",
                "remedies": remedies,
                "planets": all_planets,
                "weak_count": len(remedies),
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # Gandanta ("knot") — the water→fire sign junctions: the last 3°20' of the
    # water signs (Cancer/Scorpio/Pisces) and the first 3°20' of the fire signs
    # that follow them (Leo/Sagittarius/Aries).
    _GANDANTA_WATER = {3, 7, 11}
    _GANDANTA_FIRE = {0, 4, 8}
    _GANDANTA_ARC = 3 + 20 / 60.0
    # Each flag's tone drives the UI colour + the AI framing.
    _CONDITION_TONES = {
        "combust": "challenging", "mrityu_bhaga": "challenging",
        "marana_karaka": "challenging", "gandanta": "challenging",
        "graha_yuddha": "challenging", "vargottama": "benefic",
        "pushkara_navamsa": "benefic", "pushkara_bhaga": "benefic",
        "retrograde": "neutral",
    }
    _CONDITION_LABELS = {
        "combust": "Combust (Asta)",
        "vargottama": "Vargottama",
        "pushkara_navamsa": "Pushkara Navamsa",
        "pushkara_bhaga": "Pushkara Bhaga",
        "mrityu_bhaga": "Mrityu Bhaga",
        "marana_karaka": "Marana Karaka Sthana",
        "gandanta": "Gandanta",
        "graha_yuddha": "Graha Yuddha (planetary war)",
        "retrograde": "Retrograde (Vakri)",
    }

    @staticmethod
    def get_planet_conditions(dob: str, tob: str, place: str,
                              lat: Optional[float] = None, lon: Optional[float] = None,
                              tz: Optional[float] = None,
                              ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Classical point-conditions ("flags") that colour a planet's reading but
        are invisible on the plain Kundali:

          • **Combust (Asta)** — too close to the Sun (engine `planets_in_combustion`).
          • **Vargottama** — same sign in D1 and D9 (a strengthening dignity).
          • **Pushkara Navamsa / Bhaga** — the auspicious nourishing degrees.
          • **Mrityu Bhaga** — the classical "fatal" degrees (engine table).
          • **Marana Karaka Sthana** — a planet in its death-like house.
          • **Gandanta** — sitting on a water→fire junction (a karmic knot).
          • **Graha Yuddha** — a planetary war (two tara-grahas within 1°).
          • **Retrograde (Vakri)** — moving backward.

        All engine-grounded; each flag carries a tone (benefic/challenging/neutral)
        for the UI and the AI framing."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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

            d1 = charts.rasi_chart(jd, place_obj)
            d9 = charts.divisional_chart(jd, place_obj, divisional_chart_factor=9)
            lagna_rasi0 = d1[0][1][0]

            # ── Engine-computed condition sets ──────────────────────────────
            combust = set(charts.planets_in_combustion(d1))
            pna, pb = charts.planets_in_pushkara_navamsa_bhaga(d1)
            pna, pb = set(pna), set(pb)
            retro = set(drik.planets_in_retrograde(jd, place_obj))
            d9_sign = {p: d9[i][1][0] for i, (p, _v) in enumerate(d9[1:], start=1)
                       if isinstance(p, int)}
            # Mrityu bhaga (needs a Date + (h,m,s) tuple, and returns planet
            # index OR 'Md'/'L'); keep only the nine grahas.
            mrityu = set()
            try:
                mb = charts.planets_in_mrityu_bhaga(
                    drik.Date(year, month, day), (hour, minute, second), place_obj, d1)
                mrityu = {x[0] for x in mb if isinstance(x[0], int)}
            except Exception:
                pass
            mks = {p for p, _h in charts.get_planets_in_marana_karaka_sthana(d1)}

            # ── Graha Yuddha — tara-grahas sharing a sign within 1° ─────────
            yuddha = {}   # planet idx -> (partner name, separation°)
            taras = [(p, d1[p + 1][1][0], d1[p + 1][1][1]) for p in (2, 3, 4, 5, 6)]
            for a in range(len(taras)):
                for b in range(a + 1, len(taras)):
                    pa, sa, la = taras[a]; pb2, sb, lb = taras[b]
                    if sa == sb and abs(la - lb) <= 1.0:
                        sep = round(abs(la - lb), 2)
                        yuddha[pa] = (PLANET_NAMES[pb2], sep)
                        yuddha[pb2] = (PLANET_NAMES[pa], sep)

            planets = []
            counts = {"benefic": 0, "challenging": 0, "neutral": 0}
            for pidx in range(9):  # Sun..Ketu
                sign0, deg = d1[pidx + 1][1]
                flags = []

                def add(code, extra=None):
                    tone = AstrologyCompute._CONDITION_TONES[code]
                    f = {"code": code,
                         "label": AstrologyCompute._CONDITION_LABELS[code],
                         "tone": tone}
                    if extra:
                        f.update(extra)
                    flags.append(f)
                    counts[tone] += 1

                if pidx in combust:
                    add("combust")
                if pidx in d9_sign and d9_sign[pidx] == sign0:
                    add("vargottama")
                if pidx in pna:
                    add("pushkara_navamsa")
                if pidx in pb:
                    add("pushkara_bhaga")
                if pidx in mrityu:
                    add("mrityu_bhaga")
                if pidx in mks:
                    add("marana_karaka")
                if ((sign0 in AstrologyCompute._GANDANTA_WATER
                     and deg >= 30 - AstrologyCompute._GANDANTA_ARC)
                        or (sign0 in AstrologyCompute._GANDANTA_FIRE
                            and deg < AstrologyCompute._GANDANTA_ARC)):
                    add("gandanta")
                if pidx in yuddha:
                    partner, sep = yuddha[pidx]
                    add("graha_yuddha", {"partner": partner, "separation": sep})
                # Only the five tara-grahas: Rahu/Ketu are Mean nodes and thus
                # perpetually retrograde (noise), the luminaries never retrograde.
                if pidx in (2, 3, 4, 5, 6) and pidx in retro:
                    add("retrograde")

                planets.append({
                    "planet": PLANET_NAMES.get(pidx, str(pidx)),
                    "sign_name": ZODIAC_NAMES[sign0],
                    "degrees": round(deg, 2),
                    "house": ((sign0 - lagna_rasi0) % 12) + 1,
                    "flags": flags,
                })

            flagged = [p for p in planets if p["flags"]]
            return {
                "status": "success",
                "planets": planets,
                "flagged": flagged,
                "counts": counts,
                "flagged_count": len(flagged),
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # ── Avasthas (planetary states) — engine has none, so computed here ──────
    # Sign lord (planet index) per rasi 0..11.
    _RASI_LORD_IDX = [2, 5, 3, 1, 0, 3, 5, 2, 4, 6, 6, 4]
    # Baladi (5 states by degree; strongest = Yuva). Each 6° of the sign.
    _BALADI_STATES = ["Bala", "Kumara", "Yuva", "Vriddha", "Mrita"]
    _BALADI_INFO = {
        "Bala": ("infant", "quarter strength"),
        "Kumara": ("adolescent", "half strength"),
        "Yuva": ("youth / prime", "full strength"),
        "Vriddha": ("old", "little strength"),
        "Mrita": ("dead", "no strength"),
    }
    _JAGRADADI_INFO = {
        "Jagrat": ("awake", "gives full results"),
        "Swapna": ("dreaming", "gives moderate results"),
        "Sushupti": ("sleeping", "gives weak results"),
    }
    _DEEPTADI_INFO = {
        "Deepta": ("radiant", "exalted — very strong", "benefic"),
        "Swastha": ("healthy", "own sign — strong", "benefic"),
        "Mudita": ("delighted", "friend's sign — comfortable", "benefic"),
        "Shanta": ("peaceful", "neutral sign — settled", "neutral"),
        "Deena": ("miserable", "enemy's sign — uneasy", "challenging"),
        "Dukhita": ("distressed", "debilitated — struggling", "challenging"),
        "Vikala": ("crippled", "combust — burnt by the Sun", "challenging"),
        "Khala": ("mischievous", "with a malefic — agitated", "challenging"),
        "Kopa": ("agitated", "in a planetary war — disturbed", "challenging"),
    }

    @staticmethod
    def get_avasthas(dob: str, tob: str, place: str,
                     lat: Optional[float] = None, lon: Optional[float] = None,
                     tz: Optional[float] = None,
                     ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """The classical **avasthas** (planetary states) for the seven grahas —
        desktop JHora shows these but the engine has no function for them, so they
        are computed here from longitude + dignity (like the Mangal-dosha and
        gandanta logic):

          • **Baladi** (5) — infant→dead by degree-in-sign (reversed in even signs);
            Yuva (prime) is strongest, Mrita (dead) gives nothing.
          • **Jagradadi** (3) — awake / dreaming / sleeping, by dignity (own-exalt /
            friend-neutral / enemy-debilitated).
          • **Deeptadi** (9) — a fuller dignity-and-affliction state (radiant …
            agitated); the affliction states (combust→Vikala, in war→Kopa, with a
            malefic→Khala) override the dignity base.

        A simplified but faithful classical mapping; the AI reading treats it as a
        strength nuance, not a verdict."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from jhora import const as _const
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0 + second / 3600.0)

            d1 = charts.rasi_chart(jd, place_obj)
            planet_sign = {p: d1[p + 1][1][0] for p in range(9)}
            combust = set(charts.planets_in_combustion(d1))
            # Malefic co-tenants (same sign) for Khala; nodes + Mars + Saturn.
            malefics = (2, 6, 7, 8)
            malefic_signs = {planet_sign[m] for m in malefics}
            # Graha yuddha (tara-grahas sharing a sign within 1°) for Kopa.
            yuddha = set()
            taras = [(p, d1[p + 1][1][0], d1[p + 1][1][1]) for p in (2, 3, 4, 5, 6)]
            for a in range(len(taras)):
                for b in range(a + 1, len(taras)):
                    if taras[a][1] == taras[b][1] and abs(taras[a][2] - taras[b][2]) <= 1.0:
                        yuddha.add(taras[a][0]); yuddha.add(taras[b][0])

            def dignity(name, p, sign0):
                if name in EXALTATION_SIGN:
                    if sign0 == EXALTATION_SIGN[name]:
                        return "exalted"
                    if sign0 == (EXALTATION_SIGN[name] + 6) % 12:
                        return "debilitated"
                lord = AstrologyCompute._RASI_LORD_IDX[sign0]
                if lord == p:
                    return "own"
                rel = _const.planet_relations[p][lord]
                return {3: "friend", 2: "neutral", 1: "enemy"}.get(rel, "neutral")

            planets = []
            for p in range(7):  # Sun..Saturn (avasthas are for the seven grahas)
                name = PLANET_NAMES[p]
                sign0, deg = d1[p + 1][1]

                # Baladi — 6° parts, reversed in even (2nd/4th/… ) signs.
                part = min(int(deg // 6), 4)
                odd_sign = (sign0 % 2 == 0)  # Aries(0) is the 1st = odd sign
                baladi = (AstrologyCompute._BALADI_STATES[part] if odd_sign
                          else AstrologyCompute._BALADI_STATES[4 - part])

                dig = dignity(name, p, sign0)

                # Jagradadi from dignity.
                if dig in ("exalted", "own"):
                    jagradadi = "Jagrat"
                elif dig in ("friend", "neutral"):
                    jagradadi = "Swapna"
                else:  # enemy / debilitated
                    jagradadi = "Sushupti"

                # Deeptadi — dignity base, overridden by affliction.
                base = {"exalted": "Deepta", "own": "Swastha", "friend": "Mudita",
                        "neutral": "Shanta", "enemy": "Deena",
                        "debilitated": "Dukhita"}[dig]
                if p in combust:
                    deeptadi = "Vikala"
                elif p in yuddha:
                    deeptadi = "Kopa"
                elif any(sign0 == ms and p not in malefics for ms in [planet_sign[m] for m in malefics]):
                    deeptadi = "Khala"
                else:
                    deeptadi = base

                bl_state, bl_str = AstrologyCompute._BALADI_INFO[baladi]
                jg_state, jg_eff = AstrologyCompute._JAGRADADI_INFO[jagradadi]
                dp_state, dp_desc, dp_tone = AstrologyCompute._DEEPTADI_INFO[deeptadi]
                planets.append({
                    "planet": name,
                    "sign_name": ZODIAC_NAMES[sign0],
                    "degrees": round(deg, 2),
                    "dignity": dig,
                    "baladi": {"state": baladi, "meaning": bl_state, "strength": bl_str},
                    "jagradadi": {"state": jagradadi, "meaning": jg_state, "effect": jg_eff},
                    "deeptadi": {"state": deeptadi, "meaning": dp_state,
                                 "description": dp_desc, "tone": dp_tone},
                })

            return {"status": "success", "planets": planets}
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # Compound-relationship code (engine) → (label, tone).
    _COMPOUND_REL = {
        4: ("Adhimitra", "benefic"),   # great friend
        3: ("Mitra", "benefic"),       # friend
        2: ("Sama", "neutral"),        # neutral
        1: ("Shatru", "challenging"),  # enemy
        0: ("Adhishatru", "challenging"),  # great enemy
    }

    @staticmethod
    def get_friendships(dob: str, tob: str, place: str,
                        lat: Optional[float] = None, lon: Optional[float] = None,
                        tz: Optional[float] = None,
                        ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Planetary relationships **in this chart** (compound = natural + temporal):

          • the 7×7 **compound-friendship matrix** (Adhimitra → Adhishatru),
          • the **house-lord placement** table (the lord of each bhava and the house
            it actually occupies), and
          • **Parivartana** (mutual sign exchange) between planets.

        Nothing in the UI showed who is whose friend once temporal placement is
        folded in; this surfaces it and feeds the AI's dignity reasoning."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from jhora.horoscope.chart import house as _house
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)
            jd = swe.julday(year, month, day, hour + minute / 60.0)

            pp = charts.rasi_chart(jd, place_obj)
            lagna_rasi0 = pp[0][1][0]
            planet_sign = {pidx: rasi for pidx, (rasi, _d) in pp[1:]}
            h2p = utils.get_house_planet_list_from_planet_positions(pp)

            # ── Compound-friendship matrix (7 grahas) ───────────────────────
            comp = _house._get_compound_relationships_of_planets(h2p)
            matrix = []
            for p in range(7):
                rels = []
                for q in range(7):
                    if p == q:
                        rels.append({"to": PLANET_NAMES[q], "self": True})
                        continue
                    label, tone = AstrologyCompute._COMPOUND_REL.get(
                        comp[p][q], ("Sama", "neutral"))
                    rels.append({"to": PLANET_NAMES[q], "label": label, "tone": tone})
                matrix.append({"planet": PLANET_NAMES[p], "relations": rels})

            # ── House-lord placement ────────────────────────────────────────
            RASI_LORD_IDX = AstrologyCompute._RASI_LORD_IDX
            house_lords = []
            for h in range(1, 13):
                sign0 = (lagna_rasi0 + h - 1) % 12
                lord = RASI_LORD_IDX[sign0]
                lord_sign = planet_sign.get(lord)
                lord_house = ((lord_sign - lagna_rasi0) % 12) + 1 if lord_sign is not None else None
                house_lords.append({
                    "house": h,
                    "house_sign": ZODIAC_NAMES[sign0],
                    "signification": AstrologyCompute._BHAVA_SIGNIFICATION[h - 1],
                    "lord": PLANET_NAMES[lord],
                    "lord_house": lord_house,
                    "lord_sign": ZODIAC_NAMES[lord_sign] if lord_sign is not None else None,
                    "lord_house_signification": (
                        AstrologyCompute._BHAVA_SIGNIFICATION[lord_house - 1]
                        if lord_house else None),
                })

            # ── Parivartana (mutual sign exchange) among the 7 grahas ───────
            parivartana = []
            for a in range(7):
                for b in range(a + 1, 7):
                    sa, sb = planet_sign.get(a), planet_sign.get(b)
                    if sa is None or sb is None:
                        continue
                    if RASI_LORD_IDX[sa] == b and RASI_LORD_IDX[sb] == a:
                        parivartana.append({
                            "planets": [PLANET_NAMES[a], PLANET_NAMES[b]],
                            "signs": [ZODIAC_NAMES[sa], ZODIAC_NAMES[sb]],
                            "houses": [((sa - lagna_rasi0) % 12) + 1,
                                       ((sb - lagna_rasi0) % 12) + 1],
                        })

            return {
                "status": "success",
                "planets": [PLANET_NAMES[p] for p in range(7)],
                "matrix": matrix,
                "house_lords": house_lords,
                "parivartana": parivartana,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # The BPHS conditional nakshatra dashas the engine can test for applicability,
    # mapped to (display name, when-it-applies blurb, DhasaPage picker key or None).
    _APPLICABLE_DASHA_INFO = {
        "ashtottari": ("Ashtottari",
                       "108-year cycle; classically applies when Rahu is in a "
                       "quadrant/trine from a night-birth Lagna lord (and similar).",
                       "ashtottari"),
        "chaturaaseeti_sama": ("Chaturaaseeti Sama",
                               "84-year cycle; applies when the 10th lord is in the 10th house.",
                               None),
        "dwadasottari": ("Dwadasottari",
                         "112-year cycle; applies from a Lagna in Venus's hora (D9-based).",
                         "dwadasottari"),
        "dwisatpathi": ("Dwisatpathi",
                        "112-year cycle; applies when the Lagna is in its own or the 7th nakshatra pada.",
                        None),
        "panchottari": ("Panchottari",
                        "105-year cycle; applies from a Cancer Lagna condition (D12-based).",
                        "panchottari"),
        "satabdika": ("Shatabdika",
                      "100-year cycle; applies when the Lagna is in Vargottama at a specific pada.",
                      "shatabdika"),
        "shashtisama": ("Shashtihayani (Shashti-sama)",
                        "60-year cycle; applies when the Sun is in the Lagna.",
                        None),
    }

    @staticmethod
    def get_applicable_dashas(dob: str, tob: str, place: str,
                              lat: Optional[float] = None, lon: Optional[float] = None,
                              tz: Optional[float] = None,
                              ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Which **conditional** Vimsottari-family dashas classically apply to this
        chart (BPHS applicability rules), via the engine's `applicability_check`.

        Vimsottari always applies and is the default; this surfaces the extra
        nakshatra dashas tradition would *also* read for this specific nativity, so
        the Dhasa page can recommend (and deep-link) them."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from jhora.horoscope.dhasa.graha import applicability
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            place_obj = drik.Place(place, lat, lon, tz or 5.5)

            keys = applicability.applicability_check(
                drik.Date(year, month, day), (hour, minute, second), place_obj) or []

            applicable = []
            for k in keys:
                info = AstrologyCompute._APPLICABLE_DASHA_INFO.get(k)
                if not info:
                    applicable.append({"key": k, "name": k.replace("_", " ").title(),
                                       "description": "", "picker_key": None})
                    continue
                name, blurb, picker = info
                applicable.append({"key": k, "name": name, "description": blurb,
                                   "picker_key": picker})
            return {
                "status": "success",
                "applicable": applicable,
                "count": len(applicable),
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_eclipses(place: str = "", lat: Optional[float] = None,
                     lon: Optional[float] = None, tz: Optional[float] = None,
                     from_date: Optional[str] = None, count: int = 3) -> Dict:
        """Upcoming solar and lunar eclipses from a date. Returns the next
        `count` of each (global visibility), with the eclipse type and the key
        instants (begin / maximum / end) in the place's local time. Solar and
        lunar are searched independently, each stepping past the previous
        maximum. `from_date` defaults to today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

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

            # Jyotir AI's drik functions take a *local* JD and subtract place.timezone
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
            # Jyotir AI's retrograde node-ingress search returns a full ~18yr nodal
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

    # Saturn's house-from-Moon → the classical malefic-transit label. The three
    # Sade Sati phases (12/1/2), Ashtama Shani (8) and Kantaka/Ardha-Ashtama (4).
    _SATURN_PHASE_LABELS = {
        12: ("sade_sati", "rising", "Sade Sati — rising (12th from Moon)"),
        1:  ("sade_sati", "peak", "Sade Sati — peak / janma (Moon sign)"),
        2:  ("sade_sati", "setting", "Sade Sati — setting (2nd from Moon)"),
        8:  ("ashtama", "ashtama", "Ashtama Shani (8th from Moon)"),
        4:  ("kantaka", "kantaka", "Kantaka Shani (4th from Moon)"),
    }

    @staticmethod
    def _planet_sign_spans(pl_idx: int, jd_start: float, jd_end: float,
                           tz_offset: float) -> List[tuple]:
        """Contiguous same-sign spans of one graha across [jd_start, jd_end].

        Samples the planet's sidereal longitude once a day and bisects each sign
        change to the hour. A retrograde dip back into the previous sign naturally
        breaks into separate spans (correct — each ingress is a real event). Cheap
        (one `sidereal_longitude` per day); safe for the slow movers this is used
        for (Jupiter/Saturn/Rahu move < 0.25°/day, never crossing a sign twice in
        a day). Returns [(sign0, start_jd, end_jd), …]."""
        pl = drik.ephemeris_planet_index(pl_idx)

        def sign_at(j):
            return int(drik.sidereal_longitude(j - tz_offset / 24.0, pl) // 30) % 12

        spans = []
        jd = jd_start
        cur_sign = sign_at(jd)
        span_start = jd
        while jd < jd_end:
            jd_next = min(jd + 1.0, jd_end)
            s = sign_at(jd_next)
            if s != cur_sign:
                lo, hi = jd, jd_next
                for _ in range(30):
                    mid = (lo + hi) / 2.0
                    if sign_at(mid) == cur_sign:
                        lo = mid
                    else:
                        hi = mid
                    if hi - lo < 1.0 / 24.0:
                        break
                spans.append((cur_sign, span_start, hi))
                cur_sign = sign_at(hi)
                span_start = hi
            jd = jd_next
        spans.append((cur_sign, span_start, jd_end))
        return spans

    @staticmethod
    def get_life_timeline(dob: str, tob: str, place: str,
                          lat: Optional[float] = None, lon: Optional[float] = None,
                          tz: Optional[float] = None,
                          years_before: int = 10, years_after: int = 10,
                          ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A composed dasha–transit **life timeline** over a window around today.

        Layers, all on one shared date axis so the frontend can draw them stacked:
          • **Dasha bands** — the Vimsottari Mahadasha (and the running Maha's
            Bhuktis) overlapping the window, each clipped to the window edges.
          • **Sade Sati / Shani phases** — Saturn's dated spans in the 12th/1st/2nd
            (the three Sade Sati phases), 8th (Ashtama) and 4th (Kantaka) from the
            **natal Moon**, with true entry/exit dates (Saturn is scanned a few
            years before the window so an in-progress phase's real start is caught).
          • **Ingress markers** — Jupiter / Saturn / Rahu sign changes in the window.
          • **Eclipses** — the next solar & lunar eclipses, flagged when they fall
            on a **natal planet's nakshatra** (a personalised sensitivity).

        Everything is composed from the existing dasha / transit / eclipse computes;
        the only new primitive is the daily sign-span scan (`_planet_sign_spans`)."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            _set_ayanamsa(ayanamsa)

            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)

            years_before = max(1, min(int(years_before or 10), 40))
            years_after = max(1, min(int(years_after or 10), 40))

            today = datetime.now()
            jd_today = swe.julday(today.year, today.month, today.day, 12.0)
            jd_start = jd_today - years_before * 365.25
            jd_end = jd_today + years_after * 365.25

            def jd_to_iso(jd):
                g = utils.jd_to_gregorian(jd)
                return f"{g[0]:04d}-{g[1]:02d}-{g[2]:02d}"

            start_iso, end_iso, today_iso = (
                jd_to_iso(jd_start), jd_to_iso(jd_end), jd_to_iso(jd_today))

            # ── Natal reference: Moon sign + each planet's nakshatra ──────────
            natal_jd = swe.julday(year, month, day, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)
            natal_moon_rasi = natal[2][1][0]
            nak_span = 360.0 / 27.0
            natal_naks = {}   # nak_idx -> [planet names]
            for pidx, (rasi, deg) in natal[1:]:
                nak_idx = int((rasi * 30.0 + deg) / nak_span) % 27
                natal_naks.setdefault(nak_idx, []).append(
                    PLANET_NAMES.get(pidx, str(pidx)))

            def clip(s_jd, e_jd):
                """Intersect a span with the display window; None if disjoint."""
                s = max(s_jd, jd_start); e = min(e_jd, jd_end)
                return (s, e) if e > s else None

            # ── Dasha bands (Vimsottari maha + running-window bhuktis) ────────
            dashas = AstrologyCompute.get_dashas(
                dob, tob, place, lat=lat, lon=lon, tz=tz)
            maha_bands, bhukti_bands = [], []
            if dashas.get("status") == "success":
                for d in dashas.get("dasha_sequence", []):
                    try:
                        ds = datetime.strptime(d["start_date"], "%Y-%m-%d")
                        de = datetime.strptime(d["end_date"], "%Y-%m-%d")
                    except Exception:
                        continue
                    if de <= today - timedelta(days=years_before * 365.25 + 1):
                        continue
                    if ds >= today + timedelta(days=years_after * 365.25 + 1):
                        continue
                    running = ds <= today <= de
                    maha_bands.append({
                        "lord": d["lord"],
                        "start_date": d["start_date"],
                        "end_date": d["end_date"],
                        "is_current": running,
                    })
                    # Detail the running maha's bhuktis (they're what "now" sits in).
                    if running:
                        for b in d.get("sub_periods", []):
                            bhukti_bands.append({
                                "maha_lord": d["lord"],
                                "lord": b["lord"],
                                "start_date": b["start_date"],
                                "end_date": b["end_date"],
                                "is_current": (
                                    b["start_date"] <= today_iso <= b["end_date"]),
                            })

            # ── Saturn Sade Sati / Shani phases (from the natal Moon) ─────────
            # Scan Saturn a few years before the window so an ongoing phase's true
            # start is captured, then keep phases that overlap the display window.
            phases = []
            sat_spans = AstrologyCompute._planet_sign_spans(
                6, jd_start - 3 * 365.25, jd_end, tz_offset)
            for sign0, s_jd, e_jd in sat_spans:
                house = ((sign0 - natal_moon_rasi) % 12) + 1
                label = AstrologyCompute._SATURN_PHASE_LABELS.get(house)
                if not label:
                    continue
                cl = clip(s_jd, e_jd)
                if not cl:
                    continue
                kind, phase, desc = label
                phases.append({
                    "kind": kind,
                    "phase": phase,
                    "house_from_moon": house,
                    "sign_name": ZODIAC_NAMES[sign0],
                    "description": desc,
                    "start_date": jd_to_iso(s_jd),   # true (unclipped) boundaries
                    "end_date": jd_to_iso(e_jd),
                    "is_current": s_jd <= jd_today <= e_jd,
                })

            # ── Ingress markers (Jupiter / Saturn / Rahu) ────────────────────
            ingresses = []
            for pidx, pname in ((4, "Jupiter"), (6, "Saturn"), (7, "Rahu")):
                try:
                    spans = AstrologyCompute._planet_sign_spans(
                        pidx, jd_start, jd_end, tz_offset)
                    for i, (sign0, s_jd, _e) in enumerate(spans):
                        if i == 0:
                            continue  # already in this sign at window start
                        ingresses.append({
                            "planet": pname,
                            "to_sign": ZODIAC_NAMES[sign0],
                            "date": jd_to_iso(s_jd),
                        })
                except Exception:
                    pass
            ingresses.sort(key=lambda x: x["date"])

            # ── Eclipses (next few of each), flagged on natal nakshatras ─────
            eclipses = []
            try:
                ecl = AstrologyCompute.get_eclipses(
                    place=place, lat=lat, lon=lon, tz=tz_offset,
                    from_date=today_iso, count=6)
                if ecl.get("status") == "success":
                    sun_i = drik.ephemeris_planet_index(0)
                    moon_i = drik.ephemeris_planet_index(1)
                    for kind, key in (("solar", "solar"), ("lunar", "lunar")):
                        for e in ecl.get(key, []) or []:
                            try:
                                mx = e.get("maximum") or {}
                                edate = mx.get("date")
                                parts = (edate or "").split("-")
                                if len(parts) != 3 or not all(parts):
                                    continue
                                if edate > end_iso:
                                    continue
                                ey, em, ed = map(int, parts)
                                ejd = swe.julday(ey, em, ed, 12.0)
                                lum = sun_i if kind == "solar" else moon_i
                                lon_deg = drik.sidereal_longitude(
                                    ejd - tz_offset / 24.0, lum)
                                nak_idx = int(lon_deg / nak_span) % 27
                                hit = natal_naks.get(nak_idx)
                                eclipses.append({
                                    "kind": kind,
                                    "eclipse_type": e.get("eclipse_type"),
                                    "date": edate,
                                    "nakshatra": NAKSHATRA_NAMES[nak_idx],
                                    "on_natal_nakshatra": bool(hit),
                                    "natal_planets": hit or [],
                                })
                            except Exception:
                                continue
                    eclipses.sort(key=lambda x: x["date"])
            except Exception:
                import traceback
                traceback.print_exc()

            return {
                "status": "success",
                "dob": dob,
                "window": {
                    "start_date": start_iso,
                    "end_date": end_iso,
                    "today": today_iso,
                    "years_before": years_before,
                    "years_after": years_after,
                },
                "moon_sign": ZODIAC_NAMES[natal_moon_rasi],
                "maha_bands": maha_bands,
                "bhukti_bands": bhukti_bands,
                "saturn_phases": phases,
                "ingresses": ingresses,
                "eclipses": eclipses,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_timeline_window_context(dob: str, tob: str, place: str,
                                    target_date: str,
                                    lat: Optional[float] = None,
                                    lon: Optional[float] = None,
                                    tz: Optional[float] = None,
                                    ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """"What's running" at a chosen point on the timeline: the Maha + Bhukti
        active on `target_date`, the Saturn phase (if any) covering it, and the
        ingresses / flagged eclipses within ±9 months. Powers the click-a-point
        panel and the on-demand AI reading for that window."""
        tl = AstrologyCompute.get_life_timeline(
            dob, tob, place, lat=lat, lon=lon, tz=tz,
            years_before=40, years_after=40, ayanamsa=ayanamsa)
        if tl.get("status") != "success":
            return tl
        from datetime import datetime, timedelta
        try:
            datetime.strptime(target_date, "%Y-%m-%d")
        except Exception:
            return {"error": "bad target_date", "status": "failed"}

        def covers(item):
            return item["start_date"] <= target_date <= item["end_date"]

        saturn = next((p for p in tl["saturn_phases"] if covers(p)), None)

        # Resolve the Maha + Bhukti covering the target from the full dasha
        # sequence (tl.bhukti_bands only details the *running* maha, so a
        # far-future target needs the complete tree here).
        maha, bhukti = None, None
        dashas = AstrologyCompute.get_dashas(dob, tob, place, lat=lat, lon=lon, tz=tz)
        if dashas.get("status") == "success":
            for d in dashas.get("dasha_sequence", []):
                if d["start_date"] <= target_date <= d["end_date"]:
                    maha = {"lord": d["lord"], "start_date": d["start_date"],
                            "end_date": d["end_date"]}
                    for b in d.get("sub_periods", []):
                        if b["start_date"] <= target_date <= b["end_date"]:
                            bhukti = {"maha_lord": d["lord"], "lord": b["lord"],
                                      "start_date": b["start_date"],
                                      "end_date": b["end_date"]}
                            break
                    break
        t = datetime.strptime(target_date, "%Y-%m-%d")
        lo_iso = (t - timedelta(days=275)).strftime("%Y-%m-%d")
        hi_iso = (t + timedelta(days=275)).strftime("%Y-%m-%d")
        near_ingress = [i for i in tl["ingresses"] if lo_iso <= i["date"] <= hi_iso]
        near_ecl = [e for e in tl["eclipses"] if lo_iso <= e["date"] <= hi_iso]
        return {
            "status": "success",
            "target_date": target_date,
            "moon_sign": tl["moon_sign"],
            "maha": maha,
            "bhukti": bhukti,
            "saturn_phase": saturn,
            "ingresses": near_ingress,
            "eclipses": near_ecl,
        }

    # Saturn's house-from-Moon → the Sade Sati phase label.
    _SADE_SATI_PHASES = {12: "rising", 1: "peak", 2: "setting"}

    @staticmethod
    def get_saturn_transits(dob: str, tob: str, place: str,
                            lat: Optional[float] = None, lon: Optional[float] = None,
                            tz: Optional[float] = None,
                            ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Sade Sati and the other Saturn transits from the natal Moon, across the
        life (birth → ~37 years ahead, so the past cycles and the next one are all
        captured).

          • **Sade Sati** — the ~7½-year period of Saturn over the 12th → 1st → 2nd
            from the Moon, grouped into cycles, each with its three phase windows
            (rising / peak / setting) and the retrograde re-entry sub-windows.
          • **Ashtama Shani** (8th from Moon) and **Kantaka / Ardha-Ashtama Shani**
            (4th) periods.
          • The **current** status (which, if any, is running now)."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)

            natal_jd = swe.julday(year, month, day, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)
            moon_rasi = natal[2][1][0]

            today = datetime.now()
            jd_today = swe.julday(today.year, today.month, today.day, 12.0)
            jd_start = swe.julday(year, month, day, 12.0)
            jd_end = jd_today + 37 * 365.25

            def iso(jd):
                g = utils.jd_to_gregorian(jd)
                return f"{g[0]:04d}-{g[1]:02d}-{g[2]:02d}"

            spans = AstrologyCompute._planet_sign_spans(6, jd_start, jd_end, tz_offset)
            annotated = []
            for sign0, s_jd, e_jd in spans:
                house = ((sign0 - moon_rasi) % 12) + 1
                annotated.append({"sign0": sign0, "house": house, "s": s_jd, "e": e_jd})

            # ── Sade Sati cycles (houses 12→1→2), gaps > 1 yr split cycles ──
            sade = [a for a in annotated if a["house"] in (12, 1, 2)]
            cycles = []
            cur = None
            for a in sade:
                if cur is None or a["s"] - cur["_last"] > 365.0:
                    cur = {"spans": [a], "_start": a["s"], "_last": a["e"]}
                    cycles.append(cur)
                else:
                    cur["spans"].append(a)
                    cur["_last"] = max(cur["_last"], a["e"])

            def merge_house(spans_list, house):
                hs = [sp for sp in spans_list if sp["house"] == house]
                if not hs:
                    return None
                start = min(sp["s"] for sp in hs)
                end = max(sp["e"] for sp in hs)
                sub = [{"start": iso(sp["s"]), "end": iso(sp["e"])} for sp in hs]
                return {
                    "phase": AstrologyCompute._SADE_SATI_PHASES[house],
                    "house_from_moon": house,
                    "sign_name": ZODIAC_NAMES[hs[0]["sign0"]],
                    "start_date": iso(start), "end_date": iso(end),
                    "start_jd": start, "end_jd": end,
                    "retrograde_reentry": len(hs) > 1,
                    "sub_windows": sub if len(hs) > 1 else [],
                }

            sade_sati_periods = []
            for c in cycles:
                phases = [p for p in (merge_house(c["spans"], h) for h in (12, 1, 2)) if p]
                if not phases:
                    continue
                start = min(p["start_jd"] for p in phases)
                end = max(p["end_jd"] for p in phases)
                is_current = start <= jd_today <= end
                cur_phase = None
                if is_current:
                    for p in phases:
                        if p["start_jd"] <= jd_today <= p["end_jd"]:
                            cur_phase = p["phase"]
                            break
                for p in phases:
                    p.pop("start_jd", None); p.pop("end_jd", None)
                sade_sati_periods.append({
                    "start_date": iso(start), "end_date": iso(end),
                    "moon_sign": ZODIAC_NAMES[moon_rasi],
                    "is_current": is_current, "current_phase": cur_phase,
                    "is_past": end < jd_today, "phases": phases,
                })

            def group_periods(house):
                hs = [a for a in annotated if a["house"] == house]
                out = []
                cur2 = None
                for a in hs:
                    if cur2 is None or a["s"] - cur2["_last"] > 365.0:
                        cur2 = {"_s": a["s"], "_last": a["e"], "sign0": a["sign0"]}
                        out.append(cur2)
                    else:
                        cur2["_last"] = max(cur2["_last"], a["e"])
                return [{
                    "sign_name": ZODIAC_NAMES[o["sign0"]],
                    "start_date": iso(o["_s"]), "end_date": iso(o["_last"]),
                    "is_current": o["_s"] <= jd_today <= o["_last"],
                    "is_past": o["_last"] < jd_today,
                } for o in out]

            ashtama = group_periods(8)
            kantaka = group_periods(4)

            current = {
                "sade_sati": next((p for p in sade_sati_periods if p["is_current"]), None),
                "ashtama": next((p for p in ashtama if p["is_current"]), None),
                "kantaka": next((p for p in kantaka if p["is_current"]), None),
            }

            return {
                "status": "success",
                "moon_sign": ZODIAC_NAMES[moon_rasi],
                "today": iso(jd_today),
                "sade_sati_periods": sade_sati_periods,
                "ashtama_periods": ashtama,
                "kantaka_periods": kantaka,
                "current": current,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # Bhava (house) systems exposed to the UI. Value -> (Jyotir AI bhava_madhya_method,
    # label, short blurb). 'O' (Sripati/Porphyrius) is what Jagannatha Hora draws for
    # its Bhava Chalit; 'P' is true Placidus; 3 is the KP cuspal method; 1 is the
    # equal Bhava Chalit (KN Rao) — Jyotir AI's own default.
    BHAVA_METHODS = {
        "SRIPATI":   ("O", "Sripati (Porphyry)", "Matches Jagannatha Hora's Bhava Chalit"),
        "PLACIDUS":  ("P", "Placidus", "Western time-based house division"),
        "KP":        (3,   "KP (Krishnamurti)", "Placidus cusps, KP padhati"),
        "EQUAL":     (1,   "Equal (KN Rao)", "Cusp ±15° around the Lagna degree"),
    }

    @staticmethod
    def get_bhava_chart(dob: str, tob: str, place: str,
                        lat: Optional[float] = None, lon: Optional[float] = None,
                        tz: Optional[float] = None, method: str = "SRIPATI",
                        ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Bhava (house-cusp) chart — a Bhava Chalit / cuspal chart.

        Unlike the Rasi chart (which equates each sign with a house), a bhava chart
        divides the ecliptic by house *cusps* (Sripati/Porphyry, Placidus, KP…), so a
        graha near a sign boundary can fall in a different bhava than its sign. Returns
        each of the 12 bhavas with its start / madhya (cusp) / end longitudes, the sign
        the cusp sits in, and the grahas occupying it — plus a `planets` map keyed by
        name for the North/South Kundali component (each graha placed in the SIGN of the
        bhava it occupies, i.e. a Bhava Chalit rendering)."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

        method_key = (method or "SRIPATI").upper()
        madhya_method, method_label, method_note = AstrologyCompute.BHAVA_METHODS.get(
            method_key, AstrologyCompute.BHAVA_METHODS["SRIPATI"])

        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz or 5.5

            jd = swe.julday(year, month, day, hour + minute / 60.0)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            # Rasi positions give each graha's own sign + degree (for the table/tooltip);
            # the bhava chart gives which bhava (house) each graha falls in by cusp.
            d1 = charts.rasi_chart(jd, place_obj)
            rasi_of_planet = {}
            for pidx, (rasi, degrees) in d1[1:]:
                rasi_of_planet[pidx] = (rasi, degrees)

            bhava = charts.bhava_chart(jd, place_obj, bhava_madhya_method=madhya_method)

            houses = []
            planets = {}
            planet_bhava = {}  # planet index -> bhava number (1..12)
            for i, row in enumerate(bhava):
                bhava_rasi = row[0]
                start, cusp, end = row[1]
                occupants = row[2]
                bhava_no = i + 1
                planet_names_here = []
                for occ in occupants:
                    if occ == const._ascendant_symbol:
                        continue  # the Lagna is drawn separately
                    name = PLANET_NAMES.get(occ)
                    if name:
                        planet_names_here.append(name)
                        planet_bhava[occ] = bhava_no
                        r, d = rasi_of_planet.get(occ, (bhava_rasi, 0.0))
                        planets[name] = {
                            # Placed in the SIGN of its bhava → Bhava Chalit layout.
                            "house": bhava_rasi + 1,
                            "bhava": bhava_no,
                            "degrees": round(d, 2),
                            "rasi": r,
                            "sign_name": ZODIAC_NAMES[r],
                        }
                houses.append({
                    "bhava": bhava_no,
                    "sign": bhava_rasi + 1,
                    "sign_name": ZODIAC_NAMES[bhava_rasi],
                    "start": round(start % 360.0, 2),
                    "cusp": round(cusp % 360.0, 2),
                    "end": round(end % 360.0, 2),
                    "planets": planet_names_here,
                })

            # Lagna = first bhava; drawn on the Kundali at the sign of bhava 1.
            asc_rasi, asc_deg = d1[0][1]
            lagna = {
                "house": bhava[0][0] + 1,
                "degrees": round(asc_deg, 2),
                "sign_name": ZODIAC_NAMES[bhava[0][0]],
            }

            return {
                "status": "success",
                "method": method_key,
                "method_label": method_label,
                "method_note": method_note,
                "lagna": lagna,
                "planets": planets,
                "houses": houses,
            }
        except Exception as e:
            print(f"Bhava chart error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_ephemeris(start_date: str, days: int = 30, place: str = "",
                      lat: Optional[float] = None, lon: Optional[float] = None,
                      tz: Optional[float] = None, ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Sidereal ephemeris + ingress calendar over a date window.

        For each day in [start_date, start_date+days) computes every graha's sign,
        degree-in-sign and retrograde state at local noon, and derives the sign-change
        (ingress) events by watching for a sign change between consecutive days. Powers
        the transit-calendar / ephemeris table and the ingress list."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

        try:
            _set_ayanamsa(ayanamsa)
            from datetime import date as _date, timedelta

            days = max(1, min(int(days or 30), 92))  # clamp the window (perf + payload)
            y, m, d = map(int, start_date.split("-"))
            start = _date(y, m, d)

            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place or "", lat, lon, tz_offset)

            nak_span = 360.0 / 27.0
            order = [0, 1, 2, 3, 4, 5, 6, 7, 8]  # Sun..Ketu

            rows = []
            ingresses = []
            prev_sign = {}  # planet index -> previous day's sign
            for offset in range(days):
                cur = start + timedelta(days=offset)
                cur_iso = cur.isoformat()
                jd = swe.julday(cur.year, cur.month, cur.day, 12.0)
                chart = charts.rasi_chart(jd, place_obj)
                retro_ids = set(drik.planets_in_retrograde(jd, place_obj))
                pos = {pidx: (rasi, degrees) for pidx, (rasi, degrees) in chart[1:]}

                row_planets = {}
                for pidx in order:
                    rasi, degrees = pos.get(pidx, (0, 0.0))
                    abs_long = rasi * 30.0 + degrees
                    name = PLANET_NAMES[pidx]
                    row_planets[name] = {
                        "sign": rasi + 1,
                        "sign_name": ZODIAC_NAMES[rasi],
                        "degrees": round(degrees, 2),
                        "nakshatra": NAKSHATRA_NAMES[int(abs_long / nak_span) % 27],
                        "retrograde": pidx in retro_ids,
                    }
                    # Ingress = a sign change vs. the previous day (skip the first row).
                    if pidx in prev_sign and prev_sign[pidx] != rasi:
                        ingresses.append({
                            "date": cur_iso,
                            "planet": name,
                            "from_sign": ZODIAC_NAMES[prev_sign[pidx]],
                            "to_sign": ZODIAC_NAMES[rasi],
                            "retrograde": pidx in retro_ids,
                        })
                    prev_sign[pidx] = rasi

                rows.append({"date": cur_iso, "planets": row_planets})

            end = start + timedelta(days=days - 1)
            return {
                "status": "success",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "days": days,
                "planet_order": [PLANET_NAMES[p] for p in order],
                "rows": rows,
                "ingresses": ingresses,
            }
        except Exception as e:
            print(f"Ephemeris error: {str(e)}")
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

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

        Computes each person's Moon nakshatra+pada and runs Jyotir AI's North-Indian
        Ashtakoota (the classic 36-point system). Returns the eight kootas with
        their *correct* individual maxima plus a verdict, so the frontend can render
        an accurate breakdown."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

        nakshatra_names = [
            "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra",
            "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
            "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
            "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta", "Shatabhisha",
            "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
        ]

        def _person_chart(dob, tob, place, lat, lon, person_tz):
            """Returns (moon nakshatra 1-27, pada 1-4, rasi planet_positions)."""
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
            return nak, pada, pp

        def _mangal_dosha(pp):
            """Kuja / Mangal (Manglik) dosha with cancellation nuances. Mars in
            houses 1/2/4/7/8/12 counted from the Lagna, the Moon and Venus flags
            the dosha; classical parihara (own/exalt sign, sign-specific house
            exceptions, benefic conjunction) softens or cancels it."""
            signs = {pid: s for pid, (s, _l) in pp[1:] if pid in PLANET_NAMES}
            lagna = pp[0][1][0]
            mars_s = signs.get(2)
            refs = {"Lagna": lagna, "Moon": signs.get(1), "Venus": signs.get(5)}
            dosha_houses = {1, 2, 4, 7, 8, 12}
            hits = {}
            for name, rs in refs.items():
                if rs is None or mars_s is None:
                    continue
                h = ((mars_s - rs) % 12) + 1
                if h in dosha_houses:
                    hits[name] = h
            cancellations = []
            if mars_s in (0, 7):
                cancellations.append(f"Mars is in its own sign ({ZODIAC_NAMES[mars_s]}).")
            if mars_s == 9:
                cancellations.append("Mars is exalted in Capricorn.")
            # Sign-specific house exceptions (traditional parihara).
            exceptions = {1: {0}, 2: {2, 5}, 4: {0, 7}, 7: {3, 9}, 8: {8, 11}, 12: {1, 6}}
            for name, h in hits.items():
                if mars_s in exceptions.get(h, set()):
                    cancellations.append(
                        f"Mars in the {h}th from {name} sits in {ZODIAC_NAMES[mars_s]} — a classical exception.")
            if signs.get(4) is not None and signs.get(4) == mars_s:
                cancellations.append("Jupiter is conjunct Mars, tempering the dosha.")
            return {"manglik": len(hits) > 0,
                    "mars_sign": ZODIAC_NAMES[mars_s] if mars_s is not None else "—",
                    "from": hits, "cancellations": cancellations}

        try:
            boy_nak, boy_pada, boy_pp = _person_chart(
                male_dob, male_tob, male_place, male_lat, male_lon, male_tz)
            girl_nak, girl_pada, girl_pp = _person_chart(
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

            # ── Dashakoota (South / Tamil 10-porutham) — adds Mahendra, Vedha,
            #    Rajju and Stree-Deergha over the Ashtakoot 8. Each is worth 1.
            dashakoota = []
            dashakoota_score = 0
            try:
                sk = compat_module.Ashtakoota(boy_nak, boy_pada, girl_nak, girl_pada, method="South")
                ss = sk.compatibility_score()
                (_sv, s_vasiya, s_gana, s_dina, s_yoni, s_raasi_adhi, s_raasi,
                 _sn, _sscore, s_mahendra, s_vedha, s_rajju, s_sthree) = ss[:13]
                _dk = [
                    ("dina", "Dina (Tara)", s_dina, "Health, longevity & prosperity"),
                    ("gana", "Gana", s_gana, "Temperament & nature"),
                    ("mahendra", "Mahendra", s_mahendra, "Progeny & well-being"),
                    ("sthree", "Stree Deergha", s_sthree, "Longevity of the union & the wife's welfare"),
                    ("yoni", "Yoni", s_yoni, "Physical & intimate compatibility"),
                    ("rasi", "Rasi", s_raasi, "Family welfare & prosperity"),
                    ("rasiadhi", "Rasi Adhipati", s_raasi_adhi, "Mental affinity (lords' friendship)"),
                    ("vasiya", "Vasiya", s_vasiya, "Mutual attraction & influence"),
                    ("rajju", "Rajju", s_rajju, "Longevity of the husband (body-part clash to avoid)"),
                    ("vedha", "Vedha", s_vedha, "Absence of mutual affliction between stars"),
                ]
                for key, name, ok, desc in _dk:
                    ok_b = bool(ok)
                    dashakoota.append({"key": key, "name": name, "ok": ok_b, "description": desc})
                    if ok_b:
                        dashakoota_score += 1
            except Exception as e:
                print(f"Dashakoota calculation error: {e}")

            # ── Mangal (Kuja) dosha for both, with cancellation nuances.
            boy_mangal = _mangal_dosha(boy_pp)
            girl_mangal = _mangal_dosha(girl_pp)
            if boy_mangal["manglik"] and girl_mangal["manglik"]:
                mangal_verdict = "Both partners are Manglik — the dosha is traditionally considered mutually cancelled."
            elif boy_mangal["manglik"] or girl_mangal["manglik"]:
                who = "The groom" if boy_mangal["manglik"] else "The bride"
                mangal_verdict = (f"{who} is Manglik while the partner is not — "
                                  "weigh the cancellations before concluding.")
            else:
                mangal_verdict = "Neither partner is Manglik — no Kuja dosha to reconcile."

            return {
                "total_score": round(float(total), 1),
                "max_score": 36,
                "status": status,
                "kootas": kootas,
                "boy": {"nakshatra": nakshatra_names[boy_nak - 1], "pada": boy_pada},
                "girl": {"nakshatra": nakshatra_names[girl_nak - 1], "pada": girl_pada},
                "dashakoota": {"poruthams": dashakoota, "score": dashakoota_score, "max": 10},
                "mangal_dosha": {"boy": boy_mangal, "girl": girl_mangal, "verdict": mangal_verdict},
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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
    def _natal_jd_place(dob, tob, place, lat, lon, tz):
        """Shared setup: parse dob/tob → (jd, place_obj, y, m, d, hour, minute).
        Callers must already have set the ayanamsa."""
        y, m, d = map(int, dob.split("-"))
        tp = tob.split(":")
        hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
        if not lat or not lon:
            lat, lon = 13.0827, 80.2707
        place_obj = drik.Place(place or "", lat, lon, tz or 5.5)
        jd = swe.julday(y, m, d, hour + minute / 60.0)
        return jd, place_obj, y, m, d, hour, minute

    @staticmethod
    def get_sphuta(dob: str, tob: str, place: str,
                   lat: Optional[float] = None, lon: Optional[float] = None,
                   tz: Optional[float] = None,
                   ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """The classical Sphutas — sensitive longitudes computed from the natal
        chart (Tri/Chatur/Pancha/Prana/Deha/Mrityu/Beeja/Kshetra/Tithi/Yoga/
        Yogi/Avayogi). Each is returned as a sign + degree + house-from-Lagna.
        Ayanamsa server-injected + reset."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from jhora.horoscope.chart import sphuta as sphuta_mod

            jd, place_obj, y, m, d, hour, minute = \
                AstrologyCompute._natal_jd_place(dob, tob, place, lat, lon, tz)
            dob_date = drik.Date(y, m, d)
            tob_tuple = (hour, minute, 0)
            asc_sign = charts.rasi_chart(jd, place_obj)[0][1][0]

            items = []
            for label, fn_name, significance in SPHUTA_DEFS:
                try:
                    fn = getattr(sphuta_mod, fn_name)
                    sign, deg = fn(dob_date, tob_tuple, place_obj)
                    sign = int(sign) % 12
                    items.append({
                        "name": label,
                        "significance": significance,
                        "sign": sign,
                        "sign_name": ZODIAC_NAMES[sign],
                        "degrees": round(float(deg), 2),
                        "house": ((sign - asc_sign) % 12) + 1,
                    })
                except Exception as e:
                    print(f"Sphuta {label} error: {e}")

            return {"status": "success", "lagna_sign": asc_sign,
                    "lagna_sign_name": ZODIAC_NAMES[asc_sign], "sphutas": items}
        except Exception as e:
            print(f"Sphuta error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_sahams(dob: str, tob: str, place: str,
                   lat: Optional[float] = None, lon: Optional[float] = None,
                   tz: Optional[float] = None,
                   ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """The 36 natal Sahams (Arabic-part-like sensitive points) — each a
        longitude → sign + degree + house-from-Lagna. Day/night birth (from the
        natal sunrise/sunset) drives each saham's day/night formula. Ayanamsa
        server-injected + reset."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from jhora.horoscope.transit import saham as saham_mod

            jd, place_obj, y, m, d, hour, minute = \
                AstrologyCompute._natal_jd_place(dob, tob, place, lat, lon, tz)
            cht = charts.rasi_chart(jd, place_obj)
            asc_sign = cht[0][1][0]

            # Day- or night-birth from the natal sunrise/sunset.
            night_birth = False
            try:
                birth_hrs = hour + minute / 60.0
                sr = utils.from_dms_str_to_dms(drik.sunrise(jd, place_obj)[1])
                ss = utils.from_dms_str_to_dms(drik.sunset(jd, place_obj)[1])
                sr_h = sr[0] + sr[1] / 60.0 + sr[2] / 3600.0
                ss_h = ss[0] + ss[1] / 60.0 + ss[2] / 3600.0
                night_birth = birth_hrs > ss_h or birth_hrs < sr_h
            except Exception as e:
                print(f"Saham night-birth error: {e}")

            items = []
            for label, fn_name, significance in NATAL_SAHAMS:
                try:
                    fn = getattr(saham_mod, fn_name)
                    try:
                        s_long = fn(cht, night_birth)
                    except TypeError:
                        s_long = fn(cht)
                    s_long = float(s_long) % 360
                    s_sign = int(s_long // 30)
                    items.append({
                        "name": label,
                        "significance": significance,
                        "sign": s_sign,
                        "sign_name": ZODIAC_NAMES[s_sign],
                        "degrees": round(s_long % 30, 2),
                        "house": ((s_sign - asc_sign) % 12) + 1,
                    })
                except Exception as e:
                    print(f"Saham {label} error: {e}")

            return {"status": "success", "night_birth": night_birth,
                    "lagna_sign": asc_sign, "lagna_sign_name": ZODIAC_NAMES[asc_sign],
                    "sahams": items}
        except Exception as e:
            print(f"Sahams error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_argala(dob: str, tob: str, place: str,
                   lat: Optional[float] = None, lon: Optional[float] = None,
                   tz: Optional[float] = None,
                   ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Argala (planetary intervention) and Virodhargala (counter-intervention)
        for each of the 12 bhavas. Planets in the 2nd/4th/5th/11th from a house
        cause argala on it; planets in the 12th/10th/9th/3rd obstruct it. Returns
        one row per bhava with the contributing planets. Ayanamsa injected + reset."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            jd, place_obj, *_ = \
                AstrologyCompute._natal_jd_place(dob, tob, place, lat, lon, tz)
            cht = charts.rasi_chart(jd, place_obj)
            asc_sign = cht[0][1][0]
            h2p = utils.get_house_planet_list_from_planet_positions(cht)
            argala, virodhargala = house.get_argala(h2p)

            def _planets(cell):
                """'4/5' → ['Jupiter','Venus']; '' → []."""
                out = []
                for tok in str(cell).replace("/", " ").split():
                    tok = tok.strip()
                    if tok.isdigit() and int(tok) in PLANET_NAMES:
                        out.append(PLANET_NAMES[int(tok)])
                return out

            rows = []
            for r in range(12):
                arg = [
                    {"from": ARGALA_HOUSE_LABELS[i], "planets": _planets(argala[r][i])}
                    for i in range(len(ARGALA_HOUSE_LABELS))
                    if _planets(argala[r][i])
                ]
                vir = [
                    {"from": VIRODHARGALA_HOUSE_LABELS[i], "planets": _planets(virodhargala[r][i])}
                    for i in range(len(VIRODHARGALA_HOUSE_LABELS))
                    if _planets(virodhargala[r][i])
                ]
                sign = (asc_sign + r) % 12
                net = "argala" if len(arg) > len(vir) else \
                      ("virodhargala" if len(vir) > len(arg) else "balanced")
                rows.append({
                    "bhava": r + 1,
                    "sign": sign,
                    "sign_name": ZODIAC_NAMES[sign],
                    "argala": arg,
                    "virodhargala": vir,
                    "net": net if (arg or vir) else "none",
                })

            return {"status": "success", "lagna_sign": asc_sign,
                    "lagna_sign_name": ZODIAC_NAMES[asc_sign], "houses": rows}
        except Exception as e:
            print(f"Argala error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_vedic_clock(date: Optional[str] = None, place: str = "",
                        lat: Optional[float] = None, lon: Optional[float] = None,
                        tz: Optional[float] = None) -> Dict:
        """Vedic day-clock data for a date + place: sunrise/sunset, the day &
        night lengths, the 60-ghati day divisions (1 ghati = 24 min from sunrise),
        the running hora lord, and the panchanga limbs (tithi/nakshatra/yoga) —
        enough for the frontend to render and live-tick a ghati/vighati clock.
        `date` defaults to today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
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

            sr = drik.sunrise(jd_noon, place_obj)   # (hours, 'HH:MM:SS')
            ss = drik.sunset(jd_noon, place_obj)
            sr_h = sr[0] if isinstance(sr[0], (int, float)) else 6.0
            ss_h = ss[0] if isinstance(ss[0], (int, float)) else 18.0
            day_len = max(0.01, ss_h - sr_h)
            night_len = 24.0 - day_len

            # Running hora lord (reuse the shubha_hora table).
            horas = drik.shubha_hora(jd_noon, place_obj)
            now_local = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            is_today = (now_local.year, now_local.month, now_local.day) == (year, month, day)
            now_h = now_local.hour + now_local.minute / 60.0 if is_today else None
            current_hora = None
            for i, (pidx, start, end) in enumerate(horas):
                name = HORA_PLANETS[pidx] if 0 <= pidx < len(HORA_PLANETS) else str(pidx)
                if is_today and i < 12:
                    def _to_h(s):
                        p = str(s).split(":")
                        return int(p[0]) + int(p[1]) / 60.0
                    if _to_h(start) <= now_h < _to_h(end):
                        current_hora = {"planet": name, "benefic": name in HORA_BENEFICS,
                                        "start": str(start)[:5], "end": str(end)[:5]}
            if current_hora is None:
                # Fall back to the weekday lord as the day's first hora lord.
                first = HORA_PLANETS[horas[0][0]] if horas else "Sun"
                current_hora = {"planet": first, "benefic": first in HORA_BENEFICS}

            # Ghati/vighati elapsed since sunrise (only meaningful for "today").
            ghati = vighati = None
            if now_h is not None:
                elapsed_min = (now_h - sr_h) * 60.0
                if elapsed_min < 0:
                    elapsed_min += 24 * 60  # before sunrise → previous vedic day
                ghati_f = elapsed_min / 24.0          # 1 ghati = 24 min
                ghati = int(ghati_f) % 60
                vighati = int((ghati_f - int(ghati_f)) * 60)

            # Panchanga limbs at the reference instant.
            ref_jd = swe.julday(year, month, day, now_h if now_h is not None else 12.0)
            limbs = {}
            try:
                tt = drik.tithi(ref_jd, place_obj)
                t_name, t_paksha = _tithi_name(tt[0])
                limbs["tithi"] = t_name
                limbs["paksha"] = t_paksha
            except Exception:
                pass
            try:
                nk = drik.nakshatra(ref_jd, place_obj)
                limbs["nakshatra"] = NAKSHATRA_NAMES[(nk[0] - 1) % 27]
            except Exception:
                pass
            try:
                yg = drik.yogam(ref_jd, place_obj)
                limbs["yoga"] = YOGA_NAMES[(yg[0] - 1) % 27]
            except Exception:
                pass

            def _hm(s):
                return str(s)[:5] if s is not None else "—"

            return {
                "status": "success",
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "place": place,
                "is_today": is_today,
                "sunrise": _hm(sr[1]) if not isinstance(sr[1], (int, float)) else _fmt_hours(sr_h),
                "sunset": _hm(ss[1]) if not isinstance(ss[1], (int, float)) else _fmt_hours(ss_h),
                "sunrise_hours": round(sr_h, 4),
                "sunset_hours": round(ss_h, 4),
                "day_length_hours": round(day_len, 4),
                "night_length_hours": round(night_len, 4),
                "ghati": ghati,
                "vighati": vighati,
                "current_hora": current_hora,
                "panchanga": limbs,
                "tz": tz_offset,
            }
        except Exception as e:
            print(f"Vedic clock error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_retrograde(date: Optional[str] = None, place: str = "",
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None) -> Dict:
        """Retrograde (Vakra) status for a date: which grahas are retrograde now,
        the next station (direction-change) date for Mars/Mercury/Jupiter/Venus/
        Saturn, and the Vakra-gathi epicycle loop (x,y) for each — the geocentric
        apparent path that produces the classic retrograde loop, computed with
        numpy (no pyqtgraph). `date` defaults to today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            import numpy as np
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
            jd = swe.julday(year, month, day, 12)

            retro_now = set(drik.planets_in_retrograde(jd, place_obj))

            def _dist(T):
                return T ** (2 / 3)  # Kepler's third law (a ∝ T^(2/3))

            def _orbit(pidx, n=240):
                period_days, loops = RETRO_PERIODS[pidx]
                earth_period = RETRO_PERIODS[-1][0]
                d1 = _dist(period_days)
                d2 = _dist(earth_period)
                theta = np.linspace(0, 2 * np.pi * loops, n)
                x = d1 * np.cos(earth_period * theta / period_days) - d2 * np.cos(theta)
                y = d1 * np.sin(earth_period * theta / period_days) - d2 * np.sin(theta)
                scale = max(float(np.max(np.abs(x))), float(np.max(np.abs(y))), 1e-9)
                return [round(v / scale, 4) for v in x.tolist()], \
                       [round(v / scale, 4) for v in y.tolist()]

            planets = []
            ref_date = drik.Date(year, month, day)
            for pidx in RETRO_STATION_PLANETS:
                name = PLANET_NAMES[pidx]
                is_retro = pidx in retro_now
                next_station = None
                try:
                    nd = drik.next_planet_retrograde_change_date(pidx, ref_date, place_obj)
                    if nd and nd[0]:
                        gy, gm, gd, _ = utils.jd_to_gregorian(nd[0])
                        next_station = {
                            "date": f"{gy:04d}-{gm:02d}-{gd:02d}",
                            # direction: -1 turning retrograde, +1 turning direct
                            "becomes": "direct" if is_retro else "retrograde",
                        }
                except Exception as e:
                    print(f"Retro station {name} error: {e}")
                ox, oy = _orbit(pidx)
                planets.append({
                    "planet": name,
                    "retrograde": is_retro,
                    "next_station": next_station,
                    "orbit_x": ox,
                    "orbit_y": oy,
                })

            # Rahu & Ketu are perpetually retrograde in the mean-node scheme.
            nodes = [{"planet": PLANET_NAMES[p], "retrograde": True, "perpetual": True}
                     for p in (7, 8)]

            return {
                "status": "success",
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "place": place,
                "planets": planets,
                "nodes": nodes,
                "retrograde_now": [PLANET_NAMES[p] for p in sorted(retro_now)
                                   if p in PLANET_NAMES],
            }
        except Exception as e:
            print(f"Retrograde error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_nakshatra_profile(dob: str, tob: str, place: str,
                              lat: Optional[float] = None, lon: Optional[float] = None,
                              tz: Optional[float] = None,
                              current_date: Optional[str] = None,
                              ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Janma-nakshatra deep-dive (§5.7): the Moon's nakshatra + pada with its
        classical attributes (lord, deity, symbol, gana, yoni, nadi, guna, varna,
        naming syllable) and a 27-day tarabala calendar strip from `current_date`
        (or today) at the birth place — the favourable/unfavourable days as the
        Moon cycles the 27 stars relative to the janma-nakshatra."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime, timedelta
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place or "", lat, lon, tz_offset)

            natal_jd = swe.julday(year, month, day, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)
            moon_rasi, moon_deg = natal[2][1]  # row 2 = Moon
            moon_long = moon_rasi * 30.0 + moon_deg
            nak_span = 360.0 / 27.0
            janma_nak = int(moon_long / nak_span)          # 0-based
            pada = int((moon_long % nak_span) / (nak_span / 4.0)) + 1

            profile = refdata.nakshatra_profile(janma_nak, pada, moon_rasi)

            # ── 27-day tarabala calendar from current_date (or today) ──────
            if current_date:
                cy, cm, cd = map(int, current_date.split("-"))
            else:
                now = datetime.now()
                cy, cm, cd = now.year, now.month, now.day
            start = datetime(cy, cm, cd)
            calendar = []
            for offset in range(27):
                d = start + timedelta(days=offset)
                jd = swe.julday(d.year, d.month, d.day, 12)
                nk = drik.nakshatra(jd, place_obj)  # [nak_no(1-27), pada, ...]
                day_nak = nk[0]                     # 1-based
                # count_stars expects 1-based star numbers; tarabala group 0-8.
                tb = utils.count_stars(janma_nak + 1, day_nak) % 9
                tb_name, tb_tone = TARABALA_NAMES[tb]
                calendar.append({
                    "date": f"{d.year:04d}-{d.month:02d}-{d.day:02d}",
                    "nakshatra": NAKSHATRA_NAMES[day_nak - 1],
                    "tarabala": tb_name,
                    "tone": tb_tone,
                })

            return {
                "status": "success",
                "profile": profile,
                "moon_sign": ZODIAC_NAMES[moon_rasi],
                "tarabala_calendar": calendar,
                "calendar_from": f"{cy:04d}-{cm:02d}-{cd:02d}",
            }
        except Exception as e:
            print(f"Nakshatra profile error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_gochara_phala(dob: str, tob: str, place: str,
                          lat: Optional[float] = None, lon: Optional[float] = None,
                          tz: Optional[float] = None,
                          current_date: Optional[str] = None,
                          current_tz: Optional[float] = None,
                          ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Classical Moon-referenced gochara-phala with vedha (§5.6): for each
        transiting graha, the house it occupies from the natal Moon, whether that
        is a favourable position, and whether a vedha (another graha in the
        obstruction house) cancels the good result. Complements the degree-based
        Transit page with the panchang-tradition verdict lay readers know."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place or "", lat, lon, tz_offset)

            natal_jd = swe.julday(year, month, day, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)
            moon_rasi = natal[2][1][0]

            if current_date:
                ty, tm, td = map(int, current_date.split("-"))
            else:
                now = datetime.now()
                ty, tm, td = now.year, now.month, now.day
            transit_tz = current_tz if current_tz is not None else tz_offset
            transit_place = drik.Place(place or "", lat, lon, transit_tz)
            transit_jd = swe.julday(ty, tm, td, 12)
            transit = charts.rasi_chart(transit_jd, transit_place)

            transit_rasi = {PLANET_NAMES[pidx]: rasi
                            for pidx, (rasi, _deg) in transit[1:]
                            if pidx in PLANET_NAMES}
            rows = refdata.gochara_phala(moon_rasi, transit_rasi)
            favourable = sum(1 for r in rows if r["tone"] == "good")

            return {
                "status": "success",
                "transit_date": f"{ty:04d}-{tm:02d}-{td:02d}",
                "moon_sign": ZODIAC_NAMES[moon_rasi],
                "results": rows,
                "favourable_count": favourable,
                "total": len(rows),
            }
        except Exception as e:
            print(f"Gochara-phala error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def search_location(query: str = "", *args, **kwargs):
        """Geocode a free-text place query to [display_name, lat, lon, tz_offset].

        Coordinates come from OpenStreetMap (Nominatim via geopy) and the UTC
        offset from timezonefinder (both already Jyotir AI dependencies). The tz
        offset reflects the place's *current* rules (incl. DST), which is what
        the form needs when picking a location. Returns None when nothing
        matches so the endpoint can report a friendly "not found"."""
        if not ENGINE_AVAILABLE:
            return None
        q = (query or "").strip()
        if not q:
            return None
        try:
            from geopy.geocoders import Nominatim

            geolocator = Nominatim(user_agent="JyotirAIWeb", timeout=10)
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
        if not ENGINE_AVAILABLE:
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

            geolocator = Nominatim(user_agent="JyotirAIWeb", timeout=10)
            loc = geolocator.reverse((lat, lon), language="en", zoom=10)
            if loc and loc.address:
                place = loc.address
        except Exception as e:
            # Network/rate-limit issues should not break the picker; keep coords.
            print(f"Reverse geocode lookup error: {e}")
        return [place, lat, lon, tz]
