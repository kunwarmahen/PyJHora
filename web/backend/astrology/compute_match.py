"""Compatibility (Ashtakoot/Dashakoota/Mangal) and the marriage workspace.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class MatchMixin:

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
    def _marriage_person_analysis(jd: float, place_obj) -> Dict:
        """7th-house (marriage) deep-dive for one chart (§2.6 workspace).

        Reports the 7th sign + its lord's condition/placement, the occupants of
        the 7th, the two spouse karakas (Venus = kalatra/wife, Jupiter = husband)
        with dignity + navamsa sign, and the Upapada Lagna (UL) — the classical
        marriage arudha. Pure read-off of the natal Rasi + Navamsa; no new engine
        work, just the marriage-relevant slice surfaced in one place."""
        pp = charts.rasi_chart(jd, place_obj)
        d9 = charts.divisional_chart(jd, place_obj, divisional_chart_factor=9)
        # planet index -> sign, for D1 and D9.
        d1_sign = {pid: s for pid, (s, _l) in pp[1:] if pid in PLANET_NAMES}
        d9_sign = {pid: s for pid, (s, _l) in d9[1:] if pid in PLANET_NAMES}
        idx_of = {name: pid for pid, name in PLANET_NAMES.items()}
        retro = set(drik.planets_in_retrograde(jd, place_obj))

        lagna = pp[0][1][0]
        seventh_sign = (lagna + 6) % 12

        def _dignity(name, sign0):
            if sign0 is None:
                return "—"
            ex = EXALTATION_SIGN.get(name)
            if ex is not None:
                if sign0 == ex:
                    return "exalted"
                if sign0 == (ex + 6) % 12:
                    return "debilitated"
            if sign0 in OWN_SIGNS.get(name, set()):
                return "own sign"
            return "neutral"

        def _planet_condition(name):
            pid = idx_of.get(name)
            s = d1_sign.get(pid)
            if s is None:
                return None
            return {
                "sign": ZODIAC_NAMES[s],
                "house": ((s - lagna) % 12) + 1,
                "dignity": _dignity(name, s),
                "retrograde": pid in retro,
                "navamsa_sign": ZODIAC_NAMES[d9_sign[pid]] if pid in d9_sign else "—",
            }

        seventh_lord = RASI_LORDS[seventh_sign]
        occupants = [
            {"name": PLANET_NAMES[pid],
             "dignity": _dignity(PLANET_NAMES[pid], s),
             "retrograde": pid in retro}
            for pid, s in sorted(d1_sign.items())
            if s == seventh_sign
        ]

        # Upapada Lagna = arudha of the 12th bhava.
        upapada = None
        try:
            ba = arudhas.bhava_arudhas_from_planet_positions(pp)
            ul_sign = int(ba[11]) % 12
            upapada = {"sign": ZODIAC_NAMES[ul_sign], "lord": RASI_LORDS[ul_sign]}
        except Exception as ue:
            print(f"Marriage UL error: {ue}")

        return {
            "lagna_sign": ZODIAC_NAMES[lagna],
            "seventh_sign": ZODIAC_NAMES[seventh_sign],
            "seventh_lord": seventh_lord,
            "seventh_lord_condition": _planet_condition(seventh_lord),
            "occupants": occupants,
            "karakas": {
                "Venus": _planet_condition("Venus"),
                "Jupiter": _planet_condition("Jupiter"),
            },
            "upapada": upapada,
        }

    @staticmethod
    def get_marriage_workspace(male_dob: str, male_tob: str, male_place: str,
                               female_dob: str, female_tob: str, female_place: str,
                               male_lat: Optional[float] = None, male_lon: Optional[float] = None,
                               female_lat: Optional[float] = None, female_lon: Optional[float] = None,
                               male_tz: Optional[float] = None, female_tz: Optional[float] = None,
                               ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """The marriage/relationship workspace 7th-house layer (§2.6).

        Returns the 7th-house deep-dive for both partners in one payload. The
        dasha-overlap timeline and the shared Saturn-transit outlook are composed
        on the frontend from the existing dasha + saturn-transit endpoints (both
        partners), and the side-by-side D1/D9 charts come from the birth-chart
        endpoint — so this method owns only the marriage-specific analysis that
        nothing else exposes."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)

            def _jd_place(dob, tob, place, lat, lon, person_tz):
                y, m, d = map(int, dob.split("-"))
                tp = tob.split(":")
                hh = int(tp[0]); mm = int(tp[1]) if len(tp) > 1 else 0
                if not lat or not lon:
                    lat, lon = 13.0827, 80.2707
                jd = swe.julday(y, m, d, hh + mm / 60.0)
                return jd, drik.Place(place, lat, lon,
                                      person_tz if person_tz is not None else 5.5)

            m_jd, m_place = _jd_place(male_dob, male_tob, male_place,
                                      male_lat, male_lon, male_tz)
            f_jd, f_place = _jd_place(female_dob, female_tob, female_place,
                                      female_lat, female_lon, female_tz)

            return {
                "status": "success",
                "seventh_house": {
                    "male": AstrologyCompute._marriage_person_analysis(m_jd, m_place),
                    "female": AstrologyCompute._marriage_person_analysis(f_jd, f_place),
                },
            }
        except Exception as e:
            print(f"Marriage workspace error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)
