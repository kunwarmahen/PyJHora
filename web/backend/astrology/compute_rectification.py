"""Birth-time rectification (suddhi rules and life-events scan).

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


class RectificationMixin:

    @staticmethod
    def get_birth_time_rectification(dob: str, tob: str, place: str,
                                     lat: Optional[float] = None, lon: Optional[float] = None,
                                     tz: Optional[float] = None,
                                     ayanamsa: str = DEFAULT_AYANAMSA,
                                     method: str = "nakshatra",
                                     gender: Optional[int] = None) -> Dict:
        """EXPERIMENTAL birth-time rectification (BV Raman suddhi methods).

        Jyotir AI itself flags these "experimental - accuracy not guaranteed", so the
        result is framed as a *suggestion to verify*, never an authoritative correction.
        Nudges the entered time within +/-(step*loop) minutes until the chosen suddhi
        check is satisfied and returns entered-vs-suggested time, the delta, which rule
        fired, and before/after chart summaries so the caller can render both kundalis.

        method: "nakshatra" (nakshatra suddhi - self-serve, no extra input),
                "lagna" (lagna suddhi) or "janma" (janma suddhi, needs `gender`:
                0=male, 1=female).
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}

        method_labels = {
            "nakshatra": "Nakshatra Suddhi",
            "lagna": "Lagna Suddhi",
            "janma": "Janma Suddhi",
        }
        if method not in method_labels:
            return {"error": f"Unknown method '{method}'", "status": "failed"}
        if method == "janma" and gender not in (0, 1):
            return {"error": "Janma suddhi requires gender (0=male, 1=female)",
                    "status": "failed"}

        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz or 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            base_fh = hour + minute / 60.0 + second / 3600.0
            jd = swe.julday(year, month, day, base_fh)

            step = float(const.birth_rectification_step_minutes)
            loop_count = int(const.birth_rectification_loop_count)
            window_minutes = round(step * loop_count, 2)

            adjust_minutes = None   # None => could not converge within the window
            already_ok = False

            if method == "nakshatra":
                # The engine self-derives the expected janma star from the birth-time
                # ishtakaal and returns: 0 (already matches), a revised (h,m,s) tuple,
                # or [rectification_required, closest_star] when it could not converge.
                res = drik._birthtime_rectification_nakshathra_suddhi(jd, place_obj)
                if isinstance(res, tuple):
                    rh, rm, rs = float(res[0]), float(res[1]), float(res[2])
                    new_fh = rh + rm / 60.0 + rs / 3600.0
                    # The engine returns only a time-of-day (no date), so a converged
                    # time that crossed midnight looks ~24h away. The search is bounded
                    # to +/-window minutes, so wrap the raw diff into the nearest
                    # +/-12h to recover the true (small) signed delta.
                    raw = ((new_fh - base_fh) + 12.0) % 24.0 - 12.0
                    adjust_minutes = round(raw * 60.0, 4)
                elif isinstance(res, (int, float)) and not isinstance(res, bool):
                    adjust_minutes = 0.0
                    already_ok = True
                else:
                    adjust_minutes = None  # did not converge
            else:
                # lagna/janma suddhi only return a bool (True => rectification needed),
                # so wrap them in a symmetric +/- search that mirrors the engine's own
                # nakshatra loop (try +l, then -l; first satisfied time wins).
                def _needs(jdx):
                    if method == "lagna":
                        return drik._birthtime_rectification_lagna_suddhi(jdx, place_obj)
                    return drik._birthtime_rectification_janma_suddhi(jdx, place_obj, gender)

                if not _needs(jd):
                    adjust_minutes = 0.0
                    already_ok = True
                else:
                    for l in range(1, loop_count + 1):
                        found = False
                        for sign in (1, -1):
                            adj = sign * l * step
                            if not _needs(jd + adj / 1440.0):
                                adjust_minutes = round(adj, 4)
                                found = True
                                break
                        if found:
                            break

            def _tob_str(h, m, s):
                return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

            entered = {
                "dob": dob,
                "tob": _tob_str(hour, minute, second),
            }

            suggested = None
            after_chart = None
            if adjust_minutes is not None and abs(adjust_minutes) > 1e-6:
                jd_new = jd + adjust_minutes / 1440.0
                ny, nm, nd, nfh = utils.jd_to_gregorian(jd_new)
                sh, smn, ss = utils.to_dms(nfh, as_string=False)
                suggested = {
                    "dob": f"{int(ny):04d}-{int(nm):02d}-{int(nd):02d}",
                    "tob": _tob_str(sh, smn, ss),
                }

            # Before/after chart summaries (reuse the birth-chart renderer so the page
            # can draw both kundalis with the same component).
            before_chart = AstrologyCompute.calculate_birth_chart(
                dob, entered["tob"], place, lat, lon, tz, ayanamsa)
            if suggested is not None:
                after_chart = AstrologyCompute.calculate_birth_chart(
                    suggested["dob"], suggested["tob"], place, lat, lon, tz, ayanamsa)

            def _moon(chart):
                try:
                    m = chart["d1_chart"]["Moon"]
                    return {"nakshatra": m.get("nakshatra"), "pada": m.get("nakshatra_pada"),
                            "sign_name": m.get("sign_name")}
                except Exception:
                    return None

            def _lagna(chart):
                try:
                    la = chart.get("lagna", {})
                    return {"sign_name": la.get("sign_name"), "nakshatra": la.get("nakshatra"),
                            "pada": la.get("nakshatra_pada")}
                except Exception:
                    return None

            rectified = suggested is not None
            if rectified:
                note = ("Experimental suggestion - the entered time did not satisfy the "
                        f"{method_labels[method]} check; the closest time within "
                        f"+/-{int(window_minutes)} min that does is shown. Verify against "
                        "known life events; this is a heuristic, not authoritative.")
            elif already_ok:
                note = (f"The entered time already satisfies the {method_labels[method]} "
                        "check - no rectification suggested.")
            else:
                note = (f"Could not rectify within +/-{int(window_minutes)} min using "
                        f"{method_labels[method]}. Try another method or a wider review.")

            return {
                "status": "success",
                "experimental": True,
                "method": method,
                "method_label": method_labels[method],
                "gender": gender,
                "entered": entered,
                "suggested": suggested,
                "delta_minutes": adjust_minutes,
                "rectified": rectified,
                "already_consistent": already_ok,
                "converged": adjust_minutes is not None,
                "window_minutes": window_minutes,
                "step_minutes": step,
                "before": {"moon": _moon(before_chart), "lagna": _lagna(before_chart)},
                "after": ({"moon": _moon(after_chart), "lagna": _lagna(after_chart)}
                          if after_chart else None),
                "before_chart": before_chart,
                "after_chart": after_chart,
                "note": note,
            }
        except Exception as e:
            print(f"Birth-time rectification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)

    @staticmethod
    def get_event_rectification(dob: str, tob: str, place: str,
                                events: List[Dict],
                                lat: Optional[float] = None, lon: Optional[float] = None,
                                tz: Optional[float] = None,
                                ayanamsa: str = DEFAULT_AYANAMSA,
                                window_minutes: int = 120) -> Dict:
        """EXPERIMENTAL event-based birth-time rectification.

        Given a set of dated life events, scan candidate birth times within the day
        and pick the one whose Vimsottari dasha (maha+bhukti running at each event)
        and Jupiter/Saturn transits best match the events' classical significators.
        Deterministic + auditable: returns the per-event matches behind the score.

        events: [{"type": <EVENT_SIGNIFICATORS key>, "date": "YYYY-MM-DD"}, ...]
        window_minutes: half-window searched around the entered time (clamped to the
                        same calendar day). e.g. 120 => +/-2h; 720 => whole day.
        """
        if not ENGINE_AVAILABLE:
            return {"error": "Jyotir AI engine not available", "status": "failed"}

        # Validate + normalise events.
        clean_events = []
        for ev in (events or []):
            etype = (ev or {}).get("type")
            edate = (ev or {}).get("date")
            if etype not in EVENT_SIGNIFICATORS or not edate:
                continue
            try:
                ey, em, ed = map(int, str(edate).split("-")[:3])
                clean_events.append({"type": etype, "date": f"{ey:04d}-{em:02d}-{ed:02d}",
                                     "ymd": (ey, em, ed)})
            except Exception:
                continue
        if not clean_events:
            return {"error": "Provide at least one dated life event.", "status": "failed"}

        try:
            _set_ayanamsa(ayanamsa)
            year, month, day = map(int, dob.split("-"))
            tp = tob.split(":")
            hour = int(tp[0]); minute = int(tp[1]) if len(tp) > 1 else 0
            second = int(tp[2]) if len(tp) > 2 else 0
            if not lat or not lon:
                lat, lon = 13.0827, 80.2707
            tz_offset = tz or 5.5
            place_obj = drik.Place(place, lat, lon, tz_offset)
            base_fh = hour + minute / 60.0 + second / 3600.0

            # Precompute each event's JD (noon local) + the transiting Jupiter/Saturn
            # signs on that day (birth-time-independent → computed once per event).
            for ev in clean_events:
                ey, em, ed = ev["ymd"]
                ev_jd = swe.julday(ey, em, ed, 12.0)
                ev["jd"] = ev_jd
                tchart = charts.rasi_chart(ev_jd, place_obj)
                tsigns = {pi: rasi for pi, (rasi, _deg) in tchart[1:]}
                ev["jup_sign"] = tsigns.get(4)
                ev["sat_sign"] = tsigns.get(6)

            yd = vimsottari.year_duration
            vdict = vimsottari.vimsottari_dict

            def _periods_for(jd):
                """Flat Vimsottari maha+bhukti timeline: [(start_jd, end_jd, maha, bhukti)]."""
                mahad = vimsottari.vimsottari_mahadasa(jd, place_obj)
                smd = sorted(mahad.items(), key=lambda x: x[1])
                out = []
                for i, (mlord, mstart) in enumerate(smd):
                    mend = smd[i + 1][1] if i + 1 < len(smd) else mstart + vdict[mlord] * yd
                    bh = vimsottari._vimsottari_bhukti(mlord, mstart)
                    sbh = sorted(bh.items(), key=lambda x: x[1])
                    for j, (blord, bstart) in enumerate(sbh):
                        bend = sbh[j + 1][1] if j + 1 < len(sbh) else mend
                        out.append((bstart, bend, mlord, blord))
                return out

            def _lords_at(periods, ev_jd):
                for (s, e, m, b) in periods:
                    if s <= ev_jd < e:
                        return m, b
                # Before the first / after the last computed period.
                if periods and ev_jd < periods[0][0]:
                    return periods[0][2], periods[0][3]
                return (periods[-1][2], periods[-1][3]) if periods else (None, None)

            def _score_event(etype, maha, bhukti, lagna_sign, planet_signs, jup_sign, sat_sign):
                sig = EVENT_SIGNIFICATORS[etype]
                houses, karakas = sig["houses"], sig["karakas"]
                house_lords = {SIGN_LORD[(lagna_sign + h - 1) % 12] for h in houses}
                in_sig = {pi for pi, ps in planet_signs.items()
                          if (((ps - lagna_sign) % 12) + 1) in houses}
                s = 0.0
                reasons = []
                mn = PLANET_NAMES.get(maha, "?")
                bn = PLANET_NAMES.get(bhukti, "?")
                if maha in house_lords:
                    s += 3.0; reasons.append(f"Mahadasha {mn} rules a house of {etype}")
                if maha in karakas:
                    s += 3.0; reasons.append(f"Mahadasha {mn} is a natural significator of {etype}")
                if maha in in_sig:
                    s += 1.5; reasons.append(f"Mahadasha {mn} occupies a house of {etype}")
                if bhukti in house_lords:
                    s += 1.5; reasons.append(f"Bhukti {bn} rules a house of {etype}")
                if bhukti in karakas:
                    s += 1.5; reasons.append(f"Bhukti {bn} is a natural significator of {etype}")
                if bhukti in in_sig:
                    s += 0.75; reasons.append(f"Bhukti {bn} occupies a house of {etype}")
                if jup_sign is not None and (((jup_sign - lagna_sign) % 12) + 1) in houses:
                    s += 0.5; reasons.append("Jupiter transits a house of " + etype)
                if sat_sign is not None and (((sat_sign - lagna_sign) % 12) + 1) in houses:
                    s += 0.5; reasons.append("Saturn transits a house of " + etype)
                return s, reasons

            def _eval(fh):
                jd = swe.julday(year, month, day, fh)
                d1 = charts.rasi_chart(jd, place_obj)
                lagna_sign = int(d1[0][1][0])
                planet_signs = {pi: int(rasi) for pi, (rasi, _d) in d1[1:]}
                periods = _periods_for(jd)
                total = 0.0
                details = []
                for ev in clean_events:
                    maha, bhukti = _lords_at(periods, ev["jd"])
                    sc, reasons = _score_event(ev["type"], maha, bhukti, lagna_sign,
                                               planet_signs, ev["jup_sign"], ev["sat_sign"])
                    total += sc
                    details.append({
                        "type": ev["type"], "date": ev["date"],
                        "maha": PLANET_NAMES.get(maha), "bhukti": PLANET_NAMES.get(bhukti),
                        "score": round(sc, 2), "matched": reasons,
                    })
                return total, details, lagna_sign

            # Two-pass scan: coarse over the (clamped) window, then fine around the best.
            lo = max(0.0, base_fh - window_minutes / 60.0)
            hi = min(24.0 - 1e-6, base_fh + window_minutes / 60.0)

            def _scan(a, b, step_min):
                best = None
                fh = a
                step = step_min / 60.0
                while fh <= b + 1e-9:
                    total, _details, _lag = _eval(fh)
                    if best is None or total > best[1]:
                        best = (fh, total)
                    fh += step
                return best

            coarse = _scan(lo, hi, 15.0)
            c_fh = coarse[0]
            fine = _scan(max(0.0, c_fh - 0.25), min(24.0 - 1e-6, c_fh + 0.25), 2.0)
            best_fh = fine[0] if fine[1] >= coarse[1] else c_fh

            best_total, best_details, _lag = _eval(best_fh)
            base_total, base_details, _blag = _eval(base_fh)

            sh, sm, ss = utils.to_dms(best_fh, as_string=False)
            suggested_tob = f"{int(sh):02d}:{int(sm):02d}:{int(ss):02d}"
            entered_tob = f"{hour:02d}:{minute:02d}:{second:02d}"
            delta_minutes = round((best_fh - base_fh) * 60.0, 1)
            changed = abs(delta_minutes) > 0.5

            # A rough, honest 0-100 "fit" of the best time (≈6 pts = one strong event).
            n = len(clean_events)
            confidence = max(5, min(95, round(best_total / (n * 6.0) * 100)))

            before_chart = AstrologyCompute.calculate_birth_chart(
                dob, entered_tob, place, lat, lon, tz, ayanamsa)
            after_chart = AstrologyCompute.calculate_birth_chart(
                dob, suggested_tob, place, lat, lon, tz, ayanamsa) if changed else None

            def _moon(chart):
                try:
                    m = chart["d1_chart"]["Moon"]
                    return {"nakshatra": m.get("nakshatra"), "pada": m.get("nakshatra_pada"),
                            "sign_name": m.get("sign_name")}
                except Exception:
                    return None

            def _lagna(chart):
                try:
                    la = chart.get("lagna", {})
                    return {"sign_name": la.get("sign_name"), "nakshatra": la.get("nakshatra"),
                            "pada": la.get("nakshatra_pada")}
                except Exception:
                    return None

            if changed:
                note = (f"Experimental — of the candidate times searched (±{window_minutes} min), "
                        f"{suggested_tob} best matches the {n} event(s) supplied "
                        f"(fit ≈ {confidence}%). This is a heuristic; verify against more events "
                        "and reliable records.")
            else:
                note = (f"The entered time already scores best against the {n} event(s) supplied "
                        f"(fit ≈ {confidence}%). Add more events or widen the window to test further.")

            return {
                "status": "success",
                "experimental": True,
                "method": "events",
                "method_label": "Life-events",
                "entered": {"dob": dob, "tob": entered_tob},
                "suggested": {"dob": dob, "tob": suggested_tob} if changed else None,
                "delta_minutes": delta_minutes,
                "rectified": changed,
                "window_minutes": window_minutes,
                "score": round(best_total, 2),
                "base_score": round(base_total, 2),
                "confidence": confidence,
                "events": best_details,
                "entered_events": base_details,
                "before": {"moon": _moon(before_chart), "lagna": _lagna(before_chart)},
                "after": ({"moon": _moon(after_chart), "lagna": _lagna(after_chart)}
                          if after_chart else None),
                "before_chart": before_chart,
                "after_chart": after_chart,
                "note": note,
            }
        except Exception as e:
            print(f"Event rectification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": str(e), "status": "failed"}
        finally:
            _set_ayanamsa(DEFAULT_AYANAMSA)
