"""Gochara: current transits, Saturn/Sade Sati, gochara-phala, retrogrades.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class TransitsMixin:

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

            # ── Ashtakavarga bindu tables from the natal chart (§2.4) ───────
            # Used to weight each transit: a graha over a sign rich in its own
            # bindus is supported, poor in bindus is rough. Best-effort — a
            # failure here must not sink the whole transit response.
            try:
                av_bhinna, av_sarva = AstrologyCompute._ashtakavarga_tables(
                    natal_jd, place_obj)
            except Exception as ae:
                print(f"Transit ashtakavarga join failed: {ae}")
                av_bhinna, av_sarva = {}, None

            # ── Transit moment ──────────────────────────────────────────────
            # Anchor to the *viewer's* current location: their wall-clock time and
            # timezone, not the birthplace's. This keeps fast movers (especially the
            # Moon, ~0.5°/hr) at the present instant rather than at birthplace noon.
            if current_date:
                ty, tm, td = map(int, current_date.split("-"))
            else:
                now = _now_at_tz(current_tz if current_tz is not None else tz_offset)
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
                # Ashtakavarga bindus for the sign this graha now occupies.
                own_bav = av_bhinna.get(name, [None] * 12)[rasi] if av_bhinna else None
                sav_bindu = av_sarva[rasi] if av_sarva else None
                strength, chip = AstrologyCompute._bindu_chip(own_bav, sav_bindu)
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
                    "bav_bindus": own_bav,
                    "sav_bindus": sav_bindu,
                    "bindu_strength": strength,
                    "bindu_label": chip,
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
                        # The janma nakshatra (1-27). Everything Moon-referenced in
                        # the tradition counts from here — Tara Bala above all — and
                        # callers were otherwise re-deriving it from their own rasi
                        # chart just to get one integer this function already knew.
                        "nakshatra_index": _janma_nakshatra(
                            natal_moon_rasi * 30.0 + natal_moon_deg),
                        "nakshatra": NAKSHATRA_NAMES[_janma_nakshatra(
                            natal_moon_rasi * 30.0 + natal_moon_deg) - 1],
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
                # SAV row so the frontend can show a bindu legend / context (§2.4).
                "ashtakavarga": {"sarva": av_sarva} if av_sarva else None,
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
                now = _now_at_tz(current_tz if current_tz is not None else tz_offset)
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
