"""Panchanga almanac: five limbs, hora, eclipses, festivals, conjunctions, vedic clock.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class PanchangaMixin:

    @staticmethod
    def get_panchanga(date: Optional[str] = None, place: str = "",
                      lat: Optional[float] = None, lon: Optional[float] = None,
                      tz: Optional[float] = None, system: str = "drik") -> Dict:
        """Daily almanac (panchanga) for a date + place: the five limbs
        (tithi, vaara, nakshatra, yoga, karana) plus sunrise/sunset and the
        inauspicious/auspicious periods (rahu kalam, yamaganda, gulika,
        durmuhurtam, abhijit). Elements are resolved at sunrise of the day,
        the traditional reference point. `date` defaults to today at `place`.

        `system` selects the ephemeris/ayanamsa engine: "drik" (default, the
        modern Drik-ganita under the app ayanamsa) or "surya_siddhanta" (the
        classical Surya-Siddhanta ayanamsa mode). Also includes the Hijri
        (Islamic tabular) date for the day."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        # Surya-Siddhanta = compute the limbs under the SURYASIDDHANTA ayanamsa
        # (the vendored surya_sidhantha.py module itself is buggy). Reset after.
        use_ss = (system or "drik").lower() in ("surya_siddhanta", "surya-siddhanta", "ss")
        try:
            from datetime import datetime, timezone as _utc, timedelta

            if use_ss:
                drik.set_ayanamsa_mode("SURYASIDDHANTA")

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

            # Read vaara at local noon, not at sunrise: the vedic weekday compares
            # the time-of-day against sunrise, and evaluating exactly at sunrise
            # lands on a floating-point boundary that can flip to the previous day
            # (notably at western longitudes). Noon is safely within the vedic day.
            weekday = drik.vaara(jd_noon, place_obj)

            def _period(option):
                s, e = drik.trikalam(jd_noon, place_obj, option)
                return {"start": s[:5] if isinstance(s, str) else s,
                        "end": e[:5] if isinstance(e, str) else e}

            # Kaala-vela windows: the day sunrise→sunset split into eight parts,
            # each ruled by a planet in the weekday's own order (const.day_rulers).
            # The upagraha of the same name is the ascendant rising at the middle
            # of its planet's part — so these are the *time* faces of the Kaala /
            # Mrityu / Artha Prahara / Yama Ghantaka points on the natal table.
            #
            # NOTE these are informational, not muhurta exclusions. Rahu Kalam,
            # Yamaganda and Gulika Kalam (above) are the classical trio to avoid
            # and are already three of the eight parts; treating every kaala-vela
            # as a bar would rule out three-quarters of every day, which is not
            # what the tradition does.
            kaala_velas = []
            try:
                sr_h = _hours_from_dms(sr[1])
                ss_h = _hours_from_dms(ss[1])
                if sr_h is not None and ss_h is not None and ss_h > sr_h:
                    one_part = (ss_h - sr_h) / 8.0
                    rulers = list(const.day_rulers[weekday])
                    for label, pidx in KAALA_VELA_PLANETS:
                        if pidx not in rulers:
                            continue
                        part = rulers.index(pidx)
                        w_start = sr_h + part * one_part
                        kaala_velas.append({
                            "name": label,
                            "planet": PLANET_NAMES.get(pidx, str(pidx)),
                            "part": part + 1,
                            "start": _fmt_hours(w_start),
                            "end": _fmt_hours(w_start + one_part),
                        })
            except Exception as e:
                print(f"Kaala-vela windows error: {e}")

            durmuhurtam = drik.durmuhurtam(jd_noon, place_obj)  # flat [s,e,(s,e)]
            durm = [{"start": durmuhurtam[i][:5], "end": durmuhurtam[i + 1][:5]}
                    for i in range(0, len(durmuhurtam) - 1, 2)]
            abh = drik.abhijit_muhurta(jd_noon, place_obj)

            return {
                "status": "success",
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "place": place,
                "system": "surya_siddhanta" if use_ss else "drik",
                "hijri": _hijri_tabular(jd_noon),
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
                "kaala_velas": kaala_velas,
                "durmuhurtam": durm,
                "abhijit": {"start": abh[0][:5], "end": abh[1][:5]} if abh else None,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            if use_ss:
                drik.set_ayanamsa_mode(DEFAULT_AYANAMSA)

    @staticmethod
    def get_planetary_hours(date: Optional[str] = None, place: str = "",
                            lat: Optional[float] = None, lon: Optional[float] = None,
                            tz: Optional[float] = None) -> Dict:
        """Planetary hours (hora) for a date + place: the 24 horas of the day
        (12 daytime, from sunrise to sunset, + 12 nighttime, sunset to next
        sunrise), each ruled by one of the seven graha. The day's first hora is
        ruled by the weekday lord; the sequence follows the Chaldean order. Each
        hora is tagged benefic/malefic and, for the current day, the running hora
        is flagged. `date` defaults to today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
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

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            jd_noon = swe.julday(year, month, day, 12)

            # shubha_hora returns 24 tuples (planet_index, start 'HH:MM:SS', end),
            # first 12 daytime then 12 nighttime.
            horas = drik.shubha_hora(jd_noon, place_obj)

            # Is "now" within this day (in the place's timezone)? If so, mark the
            # running hora by comparing the local wall-clock against each window.
            now_local = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            is_today = (now_local.year, now_local.month, now_local.day) == (year, month, day)
            now_minutes = now_local.hour * 60 + now_local.minute if is_today else None

            def _hm(s):
                # 'HH:MM:SS' -> 'HH:MM'
                return s[:5] if isinstance(s, str) else str(s)

            def _to_min(s):
                try:
                    parts = str(s).split(":")
                    return int(parts[0]) * 60 + int(parts[1])
                except Exception:
                    return None

            out = []
            for i, (pidx, start, end) in enumerate(horas):
                name = HORA_PLANETS[pidx] if 0 <= pidx < len(HORA_PLANETS) else str(pidx)
                sm, em = _to_min(start), _to_min(end)
                # Night horas after midnight wrap past 24h; the string is still the
                # clock time, so only flag "current" for the daytime block reliably.
                current = False
                if now_minutes is not None and sm is not None and em is not None and i < 12:
                    current = sm <= now_minutes < em
                out.append({
                    "index": i + 1,
                    "planet": name,
                    "start": _hm(start),
                    "end": _hm(end),
                    "period": "day" if i < 12 else "night",
                    "benefic": name in HORA_BENEFICS,
                    "current": current,
                })

            sr = drik.sunrise(jd_noon, place_obj)
            ss = drik.sunset(jd_noon, place_obj)
            return {
                "status": "success",
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "place": place,
                "sunrise": sr[1][:5] if isinstance(sr[1], str) else _fmt_hours(sr[0]),
                "sunset": ss[1][:5] if isinstance(ss[1], str) else _fmt_hours(ss[0]),
                "horas": out,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_eclipses(place: str = "", lat: Optional[float] = None,
                     lon: Optional[float] = None, tz: Optional[float] = None,
                     from_date: Optional[str] = None, count: int = 3) -> Dict:
        """Upcoming solar and lunar eclipses from a date. Returns the next
        `count` of each (global visibility), with the eclipse type and the key
        instants (begin / maximum / end) in the place's local time. Solar and
        lunar are searched independently, each stepping past the previous
        maximum. `from_date` defaults to today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from jhora.panchanga.eclipse import (
                next_solar_eclipse, next_lunar_eclipse, EclipseLocation,
            )

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            if from_date:
                year, month, day = map(int, from_date.split("-"))
            else:
                local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
                year, month, day = local_now.year, local_now.month, local_now.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            count = max(1, min(int(count or 3), 6))

            def _fmt_instant(t):
                # t = (y, m, d, float_hours) local -> {date, time}
                if not t:
                    return None
                y, mo, d, fh = t[0], t[1], t[2], t[3]
                return {"date": f"{y:04d}-{mo:02d}-{d:02d}", "time": _fmt_hours(fh)}

            def _to_jd(t):
                return swe.julday(t[0], t[1], t[2], t[3]) if t else None

            def _midpoint(a, b):
                # Average two local instants -> a normalized (y,m,d,fh) tuple.
                ja, jb = _to_jd(a), _to_jd(b)
                if ja is None or jb is None:
                    return a or b
                return utils.jd_to_gregorian((ja + jb) / 2.0)

            solar = []
            jd = swe.julday(year, month, day, 0)
            for _ in range(count):
                r = next_solar_eclipse(jd, place_obj,
                                       eclipse_location_type=EclipseLocation.GLOBAL)
                if not r:
                    break
                etype, (begin, maximum, end) = r
                solar.append({
                    "type": etype,
                    "date": (_fmt_instant(maximum) or {}).get("date"),
                    "begin": _fmt_instant(begin),
                    "maximum": _fmt_instant(maximum),
                    "end": _fmt_instant(end),
                })
                jd = swe.julday(maximum[0], maximum[1], maximum[2], 0) + 1

            # Lunar: the engine returns [penumbral_begin, partial_begin, max,
            # partial_end, penumbral_end]; its `max` instant omits the tz offset
            # the others carry, so we derive the maximum as the midpoint of the
            # (correctly localized) partial phases, falling back to penumbral.
            lunar = []
            jd = swe.julday(year, month, day, 0)
            for _ in range(count):
                r = next_lunar_eclipse(jd, place_obj,
                                       eclipse_location_type=EclipseLocation.GLOBAL)
                if not r:
                    break
                etype, (pen_begin, par_begin, _bad_max, par_end, pen_end) = r
                begin = par_begin or pen_begin
                end = par_end or pen_end
                maximum = _midpoint(par_begin or pen_begin, par_end or pen_end)
                lunar.append({
                    "type": etype,
                    "date": (_fmt_instant(maximum) or {}).get("date"),
                    "begin": _fmt_instant(pen_begin),
                    "partial_begin": _fmt_instant(par_begin),
                    "maximum": _fmt_instant(maximum),
                    "partial_end": _fmt_instant(par_end),
                    "end": _fmt_instant(pen_end),
                })
                jd = swe.julday(begin[0], begin[1], begin[2], 0) + 1
            return {
                "status": "success",
                "place": place,
                "from_date": f"{year:04d}-{month:02d}-{day:02d}",
                "solar": solar,
                "lunar": lunar,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_festival_dates(place: str = "", lat: Optional[float] = None,
                           lon: Optional[float] = None, tz: Optional[float] = None,
                           start: Optional[str] = None, end: Optional[str] = None,
                           types: Optional[List[str]] = None) -> Dict:
        """Tithi-driven festival / vratha dates in a range. For each requested
        type (Ekadashi, Pradosham, Purnima, Amavasya, Sankashti, …) finds every
        occurrence between `start` and `end` via the tithi finder, returning the
        date, the tithi window, and the vratha's meaning. Defaults to the next
        ~45 days from today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from jhora.panchanga import vratha
            from jhora.panchanga.drik import Date

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707

            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            if start:
                sy, sm, sd = map(int, start.split("-"))
            else:
                sy, sm, sd = local_now.year, local_now.month, local_now.day
            if end:
                ey, em, ed = map(int, end.split("-"))
            else:
                _end = local_now + timedelta(days=45)
                ey, em, ed = _end.year, _end.month, _end.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            start_date, end_date = Date(sy, sm, sd), Date(ey, em, ed)

            if not types:
                types = list(DEFAULT_FESTIVAL_TYPES)

            events = []
            for key in types:
                spec = FESTIVAL_TYPES.get(key)
                if not spec:
                    continue
                rows = vratha.tithi_dates(place_obj, start_date, end_date,
                                          tithi_index_list=list(spec["tithis"]))
                for row in rows:
                    (yy, mm, dd), s_fh, e_fh, tag = row[0], row[1], row[2], row[3]
                    events.append({
                        "type": key,
                        "name": spec["name"],
                        "meaning": spec["meaning"],
                        "date": f"{yy:04d}-{mm:02d}-{dd:02d}",
                        "starts": _fmt_hours(s_fh),
                        "ends": _fmt_hours(e_fh),
                        "detail": tag,
                    })
            events.sort(key=lambda e: (e["date"], e["name"]))
            return {
                "status": "success",
                "place": place,
                "start": f"{sy:04d}-{sm:02d}-{sd:02d}",
                "end": f"{ey:04d}-{em:02d}-{ed:02d}",
                "events": events,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_conjunctions(place: str = "", lat: Optional[float] = None,
                         lon: Optional[float] = None, tz: Optional[float] = None,
                         start: Optional[str] = None, end: Optional[str] = None,
                         max_sep: float = 3.0) -> Dict:
        """Planetary conjunctions (Graha Yuddha / 'planetary war') in a range.

        Scans each day and records when two of the five tara grahas (Mars,
        Mercury, Jupiter, Venus, Saturn — Sun/Moon/nodes never engage in Graha
        Yuddha) come within `max_sep` degrees of each other in ecliptic
        longitude. Consecutive in-range days are collapsed into one event with
        the closest approach (minimum separation) and the date it occurs; a
        separation under 1° is flagged as an actual Graha Yuddha (war).
        Defaults to the next ~90 days from today at `place`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from itertools import combinations

            tz_offset = tz if tz is not None else 5.5
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707

            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            if start:
                sy, sm, sd = map(int, start.split("-"))
            else:
                sy, sm, sd = local_now.year, local_now.month, local_now.day
            if end:
                ey, em, ed = map(int, end.split("-"))
            else:
                _end = local_now + timedelta(days=90)
                ey, em, ed = _end.year, _end.month, _end.day

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            max_sep = max(0.1, min(float(max_sep or 3.0), 15.0))

            start_jd = swe.julday(sy, sm, sd, 0.0)
            end_jd = swe.julday(ey, em, ed, 0.0)
            # Cap the scan so a runaway range can't compute a chart per day forever.
            n_days = int(min(max(end_jd - start_jd, 0), 400)) + 1

            def _lng(pp, idx):
                # pp[idx+1][1] = [sign(0-11), degrees]; ecliptic longitude 0-360.
                return pp[idx + 1][1][0] * 30 + pp[idx + 1][1][1]

            def _sep(a, b):
                d = abs(a - b) % 360
                return 360 - d if d > 180 else d

            # Mars..Saturn planet indices (Sun=0 .. Saturn=6 in HORA_PLANETS).
            tara = list(range(2, 7))
            active: Dict = {}
            finished = []

            for i in range(n_days):
                jd = start_jd + i
                yy, mm, dd, _ = swe.revjul(jd)
                pp = charts.rasi_chart(jd, place_obj)
                lngs = {p: _lng(pp, p) for p in tara}
                seen = set()
                for p1, p2 in combinations(tara, 2):
                    s = _sep(lngs[p1], lngs[p2])
                    key = (p1, p2)
                    if s < max_sep:
                        seen.add(key)
                        date_t = (int(yy), int(mm), int(dd))
                        if key not in active:
                            active[key] = {"from": date_t, "min": s, "min_date": date_t}
                        elif s < active[key]["min"]:
                            active[key]["min"] = s
                            active[key]["min_date"] = date_t
                        active[key]["to"] = date_t
                # close any pair that dropped out of range today
                for key in [k for k in active if k not in seen]:
                    finished.append((key, active.pop(key)))
            for key, ev in active.items():
                finished.append((key, ev))

            def _d(t):
                return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"

            events = []
            for (p1, p2), ev in finished:
                events.append({
                    "planet1": HORA_PLANETS[p1],
                    "planet2": HORA_PLANETS[p2],
                    "from": _d(ev["from"]),
                    "to": _d(ev["to"]),
                    "closest_date": _d(ev["min_date"]),
                    "separation": round(ev["min"], 2),
                    "war": ev["min"] < 1.0,
                })
            events.sort(key=lambda e: (e["closest_date"], e["planet1"]))
            return {
                "status": "success",
                "place": place,
                "start": f"{sy:04d}-{sm:02d}-{sd:02d}",
                "end": f"{ey:04d}-{em:02d}-{ed:02d}",
                "max_separation": max_sep,
                "events": events,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_vedic_clock(date: Optional[str] = None, place: str = "",
                        lat: Optional[float] = None, lon: Optional[float] = None,
                        tz: Optional[float] = None) -> Dict:
        """Vedic day-clock data for a date + place: sunrise/sunset, the day &
        night lengths, the 60-ghati day divisions (1 ghati = 24 min from sunrise),
        the running hora lord, and the panchanga limbs (tithi/nakshatra/yoga) —
        enough for the frontend to render and live-tick a ghati/vighati clock.
        `date` defaults to today at `place`."""
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

            place_obj = drik.Place(place or "", lat, lon, tz_offset)
            jd_noon = swe.julday(year, month, day, 12)

            sr = drik.sunrise(jd_noon, place_obj)   # (hours, 'HH:MM:SS')
            ss = drik.sunset(jd_noon, place_obj)
            sr_h = sr[0] if isinstance(sr[0], (int, float)) else 6.0
            ss_h = ss[0] if isinstance(ss[0], (int, float)) else 18.0
            day_len = max(0.01, ss_h - sr_h)
            night_len = 24.0 - day_len

            # Running hora lord (reuse the shubha_hora table).
            horas = drik.shubha_hora(jd_noon, place_obj)
            now_local = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            is_today = (now_local.year, now_local.month, now_local.day) == (year, month, day)
            now_h = now_local.hour + now_local.minute / 60.0 if is_today else None
            current_hora = None
            for i, (pidx, start, end) in enumerate(horas):
                name = HORA_PLANETS[pidx] if 0 <= pidx < len(HORA_PLANETS) else str(pidx)
                if is_today and i < 12:
                    def _to_h(s):
                        p = str(s).split(":")
                        return int(p[0]) + int(p[1]) / 60.0
                    if _to_h(start) <= now_h < _to_h(end):
                        current_hora = {"planet": name, "benefic": name in HORA_BENEFICS,
                                        "start": str(start)[:5], "end": str(end)[:5]}
            if current_hora is None:
                # Fall back to the weekday lord as the day's first hora lord.
                first = HORA_PLANETS[horas[0][0]] if horas else "Sun"
                current_hora = {"planet": first, "benefic": first in HORA_BENEFICS}

            # Ghati/vighati elapsed since sunrise (only meaningful for "today").
            ghati = vighati = None
            if now_h is not None:
                elapsed_min = (now_h - sr_h) * 60.0
                if elapsed_min < 0:
                    elapsed_min += 24 * 60  # before sunrise → previous vedic day
                ghati_f = elapsed_min / 24.0          # 1 ghati = 24 min
                ghati = int(ghati_f) % 60
                vighati = int((ghati_f - int(ghati_f)) * 60)

            # Panchanga limbs at the reference instant.
            ref_jd = swe.julday(year, month, day, now_h if now_h is not None else 12.0)
            limbs = {}
            try:
                tt = drik.tithi(ref_jd, place_obj)
                t_name, t_paksha = _tithi_name(tt[0])
                limbs["tithi"] = t_name
                limbs["paksha"] = t_paksha
            except Exception:
                pass
            try:
                nk = drik.nakshatra(ref_jd, place_obj)
                limbs["nakshatra"] = NAKSHATRA_NAMES[(nk[0] - 1) % 27]
            except Exception:
                pass
            try:
                yg = drik.yogam(ref_jd, place_obj)
                limbs["yoga"] = YOGA_NAMES[(yg[0] - 1) % 27]
            except Exception:
                pass

            def _hm(s):
                return str(s)[:5] if s is not None else "—"

            return {
                "status": "success",
                "date": f"{year:04d}-{month:02d}-{day:02d}",
                "place": place,
                "is_today": is_today,
                "sunrise": _hm(sr[1]) if not isinstance(sr[1], (int, float)) else _fmt_hours(sr_h),
                "sunset": _hm(ss[1]) if not isinstance(ss[1], (int, float)) else _fmt_hours(ss_h),
                "sunrise_hours": round(sr_h, 4),
                "sunset_hours": round(ss_h, 4),
                "day_length_hours": round(day_len, 4),
                "night_length_hours": round(night_len, 4),
                "ghati": ghati,
                "vighati": vighati,
                "current_hora": current_hora,
                "panchanga": limbs,
                "tz": tz_offset,
            }
        except Exception as e:
            print(f"Vedic clock error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
