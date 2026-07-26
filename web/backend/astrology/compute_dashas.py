"""Dasha systems: Vimsottari chain/children, alternate systems, life timeline.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class DashasMixin:

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
            elif dhasa_type == "shashtihayani":
                rows = shastihayani.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "chaturaaseeti_sama":
                rows = chathuraaseethi_sama.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
            elif dhasa_type == "dwisatpathi":
                rows = dwisatpathi.get_dhasa_bhukthi(dob_t, tob_t, place_obj, dhasa_level_index=1)
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
            # ── Chakra dasha (§2.7) ───────────────────────────────────────
            elif dhasa_type == "sudharsana_chakra":
                # 12-year wheel × 9 cycles = 108 one-year periods.
                rows = sudharsana_chakra.get_dhasa_bhukthi(
                    jd, place_obj, dhasa_level_index=1, dhasa_cycles=9)
            else:
                return {"error": f"Unsupported dhasa type: {dhasa_type}", "status": "failed"}

            names = ZODIAC_NAMES if meta["lord_type"] == "raasi" else None

            # Sudarshana Chakra's "lord" is a triple of houses counted from three
            # different reference points, so it needs the natal Lagna/Moon/Sun signs
            # to name the rasi each wheel is running through.
            chakra_refs = None
            if meta["lord_type"] == "chakra":
                _pp = charts.rasi_chart(jd, place_obj)
                chakra_refs = {
                    "lagna": _pp[0][1][0],   # ascendant sign
                    "moon": _pp[2][1][0],    # row 2 = Moon
                    "sun": _pp[1][1][0],     # row 1 = Sun
                }

            def _chakra_period(raw):
                """Engine triple -> the active rasi + house on each wheel.

                NOTE the engine's naming is misleading: in `sudharshana_chakra_chart`
                the triple's members are `planet_positions[i][1][0]` — 0-based **sign
                indices**, not house numbers (despite being called `*_house`). So the
                triple IS the active rasi of each wheel; the house is derived by
                counting it from that wheel's natal reference sign.
                """
                triple = raw[0] if isinstance(raw, (tuple, list)) else raw
                out = {}
                for key, sign in zip(("lagna", "moon", "sun"), (int(x) for x in triple)):
                    sign %= 12
                    house = ((sign - chakra_refs[key]) % 12) + 1
                    out[key] = {"house": house, "sign": ZODIAC_NAMES[sign]}
                return out

            def _lord_name(raw):
                if chakra_refs is not None:
                    c = _chakra_period(raw)
                    return " · ".join(c[k]["sign"] for k in ("lagna", "moon", "sun"))
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
                entry = {
                    "lord": _lord_name(lord_raw),
                    "start_date": _fmt(start_t),
                    "end_date": _fmt(end_t),
                    "duration_years": round(float(dur), 2),
                }
                if chakra_refs is not None:
                    # Per-wheel house+rasi, so the UI can show all three columns.
                    entry["chakra"] = _chakra_period(lord_raw)
                periods.append(entry)

            out = {
                "status": "success",
                "dhasa_type": dhasa_type,
                "name": meta["name"],
                "lord_type": meta["lord_type"],
                "description": meta["description"],
                "periods": periods,
            }
            if chakra_refs is not None:
                # The three natal reference signs each wheel counts from.
                out["chakra_refs"] = {
                    k: ZODIAC_NAMES[v] for k, v in chakra_refs.items()
                }
            return out
        except Exception as e:
            print(f"Dasha periods error ({dhasa_type}): {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    # The BPHS conditional nakshatra dashas the engine can test for applicability,
    # mapped to (display name, when-it-applies blurb, DhasaPage picker key or None).
    _APPLICABLE_DASHA_INFO = {
        "ashtottari": ("Ashtottari",
                       "108-year cycle; classically applies when Rahu is in a "
                       "quadrant/trine from a night-birth Lagna lord (and similar).",
                       "ashtottari"),
        "chaturaaseeti_sama": ("Chaturaaseeti Sama",
                               "84-year cycle; applies when the 10th lord is in the 10th house.",
                               "chaturaaseeti_sama"),
        "dwadasottari": ("Dwadasottari",
                         "112-year cycle; applies from a Lagna in Venus's hora (D9-based).",
                         "dwadasottari"),
        "dwisatpathi": ("Dwisatpathi",
                        "112-year cycle; applies when the Lagna is in its own or the 7th nakshatra pada.",
                        "dwisatpathi"),
        "panchottari": ("Panchottari",
                        "105-year cycle; applies from a Cancer Lagna condition (D12-based).",
                        "panchottari"),
        "satabdika": ("Shatabdika",
                      "100-year cycle; applies when the Lagna is in Vargottama at a specific pada.",
                      "shatabdika"),
        "shashtisama": ("Shashtihayani (Shashti-sama)",
                        "60-year cycle; applies when the Sun is in the Lagna.",
                        "shashtihayani"),
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
