"""Natal, divisional (varga), bhava and derived chart computations.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class ChartsMixin:

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
    def get_arudha_analysis(dob: str, tob: str, place: str,
                            lat: Optional[float] = None, lon: Optional[float] = None,
                            tz: Optional[float] = None,
                            ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Bhava arudhas *with the structure an actual reading needs*.

        `get_arudha_padas` answers only "which sign is AL in?" — enough to label a
        chart cell, far too thin to interpret. This adds, per arudha: the sign lord
        and where it sits, the planets **occupying** the arudha, the planets casting
        **rasi drishti** (Jaimini sign-aspect — the drishti arudhas are judged by),
        and which house from the Lagna the arudha falls in.

        On top of that it derives the houses *counted from AL and UL* that classical
        practice actually reads — 2nd/10th/11th/12th from AL, 2nd/7th from UL — since
        an arudha's meaning comes from what surrounds it, not from its sign alone.
        Each derived house carries its classical signification as `signifies`; the
        occupants/aspects are computed, the verdict is left to the reader.
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
            lagna_sign = pp[0][1][0]
            padas = _format_arudha_padas(arudhas.bhava_arudhas_from_planet_positions(pp))

            # sign occupied by each graha in the D1, and the house→planets map the
            # rasi-drishti helper wants.
            d1_sign = {pid: sign for pid, (sign, _l) in pp[1:] if pid in PLANET_NAMES}
            h2p = utils.get_house_planet_list_from_planet_positions(pp)

            def _occupants(sign):
                return [PLANET_NAMES[pid] for pid, s in d1_sign.items() if s == sign]

            def _aspects(sign):
                return [PLANET_NAMES.get(int(p), str(p))
                        for p in house.aspected_planets_of_the_raasi(h2p, sign)]

            def _cell(sign, **extra):
                """The shared shape for any sign we describe: name, who sits there,
                who aspects it, and which house from the Lagna it is."""
                sign = sign % 12
                return {
                    "sign": sign + 1,
                    "sign_name": ZODIAC_NAMES[sign],
                    "occupants": _occupants(sign),
                    "aspecting_planets": _aspects(sign),
                    "house_from_lagna": ((sign - lagna_sign) % 12) + 1,
                    **extra,
                }

            enriched = []
            for p in padas:
                sign = p["sign"] - 1          # _format_arudha_padas returns 1-based
                lord = SIGN_LORD[sign]
                lord_sign = d1_sign.get(lord)
                enriched.append({
                    **p,
                    **_cell(sign),
                    "lord": PLANET_NAMES.get(lord, str(lord)),
                    "lord_sign_name": (ZODIAC_NAMES[lord_sign % 12]
                                       if lord_sign is not None else "—"),
                    # Where the lord sits *relative to its own arudha* — the standard
                    # way to judge whether the arudha is supported or undermined.
                    "lord_house_from_arudha": (((lord_sign - sign) % 12) + 1
                                               if lord_sign is not None else None),
                    "lord_house_from_lagna": (((lord_sign - lagna_sign) % 12) + 1
                                              if lord_sign is not None else None),
                })

            by_short = {p["short"]: p for p in padas}
            al_sign = by_short["AL"]["sign"] - 1
            ul_sign = by_short["UL"]["sign"] - 1

            # Classical significations of the houses counted FROM an arudha. These are
            # the standard readings (the 12th from AL as the seat of loss/expenditure
            # and detachment is the best-known); we supply the signification and the
            # occupants, and let the reading do the interpreting.
            al_derived = [
                _cell(al_sign + 1, house_from_al=2,
                      signifies="sustenance and the income that supports the image"),
                _cell(al_sign + 9, house_from_al=10,
                      signifies="public role and standing in work"),
                _cell(al_sign + 10, house_from_al=11,
                      signifies="gains, networks and what accrues to the image"),
                _cell(al_sign + 11, house_from_al=12,
                      signifies="loss, expenditure and detachment from the image "
                                "(benefics here read as giving away, malefics as erosion)"),
            ]
            ul_derived = [
                _cell(ul_sign + 1, house_from_ul=2,
                      signifies="the sustenance and durability of the marriage"),
                _cell(ul_sign + 6, house_from_ul=7,
                      signifies="how the partnership meets the wider world"),
            ]

            return {
                "status": "success",
                "lagna": {"sign": lagna_sign + 1, "sign_name": ZODIAC_NAMES[lagna_sign]},
                "arudhas": enriched,
                "al_derived": al_derived,
                "ul_derived": ul_derived,
                "note": ("AL = Arudha Lagna (the perceived self/image/status, maya), "
                         "UL = Upapada (spouse/marriage); A2..A11 are the arudhas of "
                         "houses 2-11. Aspects are Jaimini rasi drishti (sign aspect), "
                         "which is the drishti arudhas are judged by."),
            }
        except Exception as e:
            print(f"Arudha analysis error: {str(e)}")
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
