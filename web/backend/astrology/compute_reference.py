"""Reference/derived readings: bhrigu markers, remedies, nakshatra profile, Sarvatobhadra.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class ReferenceMixin:

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

    # ── Nadi karaka reading (significators + transit triggers) ──────────────
    @staticmethod
    def get_nadi_reading(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None, gender: Optional[int] = None,
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Nadi karaka reading of a birth chart.

        The Nadi karaka method reads the chart through the *karakas* (the fixed
        natural significators of the grahas) and their placement **by sign** —
        deliberately setting houses and aspects aside. Three devices are computed:

          1. **Karakas & significators** — for every graha: its naisargika
             significations, the sign it sits in (and that sign's lord =
             dispositor), its nakshatra and star-lord, the sign(s) it owns, and
             whom it is conjunct (planets sharing its sign). A graha *signifies*
             its occupied sign, the signs it owns, and its star-lord's sign.
          2. **Life themes** — each life area headed by its karaka, so the reader
             sees at a glance where (say) marriage or career is anchored.
          3. **Transit triggers** — the next ingress of the slow movers Jupiter,
             Saturn and Rahu into the pivotal karaka signs (Moon, Ascendant,
             marriage, career, children). In Nadi timing a slow graha entering a
             karaka's sign is what fructifies its events.

        `gender` (0 = male, 1 = female) only selects which spouse-karaka to
        foreground (Venus for a man, Jupiter for a woman); both are always shown.
        This is a traditional predictive aid, not a deterministic forecast."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
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
            lagna_sign0 = pp[0][1][0]
            # planet index -> (sign0, absolute longitude 0-360)
            ppos = {}
            for pid, (sign0, lon_in_sign) in pp[1:]:
                if pid in PLANET_NAMES:
                    ppos[pid] = (sign0, sign0 * 30.0 + lon_in_sign)

            # Star (nakshatra) lord per planet, and the sign each planet occupies.
            planet_sign0 = {pid: s for pid, (s, _l) in ppos.items()}
            star_lord_idx = {}
            nak_name = {}
            for pid, (_s, abslon) in ppos.items():
                kp = _kp_lords(pid if pid != 1 else 1, abslon)
                star_lord_idx[pid] = kp["star_lord_idx"]
                nak_i = int((abslon % 360.0) / (360.0 / 27.0)) % 27
                nak_name[pid] = NAKSHATRA_NAMES[nak_i]

            # Which signs each planet owns (0-based).
            owns0 = {pid: sorted(OWN_SIGNS.get(PLANET_NAMES[pid], set()))
                     for pid in ppos}
            # Conjunctions: planets sharing a sign.
            sign_members = {}
            for pid, s in planet_sign0.items():
                sign_members.setdefault(s, []).append(pid)

            karakas = []
            for pid in sorted(ppos):
                name = PLANET_NAMES[pid]
                s0 = planet_sign0[pid]
                sl_idx = star_lord_idx[pid]
                sl_sign0 = planet_sign0.get(sl_idx)
                # Signs this graha signifies: its own sign + owned + star-lord's sign.
                sig = []
                for x in [s0] + owns0[pid] + ([sl_sign0] if sl_sign0 is not None else []):
                    if x is not None and x not in sig:
                        sig.append(x)
                conj = [PLANET_NAMES[o] for o in sign_members.get(s0, []) if o != pid]
                karakas.append({
                    "planet": name,
                    "significations": NADI_KARAKAS.get(name, []),
                    "sign_name": ZODIAC_NAMES[s0],
                    "sign_lord": RASI_LORDS[s0],
                    "nakshatra": nak_name[pid],
                    "star_lord": PLANET_NAMES.get(sl_idx, str(sl_idx)),
                    "owns": [ZODIAC_NAMES[x] for x in owns0[pid]],
                    "conjunct": conj,
                    "signifies_signs": [ZODIAC_NAMES[x] for x in sig],
                })

            karaka_by_name = {k["planet"]: k for k in karakas}
            themes = []
            for area, planets in NADI_THEMES:
                themes.append({
                    "area": area,
                    "karakas": [
                        {"planet": p,
                         "sign_name": karaka_by_name[p]["sign_name"],
                         "sign_lord": karaka_by_name[p]["sign_lord"],
                         "conjunct": karaka_by_name[p]["conjunct"]}
                        for p in planets if p in karaka_by_name
                    ],
                })

            # ── Transit triggers ───────────────────────────────────────────
            # Coarse-scan (1-day steps — safe for slow grahas) then bisect to the
            # hour; capped at roughly one cycle of the transiting planet.
            def _next_sign_entry(pl_idx, jd_start, tgt_sign0, max_years):
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
                        lo, hi = jd0, jd1
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

            from datetime import datetime
            today = datetime.now()
            jd_now = swe.julday(today.year, today.month, today.day, 12)
            moon_sign0 = planet_sign0.get(1, lagna_sign0)
            venus_sign0 = planet_sign0.get(5, moon_sign0)
            saturn_sign0 = planet_sign0.get(6, moon_sign0)
            jup_sign0 = planet_sign0.get(4, moon_sign0)
            # Pivot signs → the karaka area they anchor (dedup, keep first label).
            pivots = [
                (moon_sign0, "Moon (mind)"),
                (lagna_sign0, "Ascendant (self)"),
                (venus_sign0, "Venus (marriage)"),
                (saturn_sign0, "Saturn (career)"),
                (jup_sign0, "Jupiter (children & fortune)"),
            ]
            seen_signs = {}
            for s0, label in pivots:
                seen_signs.setdefault(s0, label)

            triggers = []
            for pl_idx, pl_name, max_years in ((4, "Jupiter", 13), (6, "Saturn", 30),
                                               (7, "Rahu", 19)):
                for s0, label in seen_signs.items():
                    try:
                        ejd = _next_sign_entry(pl_idx, jd_now, s0, max_years)
                        if ejd is None:
                            continue
                        g = utils.jd_to_gregorian(ejd)
                        triggers.append({
                            "planet": pl_name,
                            "sign_name": ZODIAC_NAMES[s0],
                            "karaka": label,
                            "date": f"{g[0]:04d}-{g[1]:02d}-{g[2]:02d}",
                        })
                    except Exception:
                        pass
            triggers.sort(key=lambda x: x["date"])

            age_now = today.year - year - ((today.month, today.day) < (month, day))
            spouse_karaka = "Jupiter" if gender == 1 else "Venus"

            return {
                "status": "success",
                "dob": dob,
                "age_now": age_now,
                "ascendant": {"sign_name": ZODIAC_NAMES[lagna_sign0],
                              "sign_lord": RASI_LORDS[lagna_sign0]},
                "moon_sign": ZODIAC_NAMES[moon_sign0],
                "spouse_karaka": spouse_karaka,
                "karakas": karakas,
                "themes": themes,
                "triggers": triggers,
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

            # ── Every graha's own nakshatra, not just the Moon's ───────────
            # The janma star above is the Moon's; but each graha also sits in a
            # star, and a graha delivers its results coloured by that star's lord
            # (this is why the star lord, not the sign lord, drives Vimsottari).
            # Nothing read this until now, so the whole nakshatra layer of the
            # chart was invisible outside KP's own framing.
            planetary = []
            for row in natal:
                pid = row[0]
                rasi, deg = row[1]
                if pid == "L":
                    label = "Lagna"
                elif pid in PLANET_NAMES:
                    label = PLANET_NAMES[pid]
                else:
                    continue
                lon_abs = rasi * 30.0 + deg
                nak_i = int(lon_abs / nak_span)
                nak_pada = int((lon_abs % nak_span) / (nak_span / 4.0)) + 1
                planetary.append({
                    "planet": label,
                    "sign_name": ZODIAC_NAMES[rasi],
                    "nakshatra": NAKSHATRA_NAMES[nak_i],
                    "nakshatra_index": nak_i + 1,
                    "pada": nak_pada,
                    "lord": refdata.NAKSHATRA_LORD[nak_i],
                    "deity": refdata.NAKSHATRA_DEITY[nak_i],
                    "symbol": refdata.NAKSHATRA_SYMBOL[nak_i],
                    "theme": refdata.NAKSHATRA_THEME[nak_i],
                    "is_janma": nak_i == janma_nak and label == "Moon",
                })

            return {
                "status": "success",
                "profile": profile,
                "moon_sign": ZODIAC_NAMES[moon_rasi],
                "planetary_nakshatras": planetary,
                "tarabala_calendar": calendar,
                "calendar_from": f"{cy:04d}-{cm:02d}-{cd:02d}",
            }
        except Exception as e:
            print(f"Nakshatra profile error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_kota_chakra(dob: str, tob: str, place: str,
                        lat: Optional[float] = None, lon: Optional[float] = None,
                        tz: Optional[float] = None,
                        current_date: Optional[str] = None, current_time: Optional[str] = None,
                        current_tz: Optional[float] = None,
                        ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Kota Chakra — the fort — with the current transits marked (§2.7).

        The 28 nakshatras are laid out as four concentric enclosures counted from
        the janma nakshatra: Baahya (outer wall), Praakaara (rampart), Durgantara
        (inner fort) and Sthamba (the central pillar). Classical use is protection
        / health: a malefic transiting *into* the inner rings threatens the fort,
        a benefic there defends it. The **Kota Swami** (lord of the Moon's sign)
        defends, and the **Kota Paala** (from the janma star + pada) guards.

        Ported from the engine's PyQt-only `ui.chakra.KotaChakra` — there is no
        headless entry point — reusing its constant tables verbatim
        (`abhijit_order_of_stars`, `kota_chakra_star_placement_from_birth_star`,
        `kota_paala_lord_for_star_paadha`) so the layout matches desktop JHora.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from datetime import datetime

            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            natal_jd = swe.julday(year, month, day, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)

            # Janma nakshatra + pada from the natal Moon.
            moon_rasi, moon_long = natal[2][1]
            birth_star, birth_pada = drik.nakshatra_pada(moon_rasi * 30.0 + moon_long)[:2]

            # Kota Swami: lord of the sign the Moon occupies. Kota Paala: the
            # engine's janma-star x pada guard table.
            kota_lord = RASI_LORDS[moon_rasi]
            kota_paala = PLANET_NAMES.get(
                const.kota_paala_lord_for_star_paadha[birth_star - 1][birth_pada - 1], "—")

            # ── The fort's cells ────────────────────────────────────────────
            # Stars in Abhijit order, then each ring's cells offset from the
            # janma star (the engine's exact indexing, so we match JHora).
            star_order = [NAKSHATRA_NAMES_28[i] for i in const.abhijit_order_of_stars]
            grid = [
                [star_order[((birth_star - 1) + (ele - 1)) % 28] for ele in row]
                for row in const.kota_chakra_star_placement_from_birth_star
            ]

            # ── Transit moment ─────────────────────────────────────────────
            if current_date:
                ty, tm, td = map(int, current_date.split("-"))
            else:
                now = _now_at_tz(current_tz if current_tz is not None else tz_offset)
                ty, tm, td = now.year, now.month, now.day
            if current_time:
                tt = current_time.split(":")
                t_hour = int(tt[0]); t_min = int(tt[1]) if len(tt) > 1 else 0
            else:
                t_hour, t_min = 12, 0
            transit_tz = current_tz if current_tz is not None else tz_offset
            transit_place = drik.Place(place, lat, lon, transit_tz)
            transit_jd = swe.julday(ty, tm, td, t_hour + t_min / 60.0)
            transit = charts.rasi_chart(transit_jd, transit_place)
            retro = set(drik.planets_in_retrograde(transit_jd, transit_place))

            def _star_of(rasi, deg):
                return drik.nakshatra_pada(rasi * 30.0 + deg)[0]

            # Which cell (ring, index) holds a given nakshatra number (1-27)?
            def _cell_of(nak):
                name = NAKSHATRA_NAMES[nak - 1]
                for ri, row in enumerate(grid):
                    for ci, star in enumerate(row):
                        if star == name:
                            return ri, ci
                return None

            natal_at = {}
            for pid, (rasi, deg) in natal[1:]:
                nm = PLANET_NAMES.get(pid)
                if not nm:
                    continue
                cell = _cell_of(_star_of(rasi, deg))
                if cell:
                    natal_at.setdefault(cell, []).append(nm)

            transit_at = {}
            for pid, (rasi, deg) in transit[1:]:
                nm = PLANET_NAMES.get(pid)
                if not nm:
                    continue
                cell = _cell_of(_star_of(rasi, deg))
                if cell:
                    transit_at.setdefault(cell, []).append(
                        {"name": nm, "retrograde": pid in retro,
                         "malefic": nm in KOTA_MALEFICS})

            rings = []
            for ri, (key, label, blurb) in enumerate(KOTA_RINGS):
                cells = []
                for ci, star in enumerate(grid[ri]):
                    cells.append({
                        "star": star,
                        "natal": natal_at.get((ri, ci), []),
                        "transit": transit_at.get((ri, ci), []),
                    })
                rings.append({"key": key, "name": label, "description": blurb,
                              "cells": cells})

            # ── Findings ───────────────────────────────────────────────────
            findings = []
            for ri, (key, label, _b) in enumerate(KOTA_RINGS):
                mal = [p["name"] for ci in range(len(grid[ri]))
                       for p in transit_at.get((ri, ci), []) if p["malefic"]]
                ben = [p["name"] for ci in range(len(grid[ri]))
                       for p in transit_at.get((ri, ci), []) if not p["malefic"]]
                if mal:
                    findings.append({
                        "ring": key, "tone": "stressful" if ri >= 2 else "watch",
                        "text": f"{', '.join(mal)} transiting {label}"
                                + (" — the fort's core is under pressure."
                                   if ri == 3 else
                                   " — malefic pressure on the inner fort."
                                   if ri == 2 else "."),
                    })
                if ben:
                    findings.append({
                        "ring": key, "tone": "supportive",
                        "text": f"{', '.join(ben)} transiting {label} — protective.",
                    })
            # The defenders' own transit position is the classical headline.
            for role, planet in (("Kota Swami (defender)", kota_lord),
                                 ("Kota Paala (guard)", kota_paala)):
                for ri in range(len(grid)):
                    for ci in range(len(grid[ri])):
                        if any(p["name"] == planet for p in transit_at.get((ri, ci), [])):
                            findings.append({
                                "ring": KOTA_RINGS[ri][0], "tone": "note",
                                "text": f"{role} {planet} is in {KOTA_RINGS[ri][1]}.",
                            })

            return {
                "status": "success",
                "birth_star": {"number": birth_star,
                               "name": NAKSHATRA_NAMES[birth_star - 1],
                               "pada": birth_pada},
                "moon_sign": ZODIAC_NAMES[moon_rasi],
                "kota_lord": kota_lord,
                "kota_paala": kota_paala,
                "transit_date": f"{ty:04d}-{tm:02d}-{td:02d}",
                "rings": rings,
                "findings": findings,
            }
        except Exception as e:
            print(f"Kota chakra error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_kaala_chakra(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None,
                         current_date: Optional[str] = None, current_time: Optional[str] = None,
                         current_tz: Optional[float] = None,
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Kaala Chakra — the wheel of directions, with the transits on it (§2.7).

        The 28 stars (Abhijit included) are laid out as 4 inner stars around the
        hub and 8 outer divisions of 3 stars, counted from a **base star**. Each
        outer division IS a compass direction, so a graha landing on one colours
        that direction — the classical use is choosing which way to travel or act.

        Base star: the engine's rule is the **Sun's** nakshatra for the Rasi (D1)
        chart (the Lagna's star is used for vargas, which we don't offer here).

        Ported from the engine's PyQt-only `ui.chakra.KaalaChakra`; the offsets,
        the direction order and the Abhijit slot-shift are its own.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from datetime import datetime

            y, mo, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            natal_jd = swe.julday(y, mo, d, hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)

            # Base star = the natal Sun's nakshatra (the D1 rule).
            sun_rasi, sun_deg = natal[1][1]
            base_star = drik.nakshatra_pada(sun_rasi * 30.0 + sun_deg)[0]

            # ── Transit moment ─────────────────────────────────────────────
            if current_date:
                ty, tm, td = map(int, current_date.split("-"))
            else:
                now = _now_at_tz(current_tz if current_tz is not None else tz_offset)
                ty, tm, td = now.year, now.month, now.day
            if current_time:
                tt = current_time.split(":")
                t_hour = int(tt[0]); t_min = int(tt[1]) if len(tt) > 1 else 0
            else:
                t_hour, t_min = 12, 0
            transit_tz = current_tz if current_tz is not None else tz_offset
            transit_place = drik.Place(place, lat, lon, transit_tz)
            transit_jd = swe.julday(ty, tm, td, t_hour + t_min / 60.0)
            transit = charts.rasi_chart(transit_jd, transit_place)
            retro = set(drik.planets_in_retrograde(transit_jd, transit_place))

            star_order = [NAKSHATRA_NAMES_28[i] for i in const.abhijit_order_of_stars]

            def _slot(ele):
                return ((base_star - 1) + (ele - 1)) % 28

            inner_slots = [_slot(e) for e in KAALA_INNER_STARS]
            outer_slots = [[_slot(e) for e in row] for row in KAALA_OUTER_DIVISIONS]

            # Grahas by 28-star slot.
            at_slot = {}
            for pid, (rasi, deg) in transit[1:]:
                nm = PLANET_NAMES.get(pid)
                if not nm:
                    continue
                nak = drik.nakshatra_pada(rasi * 30.0 + deg)[0]
                at_slot.setdefault(kaala_star_slot(nak), []).append(
                    {"name": nm, "retrograde": pid in retro,
                     "malefic": nm in KOTA_MALEFICS})

            inner = [{"star": star_order[s], "angle": a,
                      "planets": at_slot.get(s, [])}
                     for s, a in zip(inner_slots, KAALA_INNER_ANGLES)]

            directions = []
            for i, slots in enumerate(outer_slots):
                cells = [{"star": star_order[s], "planets": at_slot.get(s, [])}
                         for s in slots]
                occupants = [p for c in cells for p in c["planets"]]
                mal = [p["name"] for p in occupants if p["malefic"]]
                ben = [p["name"] for p in occupants if not p["malefic"]]
                if mal and not ben:
                    tone = "stressful"
                elif ben and not mal:
                    tone = "supportive"
                elif mal and ben:
                    tone = "mixed"
                else:
                    tone = "clear"
                directions.append({
                    "direction": KAALA_DIRECTIONS[i],
                    "angle": KAALA_OUTER_ANGLES[i],
                    "cells": cells,
                    "malefics": mal,
                    "benefics": ben,
                    "tone": tone,
                })

            best = [d["direction"] for d in directions if d["tone"] == "supportive"]
            avoid = [d["direction"] for d in directions if d["tone"] == "stressful"]

            return {
                "status": "success",
                "transit_date": f"{ty:04d}-{tm:02d}-{td:02d}",
                "base_star": {"number": base_star,
                              "name": NAKSHATRA_NAMES[base_star - 1],
                              "from": "Sun"},
                "inner": inner,
                "directions": directions,
                "favourable": best,
                "avoid": avoid,
            }
        except Exception as e:
            print(f"Kaala chakra error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_tripataki_chakra(dob: str, tob: str, place: str,
                             lat: Optional[float] = None, lon: Optional[float] = None,
                             tz: Optional[float] = None,
                             current_date: Optional[str] = None, current_time: Optional[str] = None,
                             current_tz: Optional[float] = None,
                             basis: str = "transit", year: Optional[int] = None,
                             ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Tripataki Chakra — the twelve rasis on the three-banner diagram (§2.7).

        The rasis sit around a 5x5 grid crossed by the three *pataki* (banner)
        lines; each graha is plotted on the sign it occupies, natal and transiting.

        The chakra's point is **vedha** (obstruction). The engine ships only the
        drawing, so the rules are implemented here from the Tajaka literature:
        a movable sign has vedha with the dual signs except the dual in the 3rd
        from it; a fixed sign with the other fixed signs; a dual sign with the
        movable signs except the movable in the 11th from it (see
        `_tripataki_vedha_map`). Customarily the vedha is read **on the Moon and
        the Lagna**, which is what `vedha` reports.

        `basis` picks the chart the vedha is read on:
          • "transit" (default) — the chart for `current_date`/`current_time`,
            consistent with the other (transit-based) chakras on the page. The
            Lagna judged is the natal one.
          • "annual" — the **Varshaphal / Tajaka** chart: the solar return for
            `year` (defaults to the current year). This is Tripataki's classical
            home, so the Lagna judged is the *varsha* (annual) Lagna and the Moon
            is the annual chart's Moon.

        NOT IMPLEMENTED, deliberately: some Tajaka sources describe a further
        progression for Tripataki (remainders of the elapsed years ÷9, ÷4 and ÷6
        moving each graha from its natal place). The sources found for it are thin
        and disagree, so it is not guessed at here — "annual" means the real solar-
        return chart, which is well defined.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            _set_ayanamsa(ayanamsa)
            from datetime import datetime

            # NB: birth parts are named explicitly — `year` is the *target* year
            # parameter for basis="annual", so the birth year must not shadow it.
            birth_year, birth_month, birth_day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            natal_jd = swe.julday(birth_year, birth_month, birth_day,
                                  hour + minute / 60.0)
            natal = charts.rasi_chart(natal_jd, place_obj)
            natal_lagna = natal[0][1][0]

            if current_date:
                ty, tm, td = map(int, current_date.split("-"))
            else:
                now = _now_at_tz(current_tz if current_tz is not None else tz_offset)
                ty, tm, td = now.year, now.month, now.day
            if current_time:
                tt = current_time.split(":")
                t_hour = int(tt[0]); t_min = int(tt[1]) if len(tt) > 1 else 0
            else:
                t_hour, t_min = 12, 0

            basis = (basis or "transit").lower()
            if basis not in ("transit", "annual"):
                return {"error": f"Unknown basis '{basis}' (use transit|annual)",
                        "status": "failed"}

            if basis == "annual":
                # Imported here (not in engine.py) to match get_varshaphal, which
                # pulls the tajaka module in locally.
                from jhora.horoscope.transit import tajaka
                # Varshaphal (solar-return) chart — Tripataki's classical home.
                # NOTE the engine quirk (same as get_varshaphal): varsha_pravesh
                # (years=N) returns the solar return in birth_year+N-1, so the
                # chart for `year` needs years = age + 1.
                target_year = year or ty
                age = target_year - birth_year
                if age < 0:
                    return {"error": "Year is before the birth year", "status": "failed"}
                transit, entry = tajaka.varsha_pravesh(
                    natal_jd, place_obj, divisional_chart_factor=1, years=age + 1)
                (ey, em, ed), _etime = entry
                basis_date = f"{ey:04d}-{em:02d}-{ed:02d}"
                # The annual chart's own Lagna is what the vedha is read on.
                judged_lagna = transit[0][1][0]
                retro = set()
            else:
                transit_tz = current_tz if current_tz is not None else tz_offset
                transit_place = drik.Place(place, lat, lon, transit_tz)
                transit_jd = swe.julday(ty, tm, td, t_hour + t_min / 60.0)
                transit = charts.rasi_chart(transit_jd, transit_place)
                retro = set(drik.planets_in_retrograde(transit_jd, transit_place))
                basis_date = f"{ty:04d}-{tm:02d}-{td:02d}"
                judged_lagna = natal_lagna

            natal_by_sign = {}
            for pid, (rasi, _deg) in natal[1:]:
                nm = PLANET_NAMES.get(pid)
                if nm:
                    natal_by_sign.setdefault(rasi, []).append(nm)

            transit_by_sign = {}
            for pid, (rasi, _deg) in transit[1:]:
                nm = PLANET_NAMES.get(pid)
                if nm:
                    transit_by_sign.setdefault(rasi, []).append(
                        {"name": nm, "retrograde": pid in retro})

            # ── Vedha on the Moon and the Lagna (the customary reading) ─────
            # The Lagna judged is the natal one (the chakra is cast on it); the
            # Moon is the transiting Moon, which is what moves the picture.
            transit_moon_sign = transit[2][1][0]
            targets = {
                "Moon": transit_moon_sign,
                "Lagna": judged_lagna,
            }
            vedha = []
            for label, tsign in targets.items():
                obstructing = TRIPATAKI_VEDHA[tsign]
                hits = []
                for pid, (rasi, _deg) in transit[1:]:
                    nm = PLANET_NAMES.get(pid)
                    # A graha can't obstruct the point it sits with, and the Moon
                    # doesn't vedha itself.
                    if not nm or nm == label or rasi not in obstructing:
                        continue
                    hits.append({"planet": nm, "from_sign": ZODIAC_NAMES[rasi],
                                 "benefic": nm in HORA_BENEFICS})
                vedha.append({
                    "target": label,
                    "sign": ZODIAC_NAMES[tsign],
                    "sign_class": sign_class(tsign),
                    "obstructed_by": hits,
                    "vedha_signs": sorted(ZODIAC_NAMES[s] for s in obstructing),
                    "tone": ("stressful" if any(not h["benefic"] for h in hits)
                             else "supportive" if hits else "clear"),
                })

            # Signs that can obstruct either target — so the UI can mark them.
            vedha_signs = set()
            for v in vedha:
                vedha_signs |= {s for s in TRIPATAKI_VEDHA[targets[v["target"]]]}

            cells = []
            for sign, (x, y) in enumerate(TRIPATAKI_RASI_POSITIONS):
                cells.append({
                    "sign": sign + 1,
                    "sign_name": ZODIAC_NAMES[sign],
                    "x": x, "y": y,
                    "is_lagna": sign == judged_lagna,
                    "is_moon": sign == transit_moon_sign,
                    "sign_class": sign_class(sign),
                    "casts_vedha": sign in vedha_signs,
                    "house_from_lagna": ((sign - judged_lagna) % 12) + 1,
                    "natal": natal_by_sign.get(sign, []),
                    "transit": transit_by_sign.get(sign, []),
                })

            lines = [{"from": [sx, sy], "to": [ex, ey]}
                     for (sx, sy), ends in TRIPATAKI_LINES.items()
                     for (ex, ey) in ends]

            return {
                "status": "success",
                "basis": basis,
                "transit_date": basis_date,
                "natal_lagna": ZODIAC_NAMES[judged_lagna],
                "transit_moon": ZODIAC_NAMES[transit_moon_sign],
                "grid": {"width": 5, "height": 5},
                "cells": cells,
                "lines": lines,
                "vedha": vedha,
            }
        except Exception as e:
            print(f"Tripataki chakra error: {e}")
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
                now = _now_at_tz(current_tz if current_tz is not None else tz_offset)
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
