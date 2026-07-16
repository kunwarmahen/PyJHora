"""Daily / fortnightly / monthly digest cards.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class DigestsMixin:

    # ── Daily digest (§16) ─────────────────────────────────────────────────
    @staticmethod
    def get_daily_digest(dob: str, tob: str, place: str,
                         lat: Optional[float] = None, lon: Optional[float] = None,
                         tz: Optional[float] = None, date: Optional[str] = None,
                         current_time: Optional[str] = None,
                         current_tz: Optional[float] = None,
                         basis: str = "solar",
                         ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A personalized "Today" card: the day's Panchanga at the person's place,
        their running Vimsottari dasha (flagging a change if the current Bhukti
        ends within ~30 days), the headline transits (Sade-Sati / Jupiter's house
        from natal Moon, retrograde grahas, next Jupiter/Saturn ingress), and a
        list of plain highlight strings. Assembled from the existing panchanga /
        dasha / transit computes.

        With `basis="lunar"` the card also carries the **tithi pravesha** chart —
        the D1 cast at the moment the running tithi opened, with its Muntha and
        Tajaka yogas. (The solar ladder has no daily rung, so `basis="solar"`
        leaves the card chart-less, exactly as before.)"""
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            tz_offset = tz if tz is not None else 5.5
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            date_str = date or f"{local_now.year:04d}-{local_now.month:02d}-{local_now.day:02d}"

            panch = AstrologyCompute.get_panchanga(
                date=date_str, place=place, lat=lat, lon=lon, tz=tz_offset)
            transits = AstrologyCompute.get_transits(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                current_date=date_str, current_time=current_time,
                current_tz=current_tz, ayanamsa=ayanamsa)
            dashas = AstrologyCompute.get_dashas(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz)

            highlights = []

            # Panchanga headline.
            if panch.get("status") == "success":
                # tithi['name'] already carries the paksha prefix (e.g. "Krishna Tritiya").
                highlights.append(
                    f"{panch['vaara']['name']} · {panch['tithi']['name']}, "
                    f"{panch['nakshatra']['name']} nakshatra")

            # Dasha snapshot + imminent change.
            dasha_block = None
            if dashas.get("status") != "failed" and dashas.get("current_dasha"):
                cur = dashas["current_dasha"]
                bhukti_periods = (dashas.get("current_bhukthi") or {}).get("periods", [])
                today = datetime.strptime(date_str, "%Y-%m-%d")
                running_bhukti = None
                for b in bhukti_periods:
                    try:
                        bs = datetime.strptime(b["start_date"], "%Y-%m-%d")
                        be = datetime.strptime(b["end_date"], "%Y-%m-%d")
                    except Exception:
                        continue
                    if bs <= today <= be:
                        running_bhukti = b
                        break
                dasha_block = {
                    "maha_lord": cur["lord"],
                    "maha_end": cur["end_date"],
                    "bhukti": running_bhukti,
                    "next_maha": (dashas.get("next_dasha") or {}).get("lord"),
                }
                highlights.append(
                    f"{cur['lord']} Mahadasha"
                    + (f", {running_bhukti['lord']} Bhukti" if running_bhukti else ""))
                # Bhukti change within 30 days?
                if running_bhukti:
                    try:
                        be = datetime.strptime(running_bhukti["end_date"], "%Y-%m-%d")
                        days_left = (be - today).days
                        if 0 <= days_left <= 30:
                            highlights.append(
                                f"⚠ {running_bhukti['lord']} Bhukti ends in {days_left} "
                                f"day(s) — a dasha change is near")
                    except Exception:
                        pass

            # Transit highlights: Sade-Sati, Jupiter from Moon, retrogrades, ingresses.
            transit_block = None
            if transits.get("status") == "success":
                planets = transits.get("planets", {})
                sat = planets.get("Saturn", {})
                jup = planets.get("Jupiter", {})
                def _bindu_note(p):
                    # Ashtakavarga support for the sign a slow mover now occupies (§2.4).
                    b = p.get("bav_bindus")
                    if b is None:
                        return ""
                    return (f" — {b}-bindu sign in its own Ashtakavarga "
                            f"({p.get('bindu_label', '').lower()})")
                if sat.get("house_from_moon") in (12, 1, 2):
                    phase = {12: "first (rising)", 1: "peak (janma)",
                             2: "final (setting)"}[sat["house_from_moon"]]
                    highlights.append(f"Saturn is in your {sat['house_from_moon']}th from "
                                      f"the Moon — Sade-Sati {phase} phase"
                                      + _bindu_note(sat))
                if jup:
                    highlights.append(
                        f"Jupiter transits your {jup.get('house_from_moon')}th from the Moon "
                        f"({jup.get('sign_name')}){_bindu_note(jup)}")
                retro = [name for name, p in planets.items() if p.get("retrograde")]
                if retro:
                    highlights.append("Retrograde now: " + ", ".join(retro))
                transit_block = {
                    "planets": planets,
                    "upcoming": transits.get("upcoming", []),
                    "natal": transits.get("natal", {}),
                    "retrograde": retro,
                    "sade_sati": sat.get("house_from_moon") in (12, 1, 2),
                }
                for u in transits.get("upcoming", []):
                    highlights.append(
                        f"{u['planet']} enters {u['to_sign']} on {u['date']}")

            # On the lunar basis the day carries its tithi-pravesha chart.
            pravesh = None
            if basis == "lunar":
                tp = AstrologyCompute.get_lunar_pravesha(
                    "tithi", dob, tob, place, lat=lat, lon=lon, tz=tz,
                    date=date_str, ayanamsa=ayanamsa)
                if tp.get("status") == "success":
                    pravesh = tp
                    # No Muntha here: it advances one sign per YEAR of age, so it is
                    # the same value all year and says nothing about *this day*.
                    # (Same reason it is hidden on the short rungs of the TP page.)
                    highlights.append(
                        f"Tithi Pravesha lagna: {tp['lagna']['sign_name']}")
                    for yg in tp.get("tajaka_yogas", [])[:3]:
                        pair = f" ({'/'.join(yg['pair'])})" if yg.get("pair") else ""
                        highlights.append(f"Tajaka yoga — {yg['name']}{pair}")

            return {
                "status": "success",
                "date": date_str,
                "place": place,
                "basis": basis,
                "panchanga": panch if panch.get("status") == "success" else None,
                "dasha": dasha_block,
                "transits": transit_block,
                "pravesh": pravesh,
                "highlights": highlights,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def _period_digest(period: str, dob: str, tob: str, place: str,
                       lat: Optional[float] = None, lon: Optional[float] = None,
                       tz: Optional[float] = None, date: Optional[str] = None,
                       basis: str = "solar",
                       ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """Shared builder for the fortnightly and monthly readings — a
        longer-horizon cousin of :meth:`get_daily_digest`. Blends the running
        Vimsottari dasha/bhukti with the transit events (ingresses + retrograde
        stations) landing inside the window, plus the window's opening Panchanga,
        and anchors the whole reading to a **progressed (pravesha) chart**.

        Which chart — and therefore which window — depends on `basis`:

          * ``period="fortnight"`` → always the **Paksha Pravesha** (the running
            Shukla/Krishna fortnight, ~14.8d). The solar ladder has no fortnight
            rung, so this rung is lunar by definition.
          * ``period="month"``, ``basis="solar"`` → **Maasa Pravesha** (Tajaka
            monthly solar return, ~30.4d).
          * ``period="month"``, ``basis="lunar"`` → the **birth-tithi return**
            (lunar month, ~29.5d).
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available"}
        try:
            from datetime import datetime, timezone as _utc, timedelta

            tz_offset = tz if tz is not None else 5.5
            local_now = datetime.now(_utc.utc) + timedelta(hours=tz_offset)
            today_str = date or f"{local_now.year:04d}-{local_now.month:02d}-{local_now.day:02d}"

            # The **scan window** (events + header dates) is the pravesha window the
            # day falls in; the **snapshot** (live positions/dasha) stays anchored to
            # today. The fortnight rung is lunar-only — there is no solar fortnight.
            if period == "fortnight":
                basis = "lunar"
            pravesh = None

            if period == "fortnight":
                pravesh = AstrologyCompute.get_lunar_pravesha(
                    "paksha", dob, tob, place, lat=lat, lon=lon, tz=tz,
                    date=today_str, ayanamsa=ayanamsa)
            elif basis == "lunar":
                pravesh = AstrologyCompute.get_lunar_pravesha(
                    "month", dob, tob, place, lat=lat, lon=lon, tz=tz,
                    date=today_str, ayanamsa=ayanamsa)
            else:
                pravesh = AstrologyCompute.get_masa_pravesh(
                    dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                    date=today_str, ayanamsa=ayanamsa)

            if pravesh and pravesh.get("status") == "success":
                start_str = pravesh["window"]["start"]
                end_str = pravesh["window"]["end"]
            else:
                # Pravesha failed — fall back to a plain forward window so the
                # reading still renders (transits + dasha remain valid).
                pravesh = None
                start_str = today_str
                _sy, _sm, _sd = map(int, start_str.split("-"))
                _fallback = 14 if period == "fortnight" else 30
                ey, em, ed, _ = utils.jd_to_gregorian(
                    swe.julday(_sy, _sm, _sd, 12.0) + _fallback)
                end_str = f"{ey:04d}-{em:02d}-{ed:02d}"

            sy, sm, sd = map(int, start_str.split("-"))
            start_jd = swe.julday(sy, sm, sd, 12.0)
            ey, em, ed = map(int, end_str.split("-"))
            end_jd = swe.julday(ey, em, ed, 12.0)
            span_days = int(round(end_jd - start_jd))

            # Live snapshot is anchored to today; Panchanga to the window's opening.
            panch = AstrologyCompute.get_panchanga(
                date=start_str, place=place, lat=lat, lon=lon, tz=tz_offset)
            transits = AstrologyCompute.get_transits(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                current_date=today_str, ayanamsa=ayanamsa)
            dashas = AstrologyCompute.get_dashas(
                dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz)
            events = AstrologyCompute._transit_events_in_window(
                place, lat, lon, tz_offset, start_str, end_jd)

            # What the window is *called* — this is what the reading leads with.
            if period == "fortnight":
                when = f"{(pravesh or {}).get('paksha') or 'lunar'} Paksha (fortnight)"
            elif basis == "lunar":
                when = "lunar month (birth-tithi return)"
            else:
                when = "solar month (Maasa Pravesha)"
            highlights: List[str] = [
                f"Your {when}: {start_str} → {end_str} ({span_days} days)"]

            # Panchanga headline at the window's opening.
            if panch.get("status") == "success":
                verb = "Opened on"
                highlights.append(
                    f"{verb} {panch['vaara']['name']} · {panch['tithi']['name']}, "
                    f"{panch['nakshatra']['name']} nakshatra")

            # Dasha snapshot + any change inside the window.
            dasha_block = None
            if dashas.get("status") != "failed" and dashas.get("current_dasha"):
                cur = dashas["current_dasha"]
                bhukti_periods = (dashas.get("current_bhukthi") or {}).get("periods", [])
                today = datetime.strptime(today_str, "%Y-%m-%d")
                running_bhukti = None
                for b in bhukti_periods:
                    try:
                        bs = datetime.strptime(b["start_date"], "%Y-%m-%d")
                        be = datetime.strptime(b["end_date"], "%Y-%m-%d")
                    except Exception:
                        continue
                    if bs <= today <= be:
                        running_bhukti = b
                        break
                dasha_block = {
                    "maha_lord": cur["lord"],
                    "maha_end": cur["end_date"],
                    "bhukti": running_bhukti,
                    "next_maha": (dashas.get("next_dasha") or {}).get("lord"),
                }
                highlights.append(
                    f"{cur['lord']} Mahadasha"
                    + (f", {running_bhukti['lord']} Bhukti" if running_bhukti else ""))
                if running_bhukti:
                    try:
                        be = datetime.strptime(running_bhukti["end_date"], "%Y-%m-%d")
                        days_left = (be - today).days
                        days_to_end = (datetime.strptime(end_str, "%Y-%m-%d") - today).days
                        if 0 <= days_left <= max(0, days_to_end):
                            period_noun = "fortnight" if period == "fortnight" else "month"
                            highlights.append(
                                f"⚠ {running_bhukti['lord']} Bhukti ends {running_bhukti['end_date']} "
                                f"— a dasha change falls within this {period_noun}")
                    except Exception:
                        pass

            # Transit snapshot (positions/retro now) + all window events.
            transit_block = None
            if transits.get("status") == "success":
                planets = transits.get("planets", {})
                sat = planets.get("Saturn", {})
                jup = planets.get("Jupiter", {})
                if sat.get("house_from_moon") in (12, 1, 2):
                    phase = {12: "first (rising)", 1: "peak (janma)",
                             2: "final (setting)"}[sat["house_from_moon"]]
                    highlights.append(f"Saturn in your {sat['house_from_moon']}th from the "
                                      f"Moon — Sade-Sati {phase} phase")
                if jup:
                    highlights.append(
                        f"Jupiter transits your {jup.get('house_from_moon')}th from the Moon "
                        f"({jup.get('sign_name')})")
                retro = [name for name, p in planets.items() if p.get("retrograde")]
                if retro:
                    highlights.append("Retrograde now: " + ", ".join(retro))
                transit_block = {
                    "planets": planets,
                    "natal": transits.get("natal", {}),
                    "retrograde": retro,
                    "sade_sati": sat.get("house_from_moon") in (12, 1, 2),
                }
            for ev in events:
                highlights.append(f"{ev['text']} on {ev['date']}")

            # Progressed-chart headline, named for the rung it was actually cast on.
            if pravesh:
                if period == "fortnight":
                    chart_name = f"{pravesh.get('paksha', 'Paksha')} Paksha Pravesha"
                elif basis == "lunar":
                    chart_name = "Lunar-month (birth-tithi return)"
                else:
                    chart_name = "Maasa Pravesha"
                # No Muntha: it advances one sign per YEAR of age, so it is identical
                # for every fortnight and every month of a given year — a constant
                # dressed up as news. Hidden on the TP page's short rungs for the
                # same reason.
                highlights.append(
                    f"{chart_name} lagna: {pravesh['lagna']['sign_name']}")
                for yg in pravesh.get("tajaka_yogas", [])[:3]:
                    pair = f" ({'/'.join(yg['pair'])})" if yg.get("pair") else ""
                    highlights.append(f"Tajaka yoga — {yg['name']}{pair}")

            return {
                "status": "success",
                "period": period,
                "basis": basis,
                "window_label": when,
                "start_date": start_str,
                "end_date": end_str,
                "span_days": span_days,
                "place": place,
                "panchanga": panch if panch.get("status") == "success" else None,
                "dasha": dasha_block,
                "transits": transit_block,
                "events": events,
                "pravesh": pravesh,
                "highlights": highlights,
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}

    @staticmethod
    def get_fortnightly_digest(dob: str, tob: str, place: str,
                               lat: Optional[float] = None, lon: Optional[float] = None,
                               tz: Optional[float] = None, date: Optional[str] = None,
                               basis: str = "lunar",
                               ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A personalized "This Fortnight" reading: dasha context + the transit
        events across the running **paksha** (Shukla or Krishna, ~14.8 days),
        anchored to that paksha's Pravesha chart. The fortnight is a lunar-only
        rung — Tajaka's solar ladder has no fortnight — so `basis` is ignored."""
        return AstrologyCompute._period_digest(
            "fortnight", dob, tob, place, lat=lat, lon=lon, tz=tz, date=date,
            basis="lunar", ayanamsa=ayanamsa)

    @staticmethod
    def get_monthly_digest(dob: str, tob: str, place: str,
                           lat: Optional[float] = None, lon: Optional[float] = None,
                           tz: Optional[float] = None, date: Optional[str] = None,
                           basis: str = "solar",
                           ayanamsa: str = DEFAULT_AYANAMSA) -> Dict:
        """A personalized "This Month" reading: dasha context + the month's transit
        events, anchored to a progressed monthly chart. `basis="solar"` uses the
        **Maasa Pravesha** (Tajaka monthly solar return, ~30.4d); `basis="lunar"`
        uses the **birth-tithi return** (lunar month, ~29.5d). The chosen window
        defines the reading's start/end."""
        return AstrologyCompute._period_digest(
            "month", dob, tob, place, lat=lat, lon=lon, tz=tz, date=date,
            basis=basis, ayanamsa=ayanamsa)
