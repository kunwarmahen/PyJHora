"""Krishnamurti Paddhati (sub-lords, significators, horary) and Jaimini.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class KpMixin:

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
