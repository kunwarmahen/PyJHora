"""Sensitive points: sphutas, sahams, argala.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class PointsMixin:

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
    def get_special_points(dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None,
                           ayanamsa: str = DEFAULT_AYANAMSA,
                           varnada_method: int = DEFAULT_VARNADA_METHOD) -> Dict:
        """One consolidated table of every non-planetary sensitive longitude, in
        the same shape Jagannatha Hora prints them: the special lagnas (four
        time-based kaala lagnas + five point-derived + Varnada), the upagrahas
        (six kaala-velas + five solar), Varnada V1..V12 and the Sphutas.

        `interpreted` names the subset that carries enough classical rule-weight
        to narrate — everything else is reference data and must not be given a
        verdict it has no basis for.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        details = AstrologyCompute.get_chart_details(
            dob, tob, place, lat, lon, tz, ayanamsa, varnada_method)
        if details.get("status") != "success":
            return details
        sphuta = AstrologyCompute.get_sphuta(dob, tob, place, lat, lon, tz, ayanamsa)
        return {
            "status": "success",
            "lagna_sign": details.get("lagna_sign"),
            "lagna_sign_name": details.get("lagna_sign_name"),
            "special_lagnas": details.get("special_lagnas", []),
            "upagrahas": details.get("upagrahas", []),
            "varnadas": details.get("varnadas", []),
            "varnada_method": details.get("varnada_method"),
            "varnada_method_name": details.get("varnada_method_name"),
            "sphutas": (sphuta or {}).get("sphutas", []),
            "interpreted": list(INTERPRETED_SPECIAL_LAGNAS) + ["Gulika"],
            "note": ("Hora Lagna governs wealth and income (judge the 2nd and 11th "
                     "from it), Ghati Lagna governs power and authority (judge the "
                     "10th from it), Bhava Lagna the body — these three are read as "
                     "a trio. Varnada Lagna gives the chart's overall direction and "
                     "Gulika marks chronic difficulty. The remaining points are "
                     "reference data with no settled predictive rule; report their "
                     "positions but do not invent verdicts from them. Vighati Lagna "
                     "moves a full sign every four minutes and is meaningless unless "
                     "the birth time is accurate to the second."),
        }

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
