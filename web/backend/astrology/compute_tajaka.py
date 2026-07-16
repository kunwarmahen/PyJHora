"""Tajaka / annual + lunar returns: Varshaphal, masa/tithi pravesha, tithi-ashtottari.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class TajakaMixin:

    @staticmethod
    def get_varshaphal(dob: str, tob: str, place: str, year: int,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None,
                       ayanamsa: str = DEFAULT_AYANAMSA,
                       dasha_system: str = "mudda") -> Dict:
        """Varshaphal / Tajaka annual (solar-return) horoscope for a target year.

        Returns the annual chart (formatted for the Kundali component), the
        year-entry instant, the Muntha (progressed Ascendant), the year-lord
        (Varsheshwara), a curated set of Sahams, the present Tajaka yogas and the
        annual Mudda (Varsha Vimsottari) maha-dasha periods. Birth details +
        ayanamsa are server-injected; global ayanamsa is reset afterwards.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}

        try:
            birth_year = int(dob.split("-")[0])
            year = int(year)
            # The native attains `age` in the target year; age 0 = birth year.
            # varsha_pravesh(years=N) yields the solar return in (birth_year+N-1),
            # so the annual chart for `year` uses years = age + 1, while
            # lord_of_the_year / muntha / mudda use `age` (they advance from dob).
            age = year - birth_year
            if age < 0:
                return {"error": "Year must be on or after the birth year",
                        "status": "failed"}

            dasha_key = (dasha_system or "mudda").lower()
            if dasha_key not in VARSHA_DASHA_SYSTEMS:
                dasha_key = "mudda"

            _set_ayanamsa(ayanamsa)
            import contextlib
            import io
            from jhora.horoscope.transit import tajaka, saham, tajaka_yoga

            y, m, d = map(int, dob.split("-"))
            time_parts = tob.split(":")
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0

            if not lat or not lon:
                lat, lon = 13.0827, 80.2707  # Chennai default
            tz_offset = tz or 5.5

            jd_dob = swe.julday(y, m, d, hour + minute / 60)
            place_obj = drik.Place(place, lat, lon, tz_offset)

            # ── Annual (Tajaka) chart ──────────────────────────────────────
            cht, entry = tajaka.varsha_pravesh(jd_dob, place_obj,
                                               divisional_chart_factor=1,
                                               years=age + 1)
            (ey, em, ed), etime = entry
            year_entry = {
                "date": f"{ey:04d}-{em:02d}-{ed:02d}",
                "time": str(etime),
            }

            asc_rasi, asc_deg = cht[0][1]
            lagna = {
                "house": asc_rasi + 1,
                "degrees": round(asc_deg, 2),
                "sign_name": ZODIAC_NAMES[asc_rasi],
            }
            planets = {}
            for planet_index, (rasi, degrees) in cht[1:]:
                name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
                planets[name] = {
                    "rasi": rasi,
                    "house": rasi + 1,
                    "degrees": round(degrees, 2),
                    "sign_name": ZODIAC_NAMES[rasi],
                }

            # ── Muntha: natal Lagna sign advanced one sign per completed year ─
            natal_chart = charts.divisional_chart(jd_dob, place_obj,
                                                  divisional_chart_factor=1)
            natal_asc = natal_chart[0][1][0]
            muntha_sign = tajaka.muntha_house(natal_asc, age)  # 0-11 sign index
            muntha = {
                "sign": muntha_sign,
                "sign_name": ZODIAC_NAMES[muntha_sign],
                "house": ((muntha_sign - asc_rasi) % 12) + 1,
            }

            # ── Year-lord (Varsheshwara) ───────────────────────────────────
            year_lord = None
            try:
                yl_idx = tajaka.lord_of_the_year(jd_dob, place_obj, age)
                if yl_idx is not None and yl_idx in PLANET_NAMES:
                    year_lord = {"index": yl_idx, "planet": PLANET_NAMES[yl_idx]}
            except Exception as e:
                print(f"Varshaphal year-lord error: {e}")

            # Day/night of the annual entry drives the Sahams' day/night formula.
            night_birth = False
            try:
                ann_jd = drik.next_solar_date(jd_dob, place_obj, years=age + 1)
                entry_hrs = drik.jd_to_gregorian(ann_jd)[3]
                sr = utils.from_dms_str_to_dms(drik.sunrise(ann_jd, place_obj)[1])
                ss = utils.from_dms_str_to_dms(drik.sunset(ann_jd, place_obj)[1])
                sr_h = sr[0] + sr[1] / 60.0 + sr[2] / 3600.0
                ss_h = ss[0] + ss[1] / 60.0 + ss[2] / 3600.0
                night_birth = entry_hrs > ss_h or entry_hrs < sr_h
            except Exception as e:
                print(f"Varshaphal night-birth error: {e}")

            # ── Sahams (sensitive points) ──────────────────────────────────
            sahams = []
            for label, fn_name, significance in VARSHAPHAL_SAHAMS:
                try:
                    fn = getattr(saham, fn_name)
                    try:
                        s_long = fn(cht, night_birth)
                    except TypeError:
                        s_long = fn(cht)  # a few sahams take positions only
                    s_long = float(s_long) % 360
                    s_sign = int(s_long // 30)
                    sahams.append({
                        "name": label,
                        "significance": significance,
                        "sign": s_sign,
                        "sign_name": ZODIAC_NAMES[s_sign],
                        "degrees": round(s_long % 30, 2),
                        "house": ((s_sign - asc_rasi) % 12) + 1,
                    })
                except Exception as e:
                    print(f"Varshaphal saham {label} error: {e}")

            # ── Tajaka yogas (curated) ─────────────────────────────────────
            tajaka_yogas = []
            p2h = utils.get_planet_house_dictionary_from_planet_positions(cht)
            _sink = io.StringIO()  # muffle engine debug prints
            try:
                if tajaka_yoga.ishkavala_yoga(p2h):
                    tajaka_yogas.append({
                        "name": "Ishkavala",
                        "description": "Planets confined to kendras and panapharas — "
                                       "indicates wealth, happiness and good fortune.",
                    })
            except Exception:
                pass
            try:
                if tajaka_yoga.induvara_yoga(p2h):
                    tajaka_yogas.append({
                        "name": "Induvara",
                        "description": "Planets confined to apoklimas — cautions of "
                                       "worries, obstacles and ill health.",
                    })
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ith_pairs = tajaka_yoga.get_ithasala_yoga_planet_pairs(cht)
                for p1, p2, _t in ith_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({
                        "name": "Ithasala",
                        "pair": [a, b],
                        "description": f"Applying aspect between {a} and {b} — the "
                                       "matter they signify tends to fructify this year.",
                    })
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ees_pairs = tajaka_yoga.get_eesarpha_yoga_planet_pairs(cht)
                for p1, p2 in ees_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({
                        "name": "Eesarpha",
                        "pair": [a, b],
                        "description": f"Separating aspect between {a} and {b} — the "
                                       "matter they signify tends to slip away or delay.",
                    })
            except Exception:
                pass

            # ── Annual dasha (selectable system: Mudda / Patyayini / Narayana) ─
            label, lord_type = VARSHA_DASHA_SYSTEMS[dasha_key]
            annual_dasha = {"system": label, "system_key": dasha_key,
                            "lord_type": lord_type, "periods": []}
            dob_date = drik.Date(y, m, d)
            tob_tuple = (hour, minute, 0)
            try:
                annual_dasha = _annual_dasha(dasha_key, jd_dob, place_obj, age,
                                             dob_date, tob_tuple)
            except Exception as e:
                print(f"Varshaphal annual-dasha ({dasha_key}) error: {e}")

            return {
                "status": "success",
                "year": year,
                "age": age,
                "year_entry": year_entry,
                "lagna": lagna,
                "planets": planets,
                "muntha": muntha,
                "year_lord": year_lord,
                "sahams": sahams,
                "tajaka_yogas": tajaka_yogas,
                "annual_dasha": annual_dasha,
                "dasha_systems": [
                    {"key": k, "label": v[0], "lord_type": v[1]}
                    for k, v in VARSHA_DASHA_SYSTEMS.items()
                ],
            }
        except Exception as e:
            print(f"Varshaphal error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_masa_pravesh(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None, date: Optional[str] = None,
                         year: Optional[int] = None, month: Optional[int] = None,
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Maasa Pravesha / Tajaka **monthly** (solar-return) horoscope.

        The Tajaka month is 1/12 of a solar-return year (~30.4 days), the Sun
        advancing 30° from its natal longitude per month — *not* a calendar month.
        By default the window containing `date` (today) is selected; pass an
        explicit solar `year` (native's age → year) + `month` (1-12) to target a
        specific window. Returns the monthly chart, the pravesh window
        (start/end instants), the progressed Muntha, the year-lord and the current
        Tajaka yogas — the monthly analogue of :meth:`get_varshaphal`."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            import contextlib, io
            from jhora.horoscope.transit import tajaka, saham, tajaka_yoga
            from jhora import const as _const

            _set_ayanamsa(ayanamsa)

            y, m, d = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            jd_dob = swe.julday(y, m, d, hour + minute / 60.0)

            # ── Pick the (years, months) window ────────────────────────────
            birth_year = int(dob.split("-")[0])
            if year is not None and month is not None:
                years_param = int(year) - birth_year + 1
                months_param = max(1, min(12, int(month)))
            else:
                # Which monthly window contains the reference date? Use the
                # linear solar-year fraction from birth (good enough to select
                # the window; the engine then solves the exact pravesh instant).
                tz_now = tz_offset
                if date:
                    ry, rm, rd = map(int, date.split("-"))
                    jd_ref = swe.julday(ry, rm, rd, 12.0)
                else:
                    now = datetime.now(_utc.utc) + timedelta(hours=tz_now)
                    jd_ref = swe.julday(now.year, now.month, now.day, 12.0)
                frac = (jd_ref - jd_dob) / _const.tropical_year
                if frac < 0:
                    return {"error": "Date must be on or after the birth date",
                            "status": "failed"}
                years_elapsed = int(frac)
                month_idx = int((frac - years_elapsed) * 12)  # 0-11

                # The linear fraction is only an *estimate* — the true Maasa
                # Pravesha is where the Sun actually reaches natal-longitude+30°k,
                # which drifts a day or two from an even 1/12 of the year. Snap the
                # estimate onto the window that really contains the date by solving
                # the boundaries and walking the index until it does. Without this
                # the digest could return a window the requested date sits outside
                # of, and stepping back off a window's start would re-select that
                # same window instead of the previous one.
                idx = years_elapsed * 12 + month_idx      # months since birth
                for _ in range(4):
                    yp, mp = idx // 12 + 1, idx % 12 + 1
                    w_start = drik.next_solar_date(jd_dob, place_obj,
                                                   years=yp, months=mp)
                    n_yp, n_mp = (yp + 1, 1) if mp >= 12 else (yp, mp + 1)
                    w_end = drik.next_solar_date(jd_dob, place_obj,
                                                 years=n_yp, months=n_mp)
                    if jd_ref < w_start and idx > 0:
                        idx -= 1
                    elif jd_ref >= w_end:
                        idx += 1
                    else:
                        break
                years_param = idx // 12 + 1
                months_param = idx % 12 + 1
            age = years_param - 1

            # ── Monthly (Tajaka) chart + window boundaries ─────────────────
            cht, entry = tajaka.maasa_pravesh(jd_dob, place_obj,
                                              divisional_chart_factor=1,
                                              years=years_param, months=months_param)
            (ey, em, ed), etime = entry
            start_jd = drik.next_solar_date(jd_dob, place_obj,
                                            years=years_param, months=months_param)
            # Next month's entry closes this window (rolling 12 → next year).
            if months_param >= 12:
                next_yp, next_mp = years_param + 1, 1
            else:
                next_yp, next_mp = years_param, months_param + 1
            end_jd = drik.next_solar_date(jd_dob, place_obj,
                                          years=next_yp, months=next_mp)
            ny, nm, nd, _nf = utils.jd_to_gregorian(end_jd)
            month_entry = {"date": f"{ey:04d}-{em:02d}-{ed:02d}", "time": str(etime)}
            window = {
                "start": f"{ey:04d}-{em:02d}-{ed:02d}",
                "end": f"{ny:04d}-{nm:02d}-{nd:02d}",
                "month_index": months_param,
                "year": birth_year + age,
                "age": age,
            }

            asc_rasi, asc_deg = cht[0][1]
            lagna = {"house": asc_rasi + 1, "degrees": round(asc_deg, 2),
                     "sign_name": ZODIAC_NAMES[asc_rasi]}
            planets = {}
            for planet_index, (rasi, degrees) in cht[1:]:
                name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
                planets[name] = {"rasi": rasi, "house": rasi + 1,
                                 "degrees": round(degrees, 2),
                                 "sign_name": ZODIAC_NAMES[rasi]}

            # ── Muntha (natal Lagna advanced one sign per completed year) ──
            natal_chart = charts.divisional_chart(jd_dob, place_obj,
                                                  divisional_chart_factor=1)
            natal_asc = natal_chart[0][1][0]
            muntha_sign = tajaka.muntha_house(natal_asc, age)
            muntha = {"sign": muntha_sign, "sign_name": ZODIAC_NAMES[muntha_sign],
                      "house": ((muntha_sign - asc_rasi) % 12) + 1}

            year_lord = None
            try:
                yl_idx = tajaka.lord_of_the_year(jd_dob, place_obj, age)
                if yl_idx is not None and yl_idx in PLANET_NAMES:
                    year_lord = {"index": yl_idx, "planet": PLANET_NAMES[yl_idx]}
            except Exception as e:
                print(f"Masa-pravesh year-lord error: {e}")

            # Day/night of the month entry drives the Sahams' day/night formula.
            night_entry = False
            try:
                entry_hrs = drik.jd_to_gregorian(start_jd)[3]
                sr = utils.from_dms_str_to_dms(drik.sunrise(start_jd, place_obj)[1])
                ss = utils.from_dms_str_to_dms(drik.sunset(start_jd, place_obj)[1])
                sr_h = sr[0] + sr[1] / 60.0 + sr[2] / 3600.0
                ss_h = ss[0] + ss[1] / 60.0 + ss[2] / 3600.0
                night_entry = entry_hrs > ss_h or entry_hrs < sr_h
            except Exception as e:
                print(f"Masa-pravesh night-entry error: {e}")

            sahams = []
            for label, fn_name, significance in VARSHAPHAL_SAHAMS:
                try:
                    fn = getattr(saham, fn_name)
                    try:
                        s_long = fn(cht, night_entry)
                    except TypeError:
                        s_long = fn(cht)
                    s_long = float(s_long) % 360
                    s_sign = int(s_long // 30)
                    sahams.append({
                        "name": label, "significance": significance,
                        "sign": s_sign, "sign_name": ZODIAC_NAMES[s_sign],
                        "degrees": round(s_long % 30, 2),
                        "house": ((s_sign - asc_rasi) % 12) + 1,
                    })
                except Exception as e:
                    print(f"Masa-pravesh saham {label} error: {e}")

            tajaka_yogas = []
            p2h = utils.get_planet_house_dictionary_from_planet_positions(cht)
            _sink = io.StringIO()
            try:
                if tajaka_yoga.ishkavala_yoga(p2h):
                    tajaka_yogas.append({"name": "Ishkavala",
                        "description": "Planets confined to kendras and panapharas — "
                                       "wealth, happiness and good fortune this month."})
            except Exception:
                pass
            try:
                if tajaka_yoga.induvara_yoga(p2h):
                    tajaka_yogas.append({"name": "Induvara",
                        "description": "Planets confined to apoklimas — cautions of "
                                       "worries, obstacles and ill health this month."})
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ith_pairs = tajaka_yoga.get_ithasala_yoga_planet_pairs(cht)
                for p1, p2, _t in ith_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({"name": "Ithasala", "pair": [a, b],
                        "description": f"Applying aspect between {a} and {b} — the "
                                       "matter they signify tends to fructify this month."})
            except Exception:
                pass
            try:
                with contextlib.redirect_stdout(_sink):
                    ees_pairs = tajaka_yoga.get_eesarpha_yoga_planet_pairs(cht)
                for p1, p2 in ees_pairs:
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    tajaka_yogas.append({"name": "Eesarpha", "pair": [a, b],
                        "description": f"Separating aspect between {a} and {b} — the "
                                       "matter they signify tends to slip away or delay."})
            except Exception:
                pass

            return {
                "status": "success",
                "window": window,
                "month_entry": month_entry,
                "lagna": lagna,
                "planets": planets,
                "muntha": muntha,
                "year_lord": year_lord,
                "sahams": sahams,
                "tajaka_yogas": tajaka_yogas,
            }
        except Exception as e:
            print(f"Masa-pravesh error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    # ── Lunar (tithi) pravesha ladder ──────────────────────────────────────
    #
    # Tajaka's *solar* ladder only has chart-bearing rungs at the year
    # (Varshaphal) and the month (Maasa Pravesha) — below that it drops to the
    # ~2.53-day "sixty-hour", so there is no solar week or fortnight.
    #
    # The *lunar* (tithi) ladder — which is the family Jagannatha Hora exposes as
    # daily / fortnightly / monthly / annual — is complete:
    #
    #   tithi (~0.98d) → paksha (~14.8d) → lunar month (~29.5d) → Tithi Pravesha (~354d)
    #
    # Each window is solved off drik's tithi-boundary primitives
    # (`_tithi_number_at_jd` + `_tithi_boundary_jd`, a bisection on the tithi
    # change). NOTE: `drik.next_tithi` is marked UNDER EXPERIMENTATION and its
    # backward branch is wrong (it sums the indices instead of differencing), so
    # we never use it — we walk boundaries ourselves.

    @staticmethod
    def _tithi_num(jd: float, place_obj) -> int:
        """Instantaneous tithi number (1-30) at `jd`."""
        return int(drik._tithi_number_at_jd(jd, place_obj))

    @staticmethod
    def _tithi_bound(jd: float, place_obj, direction: int) -> float:
        """Nearest tithi boundary before (-1) or after (+1) `jd`."""
        return drik._tithi_boundary_jd(jd, place_obj, direction=direction)

    @staticmethod
    def _walk_tithi(jd: float, place_obj, steps: int) -> float:
        """Advance `steps` tithi boundaries from `jd` (negative walks backwards)."""
        direction = 1 if steps >= 0 else -1
        cur = jd
        for _ in range(abs(int(steps))):
            cur = AstrologyCompute._tithi_bound(cur, place_obj, direction)
        return cur

    @staticmethod
    def _tithi_window(jd: float, place_obj) -> Dict:
        """The running tithi's window: {index, start_jd, end_jd}."""
        return {
            "index": AstrologyCompute._tithi_num(jd, place_obj),
            "start_jd": AstrologyCompute._tithi_bound(jd, place_obj, -1),
            "end_jd": AstrologyCompute._tithi_bound(jd, place_obj, +1),
        }

    @staticmethod
    def _paksha_window(jd: float, place_obj) -> Dict:
        """The running paksha (lunar fortnight): Shukla = tithis 1-15, Krishna =
        16-30. The window runs from *this* paksha's first tithi to the *next*
        paksha's first tithi — i.e. Shukla opens at tithi 1 and closes at 16,
        Krishna opens at 16 and closes at (the next) 1. Both boundaries are found
        with the direct tithi-index solver rather than by walking every tithi in
        between. Returns {paksha, tithi_index, start_jd, end_jd}."""
        n = AstrologyCompute._tithi_num(jd, place_obj)
        shukla = n <= 15
        opens, closes = (1, 16) if shukla else (16, 1)
        return {
            "paksha": "Shukla" if shukla else "Krishna",
            "tithi_index": n,
            "start_jd": AstrologyCompute._tithi_index_start(jd, place_obj, opens, -1),
            "end_jd": AstrologyCompute._tithi_index_start(jd, place_obj, closes, +1),
        }

    # Mean synodic month — the period over which a tithi index recurs.
    _SYNODIC_MONTH = 29.530588

    @staticmethod
    def _tithi_index_start(jd: float, place_obj, target: int, direction: int) -> Optional[float]:
        """Start-JD of the nearest tithi whose index == `target`, searching
        backwards (-1) or forwards (+1).

        A tithi index recurs once per synodic month, so we **jump straight to the
        estimated recurrence** (each tithi is 1/30 of a lunation) and then settle
        onto the exact boundary, correcting at most a couple of tithis for the
        Moon's non-uniform motion. Walking every boundary in between instead would
        cost ~30 bisections — ~1250 `tithi()` calls, each an inverse-Lagrange over
        17 lunar-phase samples — which is fast enough on a dev box but times out
        the request on slower hardware."""
        step = AstrologyCompute._SYNODIC_MONTH / 30.0  # ~one tithi
        cur = AstrologyCompute._tithi_num(jd, place_obj)
        if direction < 0:
            # Most recent occurrence at/before jd. If we are already inside the
            # target tithi, that occurrence is the one we're in.
            est = jd - ((cur - target) % 30) * step
        else:
            # The *next* occurrence strictly after jd. If we are already inside
            # the target tithi, it does not count — skip a full lunation to the
            # next recurrence (a tithi can run past 1 day, so "already in it" is
            # reachable even a day out from its start).
            ahead = (target - cur) % 30 or 30
            est = jd + ahead * step

        # Settle: the estimate lands within a tithi or two of the target.
        for _ in range(8):
            n = AstrologyCompute._tithi_num(est, place_obj)
            if n == target:
                return AstrologyCompute._tithi_bound(est, place_obj, -1)
            # Signed shortest distance (in tithis) from n to target.
            d = (target - n) % 30
            if d > 15:
                d -= 30
            if d > 0:  # step forward into the next tithi
                est = AstrologyCompute._tithi_bound(est, place_obj, +1) + 1e-3
            else:      # step back into the previous tithi
                est = AstrologyCompute._tithi_bound(est, place_obj, -1) - 1e-3
        return None

    @staticmethod
    def _lunar_month_window(jd: float, place_obj, birth_tithi: int) -> Optional[Dict]:
        """The lunar month as a *birth-tithi return*: from the most recent
        recurrence of the natal tithi at/before `jd` to its next recurrence
        (~29.5 days). Returns {tithi_index, start_jd, end_jd}."""
        start = AstrologyCompute._tithi_index_start(jd, place_obj, birth_tithi, -1)
        if start is None:
            return None
        end = AstrologyCompute._tithi_index_start(start + 1.0, place_obj, birth_tithi, +1)
        if end is None:
            return None
        return {"tithi_index": birth_tithi, "start_jd": start, "end_jd": end}

    @staticmethod
    def _pravesha_block(cht, jd_dob, place_obj, age: int,
                        with_sahams: bool = False, jd_event: Optional[float] = None) -> Dict:
        """The standard progressed-chart block shared by every pravesha rung
        (solar or lunar): Lagna, planets, Muntha, year-lord and the Tajaka yogas
        present in the cast chart. `cht` is a D1 planet-positions list.

        `with_sahams` additionally derives the curated Sahams from the cast chart
        (needs `jd_event`, the pravesha instant, for the day/night formula). Only
        the *annual* rungs surface Sahams — on a fortnight or a single tithi they
        are noise."""
        import contextlib, io
        from jhora.horoscope.transit import tajaka, tajaka_yoga

        asc_rasi, asc_deg = cht[0][1]
        lagna = {"house": asc_rasi + 1, "degrees": round(asc_deg, 2),
                 "sign_name": ZODIAC_NAMES[asc_rasi]}
        planets = {}
        for planet_index, (rasi, degrees) in cht[1:]:
            name = PLANET_NAMES.get(planet_index, f"Planet_{planet_index}")
            planets[name] = {"rasi": rasi, "house": rasi + 1,
                             "degrees": round(degrees, 2),
                             "sign_name": ZODIAC_NAMES[rasi]}

        natal_chart = charts.divisional_chart(jd_dob, place_obj, divisional_chart_factor=1)
        natal_asc = natal_chart[0][1][0]
        muntha_sign = tajaka.muntha_house(natal_asc, age)
        muntha = {"sign": muntha_sign, "sign_name": ZODIAC_NAMES[muntha_sign],
                  "house": ((muntha_sign - asc_rasi) % 12) + 1}

        year_lord = None
        try:
            yl_idx = tajaka.lord_of_the_year(jd_dob, place_obj, age)
            if yl_idx is not None and yl_idx in PLANET_NAMES:
                year_lord = {"index": yl_idx, "planet": PLANET_NAMES[yl_idx]}
        except Exception as e:
            print(f"[pravesha] year-lord error: {e}")

        yogas = []
        p2h = utils.get_planet_house_dictionary_from_planet_positions(cht)
        _sink = io.StringIO()
        try:
            if tajaka_yoga.ishkavala_yoga(p2h):
                yogas.append({"name": "Ishkavala",
                              "description": "Planets confined to kendras and panapharas — "
                                             "wealth, happiness and good fortune."})
        except Exception:
            pass
        try:
            if tajaka_yoga.induvara_yoga(p2h):
                yogas.append({"name": "Induvara",
                              "description": "Planets confined to apoklimas — cautions of "
                                             "worries, obstacles and ill health."})
        except Exception:
            pass
        for fn, label, blurb in (
            (tajaka_yoga.get_ithasala_yoga_planet_pairs, "Ithasala",
             "Applying aspect between {a} and {b} — the matter they signify tends to fructify."),
            (tajaka_yoga.get_eesarpha_yoga_planet_pairs, "Eesarpha",
             "Separating aspect between {a} and {b} — the matter they signify tends to slip away."),
        ):
            try:
                with contextlib.redirect_stdout(_sink):
                    pairs = fn(cht)
                for pair in pairs:
                    p1, p2 = pair[0], pair[1]
                    a, b = PLANET_NAMES.get(p1, p1), PLANET_NAMES.get(p2, p2)
                    yogas.append({"name": label, "pair": [a, b],
                                  "description": blurb.format(a=a, b=b)})
            except Exception:
                pass

        block = {"lagna": lagna, "planets": planets, "muntha": muntha,
                 "year_lord": year_lord, "tajaka_yogas": yogas}

        if with_sahams:
            # Sahams are sensitive points derived from the cast chart's planetary
            # positions, so they are well-defined on any pravesha chart. Their
            # day/night formula keys off whether the pravesha instant is by day.
            from jhora.horoscope.transit import saham

            night_entry = False
            try:
                entry_hrs = drik.jd_to_gregorian(jd_event)[3]
                sr = utils.from_dms_str_to_dms(drik.sunrise(jd_event, place_obj)[1])
                ss = utils.from_dms_str_to_dms(drik.sunset(jd_event, place_obj)[1])
                sr_h = sr[0] + sr[1] / 60.0 + sr[2] / 3600.0
                ss_h = ss[0] + ss[1] / 60.0 + ss[2] / 3600.0
                night_entry = entry_hrs > ss_h or entry_hrs < sr_h
            except Exception as e:
                print(f"[pravesha] night-entry error: {e}")

            sahams = []
            for slabel, fn_name, significance in VARSHAPHAL_SAHAMS:
                try:
                    fn = getattr(saham, fn_name)
                    try:
                        s_long = fn(cht, night_entry)
                    except TypeError:
                        s_long = fn(cht)
                    s_long = float(s_long) % 360
                    s_sign = int(s_long // 30)
                    sahams.append({
                        "name": slabel, "significance": significance,
                        "sign": s_sign, "sign_name": ZODIAC_NAMES[s_sign],
                        "degrees": round(s_long % 30, 2),
                        "house": ((s_sign - asc_rasi) % 12) + 1,
                    })
                except Exception as e:
                    print(f"[pravesha] saham {slabel} error: {e}")
            block["sahams"] = sahams

        return block

    @staticmethod
    def _ta_rows(rows: List[Dict], level: int) -> List[Dict]:
        """Shape `varsha_tithi_ashtottari` periods for the API.

        `start_jd` / `span_deg` are handed back verbatim because the drill-down
        endpoint needs them to subdivide a period without re-deriving the whole
        tree from the pravesha instant."""
        from datetime import datetime as _dt

        now = _dt.now().isoformat(timespec="seconds")
        out = []
        for r in rows:
            start = _iso_datetime(r["start_jd"])
            end = _iso_datetime(r["end_jd"])
            out.append({
                "lord": r["lord"],
                "lord_name": PLANET_NAMES.get(r["lord"], str(r["lord"])),
                "start": start,
                "end": end,
                "span_days": round(r["span_days"], 4),
                "span_deg": r["span_deg"],
                "start_jd": r["start_jd"],
                "level": level,
                "level_name": vta.LEVEL_NAMES[min(level, vta.MAX_LEVEL)],
                "has_children": level < vta.MAX_LEVEL,
                "current": start <= now < end,
            })
        return out

    # What window each lunar rung's dasha is compressed into, for the label.
    _TA_WINDOW_LABEL = {
        "tithi": "this tithi",
        "paksha": "this fortnight",
        "month": "this lunar month",
        "annual": "this lunar year",
    }

    @staticmethod
    def get_varsha_tithi_ashtottari(anchor_jd: float, place_obj, cycle_deg: float,
                                    rung: str = "annual") -> Dict:
        """**Varsha Tithi Ashtottari** — the compressed dasha Jagannatha Hora shows
        beside the Tithi Pravesha chart ("Tithi Ashtottari Dasa of Janma tithi in
        D-1"). The whole 108-unit Ashtottari cycle is squeezed into the pravesha
        window, exactly as Mudda squeezes Vimsottari into the solar year.

        The compression is in **Moon−Sun elongation**, not in days: `cycle_deg` is
        the elongation the window sweeps (a tithi 12°, a fortnight 180°, a lunar
        month 360°, a pravesha year N × 360°) and each lord takes `allotment/108` of
        it. Because it is angular, the same construction serves every rung of the
        lunar ladder — a day is compressed exactly as a year is. See
        `varsha_tithi_ashtottari` for the algorithm and for why the engine's own
        Tithi Ashtottari functions cannot be used.

        Nine maha rows come back, not eight: the first is the balance of the period
        already running when the window opens (JHora lists it too), so a full cycle
        of eight still follows it."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            rows = vta.maha_periods(anchor_jd, place_obj, cycle_deg)
            window = AstrologyCompute._TA_WINDOW_LABEL.get(rung, "this window")
            return {
                "status": "success",
                "system": f"Tithi Ashtottari (compressed into {window})",
                "system_key": "varsha_tithi_ashtottari",
                "lord_type": "planet",
                "level": "maha",
                "rung": rung,
                "cycle_deg": cycle_deg,
                "lunar_months": vta.lunar_months_in(cycle_deg),
                "expandable": True,
                "periods": AstrologyCompute._ta_rows(rows, 0),
            }
        except Exception as e:
            print(f"Varsha-Tithi-Ashtottari error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_tithi_ashtottari_children(start_jd: float, lord: int, span_deg: float,
                                      level: int, lat: float, lon: float,
                                      tz: float, place: str = "") -> Dict:
        """The eight sub-periods of one Varsha Tithi Ashtottari period — the lazy
        drill-down behind the expandable dasha tree.

        Expanded on demand rather than served whole: six levels (Maha → Antara →
        Pratyantara → Sookshma → Prana → Deha) is 8⁶ ≈ 262k rows, and the deepest
        are under a minute long. A period is fully described by its start instant,
        lord and **degree** span, so a child level needs no other state — it
        subdivides that span by allotment, starting on the lord after the parent."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        if level >= vta.MAX_LEVEL:
            return {"status": "success", "periods": []}
        if int(lord) not in vta.ORDER:
            return {"error": f"Unknown dasha lord '{lord}'", "status": "failed"}
        # A period always has positive extent. A zero or negative span would walk
        # the elongation backwards and hand back periods that end before they
        # start, so refuse it rather than emit nonsense.
        if not span_deg or span_deg <= 0:
            return {"error": "A period's span must be positive", "status": "failed"}
        try:
            place_obj = drik.Place(place or "", lat, lon, tz)
            rows = vta.children(start_jd, int(lord), span_deg, place_obj)
            return {
                "status": "success",
                "level": level + 1,
                "level_name": vta.LEVEL_NAMES[level + 1],
                "periods": AstrologyCompute._ta_rows(rows, level + 1),
            }
        except Exception as e:
            print(f"Tithi-Ashtottari children error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def _tithi_pravesha_dates(by: int, bm: int, bd: int, hour: int, minute: int,
                              place_obj, year_number: int) -> List:
        """`vratha.tithi_pravesha`, but leap-day safe.

        The engine centres its ±30-day search on `Date(year_number, birth_month,
        birth_day)`. For a **29-February birth** that date does not exist in a
        non-leap target year, and the call dies converting it to a numpy datetime
        — so Tithi Pravesha was broken outright for leap-day natives.

        The anchor only *centres* the search window, so clamping 29 Feb → 28 Feb
        cannot change which date is found (the true TP is located by matching the
        birth tithi + lunar month inside that window). The birth tithi and lunar
        month are still taken from the real birth date, so nothing else shifts.
        Non-leap births take the engine's own path untouched."""
        from jhora.panchanga import vratha

        birth_date = drik.Date(by, bm, bd)
        birth_time = (hour, minute, 0)

        if not (bm == 2 and bd == 29):
            return vratha.tithi_pravesha(birth_date, birth_time, place_obj, year_number)

        window = 30
        anchor = drik.Date(year_number, 2, 28)  # 29 Feb may not exist in year_number
        start = utils.previous_panchanga_day(anchor, window)
        end = utils.next_panchanga_day(start, 2 * window)

        jd = utils.julian_day_number(birth_date, birth_time)
        _, _, _, bt_hours = utils.jd_to_gregorian(jd)
        t = drik.tithi(jd, place_obj)
        tm = drik.tamil_solar_month_and_date(birth_date, place_obj)
        t_frac = utils.get_fraction(t[1], t[2], bt_hours)

        results = vratha.search(place_obj, start, end,
                                tithi_index=t[0], tamil_month_index=tm[0] + 1)
        out = []
        for s_date, s_start, s_end, s_desc in results:
            t_len = s_end - s_start
            if s_start > 23.99:
                t_len += 24
            out.append((s_date, s_end - t_frac * t_len, s_end, s_desc))
        return out

    @staticmethod
    def get_lunar_pravesha(rung: str, dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None, date: Optional[str] = None,
                           year: Optional[int] = None,
                           ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A chart on the **lunar (tithi) pravesha ladder**, cast at the moment the
        window opens. `rung` is one of:

          * ``"tithi"``   — the running tithi (~0.98 days)
          * ``"paksha"``  — the running lunar fortnight, Shukla or Krishna (~14.8 days)
          * ``"month"``   — the birth-tithi return, i.e. the lunar month (~29.5 days)
          * ``"annual"``  — **Tithi Pravesha**: the natal tithi *and* lunar month
                            recurring (~354 days). This is Jagannatha Hora's TP chart,
                            the lunar-return counterpart of the solar Varshaphal.

        Returns the pravesha window (start/end), the chart cast at its opening
        instant, and the standard Muntha / year-lord / Tajaka-yoga block."""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}
        try:
            from datetime import datetime, timezone as _utc, timedelta
            from jhora.panchanga import vratha

            _set_ayanamsa(ayanamsa)

            y, m, d = map(int, dob.split("-"))
            tp_ = tob.split(":")
            hour = int(tp_[0]); minute = int(tp_[1]) if len(tp_) > 1 else 0
            # Seconds are honoured here (they are ignored elsewhere) because the
            # compressed Tithi Ashtottari is unusually sensitive to them: the
            # balance rule winds the elongation back by up to a maha span, so the
            # whole table moves ~5.7 days per degree of birth elongation — about
            # 75 seconds of dasha for every 1 second of birth time.
            second = int(float(tp_[2])) if len(tp_) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz if tz is not None else 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            jd_dob = swe.julday(y, m, d, hour + minute / 60.0 + second / 3600.0)

            if date:
                ry, rm, rd = map(int, date.split("-"))
            else:
                now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
                ry, rm, rd = now.year, now.month, now.day
            jd_ref = swe.julday(ry, rm, rd, 12.0)

            birth_tithi = AstrologyCompute._tithi_num(jd_dob, place_obj)
            label = None
            paksha = None

            if rung == "annual":
                # Tithi Pravesha: find the date in `year` where the natal tithi +
                # lunar month recur, then take the window to the next year's.
                target_year = int(year) if year else ry
                birth_elongation = vta.elongation(jd_dob, place_obj)

                def tp_for(yr):
                    """The pravesha *instant*, exact in elongation.

                    The engine's search gives the right day but interpolates the
                    time linearly between the tithi's start and end, landing ~45-50
                    minutes early. Refining to the moment the Moon-Sun elongation
                    actually regains its birth value matters twice over: the chart
                    is cast at this instant (50 minutes is ~12 deg of ascendant),
                    and the compressed dasha winds its balance back by up to a full
                    maha span, which amplifies the error ~50x into a 2.5-day shift
                    of every period in the table."""
                    rows = AstrologyCompute._tithi_pravesha_dates(
                        y, m, d, hour, minute, place_obj, yr)
                    if not rows:
                        return None, None
                    (ty, tm, td), t_time, _t1, tp_label = rows[0]
                    seed = (utils.julian_day_number(drik.Date(ty, tm, td), (0, 0, 0))
                            + t_time / 24.0)
                    exact = vta.refine_pravesha(seed, birth_elongation, place_obj)
                    return (exact if exact is not None else seed), tp_label

                start_jd, tp_label = tp_for(target_year)
                if start_jd is None:
                    return {"error": "Tithi Pravesha could not be resolved for that year",
                            "status": "failed"}
                if not year and start_jd > jd_ref:
                    # This year's TP hasn't happened yet — we're still in last year's window.
                    prev_jd, prev_label = tp_for(target_year - 1)
                    if prev_jd is not None:
                        target_year -= 1
                        start_jd, tp_label = prev_jd, prev_label

                end_jd, _ = tp_for(target_year + 1)
                if end_jd is None:
                    # Next year's TP couldn't be resolved — close the window with a
                    # mean lunar year rather than failing the whole reading.
                    end_jd = start_jd + 354.367
                label = (tp_label or "").strip(" /")
                age = target_year - y
                window_extra = {"tp_year": target_year}
            else:
                if rung == "tithi":
                    w = AstrologyCompute._tithi_window(jd_ref, place_obj)
                    label = f"Tithi {w['index']}"
                elif rung == "paksha":
                    w = AstrologyCompute._paksha_window(jd_ref, place_obj)
                    paksha = w["paksha"]
                    label = f"{w['paksha']} Paksha"
                elif rung == "month":
                    w = AstrologyCompute._lunar_month_window(jd_ref, place_obj, birth_tithi)
                    if not w:
                        return {"error": "Could not resolve the lunar month window",
                                "status": "failed"}
                    label = f"Birth-tithi ({birth_tithi}) return"
                else:
                    return {"error": f"Unknown lunar rung '{rung}'", "status": "failed"}
                start_jd, end_jd = w["start_jd"], w["end_jd"]
                age = max(0, int((jd_ref - jd_dob) / 365.2425))
                window_extra = {"tithi_index": w.get("tithi_index")}

            sy_, sm_, sd_, _sf = utils.jd_to_gregorian(start_jd)
            ey_, em_, ed_, _ef = utils.jd_to_gregorian(end_jd)

            # Cast the D1 chart at the instant the window opens. The annual rung
            # (Tithi Pravesha) is the full-dress chart: it also carries the Sahams
            # and its own dasha, so the Solar/Lunar annual views are symmetrical.
            is_annual = rung == "annual"
            cht = charts.divisional_chart(start_jd, place_obj, divisional_chart_factor=1)
            block = AstrologyCompute._pravesha_block(
                cht, jd_dob, place_obj, age,
                with_sahams=is_annual, jd_event=start_jd)

            # Jagannatha Hora pairs the Tithi Pravesha chart with **Tithi Ashtottari**
            # — a tithi-reckoned dasha for a tithi-reckoned chart. (The Tajaka annual
            # dashas — Mudda/Patyayini/Narayana — belong to the *solar* return and are
            # not carried over here.)
            #
            # It is the *compressed* form: the whole 108-unit cycle squeezed into this
            # window, as Mudda squeezes Vimsottari into the solar year. Every rung of
            # the ladder gets one, not just the annual — the compression is in
            # elongation, and each rung is a clean fraction or multiple of a turn
            # (tithi 12 deg, paksha 180, month 360, year N x 360), so the same dasha
            # tiles a day exactly as it tiles a year.
            cycle_deg = vta.cycle_degrees(start_jd, end_jd, place_obj)
            ta = AstrologyCompute.get_varsha_tithi_ashtottari(
                start_jd, place_obj, cycle_deg, rung=rung)
            tithi_ashtottari = ta if ta.get("status") == "success" else None

            return {
                "status": "success",
                "basis": "lunar",
                "rung": rung,
                "label": label,
                "paksha": paksha,
                "birth_tithi": birth_tithi,
                "window": {
                    "start": f"{sy_:04d}-{sm_:02d}-{sd_:02d}",
                    "end": f"{ey_:04d}-{em_:02d}-{ed_:02d}",
                    # The chart is cast at the instant, not the day — surface it, so
                    # the lagna can be checked against JHora's own TP chart.
                    "start_at": _iso_datetime(start_jd),
                    "end_at": _iso_datetime(end_jd),
                    "span_days": round(end_jd - start_jd, 2),
                    "age": age,
                    **window_extra,
                },
                # `tithi_ashtottari` on every rung; `annual_dasha` stays as the
                # annual rung's alias so the Varshaphal page can read the same key
                # for the solar (Mudda/Patyayini/Narayana) and lunar sides.
                "tithi_ashtottari": tithi_ashtottari,
                "annual_dasha": tithi_ashtottari if is_annual else None,
                **block,
            }
        except Exception as e:
            print(f"Lunar-pravesha ({rung}) error: {e}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_tithi_pravesha(dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None, year: Optional[int] = None,
                           date: Optional[str] = None,
                           ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """**Tithi Pravesha** — the annual *lunar*-return chart (the natal tithi and
        lunar month recurring, ~354 days). The lunar counterpart of Varshaphal's
        solar return, and the chart Jagannatha Hora calls the TP chart."""
        return AstrologyCompute.get_lunar_pravesha(
            "annual", dob, tob, place, lat=lat, lon=lon, tz=tz, date=date,
            year=year, ayanamsa=ayanamsa)
