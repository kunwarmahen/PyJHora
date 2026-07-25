"""Electional astrology: muhurta windows, day sub-tools, prashna, pancha pakshi.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class MuhurtaMixin:

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

                    # Kaala-velas annotate rather than exclude. They are eighth-parts
                    # of the same day as Rahu Kalam / Yamaganda / Gulika and often
                    # coincide with them; barring all of them would rule out most of
                    # every day, which no muhurta tradition does. So a window that
                    # falls inside one is still offered, with the caution attached.
                    kaala_velas = [
                        (kv.get("name"), _to_min(kv.get("start")), _to_min(kv.get("end")))
                        for kv in (panch.get("kaala_velas") or [])
                    ]

                    def _kaala_vela_caution(w1, w2):
                        hits = [n for n, s, e in kaala_velas
                                if s is not None and e is not None and w1 < e and s < w2]
                        return ", ".join(hits) if hits else None

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
                                "kaala_vela": _kaala_vela_caution(a1, a2),
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
                            "kaala_vela": _kaala_vela_caution(h1, h2),
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
                    "kaala_velas": panch.get("kaala_velas", []),
                    "reasons": reasons,
                    "windows": windows,
                })

            # Rank the best windows: Abhijit first, then clear of any kaala-vela,
            # then higher day-score, then date. The kaala-vela is a tie-breaker
            # rather than a filter — see _kaala_vela_caution above.
            _q = {"excellent": 0, "good": 1, "average": 2, "avoid": 3}
            all_windows.sort(key=lambda w: (
                _q.get(w["quality"], 4),
                0 if w["label"] == "Abhijit Muhurta" else 1,
                1 if w.get("kaala_vela") else 0,
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
