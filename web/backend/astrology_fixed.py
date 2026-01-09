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
    PYJHORA_AVAILABLE = True
except ImportError as e:
    print(f"PyJHora import error: {e}")
    PYJHORA_AVAILABLE = False

class AstrologyCompute:
    """Core astrology calculations using PyJHora"""

    @staticmethod
    def calculate_birth_chart(dob: str, tob: str, place: str,
                             lat: Optional[float] = None, lon: Optional[float] = None,
                             tz: Optional[float] = None) -> Dict:
        """Calculate birth chart with planetary positions"""
        if not PYJHORA_AVAILABLE:
            return {"error": "PyJHora not available"}

        try:
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

            # Get ascendant
            ascendant = charts.ascendant(jd, place_obj)

            # Format planetary positions for D1
            d1_planets = {}
            for planet_index, (rasi, degrees) in d1_chart[1:]:  # Skip ascendant at index 0
                planet_name = const.planet_list[planet_index]
                d1_planets[planet_name] = {
                    "rasi": rasi,
                    "degrees": round(degrees, 2),
                    "sign_name": const.zodiac_list[rasi]
                }

            # Format planetary positions for D9
            d9_planets = {}
            for planet_index, (rasi, degrees) in d9_chart[1:]:
                planet_name = const.planet_list[planet_index]
                d9_planets[planet_name] = {
                    "rasi": rasi,
                    "degrees": round(degrees, 2),
                    "sign_name": const.zodiac_list[rasi]
                }

            return {
                "status": "success",
                "dob": dob,
                "tob": tob,
                "place": place,
                "ascendant": {
                    "rasi": ascendant[0],
                    "degrees": round(ascendant[1], 2),
                    "sign_name": const.zodiac_list[ascendant[0]]
                },
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

    # Alias for backwards compatibility
    get_birth_chart = calculate_birth_chart

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

            # Planet name mapping
            planet_names = {
                6: "Ketu",
                3: "Venus",
                0: "Sun",
                1: "Moon",
                2: "Mars",
                7: "Rahu",
                4: "Jupiter",
                5: "Saturn",
                8: "Mercury"
            }

            # Convert to list with dates
            dasha_periods = []
            lords_list = list(mahadashas.keys())

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
    def get_doshas(*args, **kwargs):
        return {"error": "Not implemented yet"}

    @staticmethod
    def get_yogas(*args, **kwargs):
        return {"error": "Not implemented yet"}

    @staticmethod
    def get_transits(*args, **kwargs):
        return {"error": "Not implemented yet"}

    @staticmethod
    def get_compatibility(*args, **kwargs):
        return {"error": "Not implemented yet"}

    @staticmethod
    def search_location(*args, **kwargs):
        return {"error": "Not implemented yet"}
