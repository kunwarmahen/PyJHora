#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from typing import Dict, Optional, List
import sys
import os

# Add parent directory to path to import jhora
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

try:
    from jhora.panchanga import drik
    from jhora.horoscope.chart import charts, house, strength, yoga, dosha
    from jhora.horoscope.match import compatibility as compat_module
    from jhora.horoscope.dhasa.graha import vimsottari
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

    # Add placeholder methods for other required functions
    @staticmethod
    def get_horoscope_predictions(*args, **kwargs):
        return {"error": "Not implemented yet"}

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

            weekday = drik.vaara(jd, place_obj)

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
    def get_transits(*args, **kwargs):
        return {"error": "Not implemented yet"}

    @staticmethod
    def get_compatibility(*args, **kwargs):
        return {"error": "Not implemented yet"}

    @staticmethod
    def search_location(*args, **kwargs):
        return {"error": "Not implemented yet"}
