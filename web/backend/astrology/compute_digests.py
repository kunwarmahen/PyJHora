"""Daily / fortnightly / monthly digest cards.

Part of the `astrology` package split (§4). Members moved verbatim from the
old single-file astrology.py; `AstrologyCompute` is bound at import time by
core.py so cross-module `AstrologyCompute.x` calls keep working.
"""
from .engine import *  # noqa: F401,F403  (constants + helpers the bodies use)

# Rebound by core.py once the composed class exists (late binding).
AstrologyCompute = None


# ── The difficult side of a day ──────────────────────────────────────────────
# A digest that can only ever report neutral facts and favourable windows reads
# the same every morning and quietly misrepresents the tradition, which is not
# shy about a hard transit. These tables name the classical difficulties so the
# card can carry them in the language a reader would meet in a panchang.

# Saturn's house from the natal Moon, in the names the tradition uses for it.
# 12/1/2 are the three phases of Sade-Sati (already reported as a highlight);
# 4 and 8 are the two shorter, sharper transits that had no representation at all.
_SANI_FROM_MOON = {
    4: ("Ardhashtama Sani", "Saturn transiting the 4th from your Moon — "
        "the classical 'half-eighth', felt in home, property and peace of mind"),
    8: ("Ashtama Sani", "Saturn transiting the 8th from your Moon — "
        "classically the most testing of Saturn's transits, asking for caution "
        "with health, obligations and anything irreversible"),
}

# Grahas whose gochara verdict is worth a caution line, most significant first,
# each tagged with how fast the verdict actually moves.
#
# This split is the anti-monotony mechanism. Saturn's verdict holds for two and a
# half years; report it every morning as though it were today's news and every
# morning reads the same, which is precisely the complaint. A "standing" caution
# is the season a reader is living through and should be named as backdrop; a
# "today" caution is what is different about this particular day. Both are
# carried, tagged, and rationed separately — see `_pick_cautions`.
_GOCHARA_CAUTION_PLANETS = {
    "Saturn": (0, "standing"),
    "Jupiter": (1, "standing"),
    "Rahu": (2, "standing"),
    "Ketu": (3, "standing"),
    "Sun": (4, "today"),
    "Mars": (5, "today"),
    "Moon": (6, "today"),
}

# At most this many caution lines. A digest listing every unfavourable graha is
# as monotonous as one listing none, and reads as doom rather than guidance.
_MAX_CAUTIONS = 4
# ...of which at most this many may be the slow-moving backdrop, so a months-long
# Saturn transit can never crowd out what is actually different about today.
_MAX_STANDING_CAUTIONS = 2


def _caution(text, scope):
    return {"text": text, "scope": scope}


def _gochara_cautions(gochara, skip_planets=()):
    """Caution entries from the Moon-referenced gochara verdicts, most significant
    first.

    Two tones, both classical and both worth saying out loud: an outright
    ``Unfavourable`` transit, and a favourable one cancelled by a *vedha* — an
    obstructing graha in the paired house. The verdict is quoted in the
    tradition's own words and then said plainly, because "Favourable but
    obstructed (vedha)" means nothing to a reader on its own.

    `skip_planets` drops grahas already reported under a more specific classical
    name — there is no point telling someone Saturn is unfavourable in the 4th
    directly under a line calling that same transit Ardhashtama Sani."""
    scored = []
    for row in (gochara or {}).get("results", []):
        planet = row.get("planet")
        if planet not in _GOCHARA_CAUTION_PLANETS or planet in skip_planets:
            continue
        house = row.get("house_from_moon")
        rank, scope = _GOCHARA_CAUTION_PLANETS[planet]
        if row.get("tone") == "bad":
            scored.append((0, rank, _caution(
                f"{planet} transits the {_ordinal(house)} from your natal Moon — "
                f"gochara: Unfavourable", scope)))
        elif row.get("tone") == "caution":
            blockers = ", ".join(row.get("obstructed_by") or []) or "another graha"
            scored.append((1, rank, _caution(
                f"{planet} is well placed in the {_ordinal(house)} from your natal "
                f"Moon but obstructed by vedha ({blockers}) — the good result is "
                f"checked, not delivered", scope)))
    scored.sort(key=lambda t: (t[0], t[1]))
    return [c for _, _, c in scored]


def _pick_cautions(cautions):
    """Ration the caution list so today's signal always gets through.

    Today-scoped entries take the first two slots, the standing backdrop takes at
    most two, and anything left over fills what remains. Without this the slow
    grahas — which are also the most 'significant' — would take every slot every
    day for months on end."""
    today = [c for c in cautions if c.get("scope") == "today"]
    standing = [c for c in cautions if c.get("scope") != "today"]
    picked = today[:2] + standing[:_MAX_STANDING_CAUTIONS] + today[2:]
    return picked[:_MAX_CAUTIONS]


def _ordinal(n):
    try:
        n = int(n)
    except (TypeError, ValueError):
        return str(n)
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _avoid_windows(panch):
    """The classical trio to keep clear of for anything new — Rahu Kalam,
    Yamaganda and Gulika Kalam. These were already computed for the panchanga
    card and simply never reached the digest, which is why a digest could name
    the day's good hour but never its bad ones."""
    out = []
    for key, label in (("rahu_kalam", "Rahu Kalam"),
                       ("yamaganda", "Yamaganda"),
                       ("gulika", "Gulika Kalam")):
        w = (panch or {}).get(key) or {}
        if w.get("start") and w.get("end"):
            out.append({"name": label, "start": w["start"], "end": w["end"]})
    return out


def _next_good_window(choghadiya, now_h):
    """The next auspicious Choghadiya window at/after ``now_h`` (local hours).

    ``choghadiya`` is the chronological day+night list from
    ``get_muhurta_subtools`` — each part a dict with ``name``/``nature``/``start``/
    ``end`` ("HH:MM"). Night parts wrap past midnight, so the clock strings are
    linearised onto a single rising axis before comparing. Returns the part dict
    (with linear-safe ``start``/``end`` strings unchanged) or None when no good
    window remains on the axis."""
    def _h(s):
        hh, mm = (s.split(":") + ["0"])[:2]
        return int(hh) + int(mm) / 60.0

    good = {"good"}
    offset = 0.0
    prev = None
    for part in choghadiya:
        s = _h(part["start"])
        if prev is not None and s < prev - 1e-6:
            offset += 24.0  # crossed midnight — bump onto the next day
        prev = s
        abs_start = s + offset
        # A part lasts until its end; if end < start it wrapped, so +24.
        e = _h(part["end"])
        abs_end = e + offset + (24.0 if e < s - 1e-6 else 0.0)
        if part.get("nature") in good and abs_end > now_h:
            return part
    return None


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

            # The classical gochara verdicts for today — the digest's only source
            # of an honestly *unfavourable* reading. Best-effort: a day without it
            # is a thinner day, not a failed one.
            try:
                gochara = AstrologyCompute.get_gochara_phala(
                    dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                    current_date=date_str, current_tz=current_tz, ayanamsa=ayanamsa)
                if gochara.get("status") != "success":
                    gochara = None
            except Exception as e:
                print(f"Daily digest gochara skipped: {e}")
                gochara = None

            highlights = []
            cautions = []
            named_planets = set()

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
                sat_house = sat.get("house_from_moon")
                if sat_house in (12, 1, 2):
                    phase = {12: "first (rising)", 1: "peak (janma)",
                             2: "final (setting)"}[sat_house]
                    highlights.append(f"Saturn is in your {sat_house}th from "
                                      f"the Moon — Sade-Sati {phase} phase"
                                      + _bindu_note(sat))
                elif sat_house in _SANI_FROM_MOON:
                    # The two hard Saturn transits outside Sade-Sati. Named, because
                    # a reader who knows the term deserves to see it, and explained,
                    # because one who doesn't deserves to know what it means.
                    label, meaning = _SANI_FROM_MOON[sat_house]
                    highlights.append(f"{label}: Saturn in your {sat_house}th from the "
                                      f"Moon" + _bindu_note(sat))
                    cautions.append(_caution(f"{label} — {meaning}", "standing"))
                    # Named here, so don't repeat it as a bare gochara verdict below.
                    named_planets.add("Saturn")
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

            # ── Best window today: the next auspicious Choghadiya from "now" ──
            # A single actionable "when to act" line — the same for everyone at a
            # place on a day, so the digest hoists it into the shared-sky header.
            action_window = None
            try:
                sub = AstrologyCompute.get_muhurta_subtools(
                    date=date_str, place=place, lat=lat, lon=lon, tz=tz_offset)
                if sub.get("status") == "success":
                    if current_time:
                        hh, mm = (current_time.split(":") + ["0"])[:2]
                        now_h = int(hh) + int(mm) / 60.0
                    else:
                        now_h = local_now.hour + local_now.minute / 60.0
                    best = _next_good_window(sub.get("choghadiya", []), now_h)
                    if best:
                        action_window = {
                            "name": best["name"], "nature": best["nature"],
                            "start": best["start"], "end": best["end"],
                            "period": best.get("period"),
                        }
                        highlights.append(
                            f"Favourable window today: {best['name']} "
                            f"{best['start']}–{best['end']} ({best.get('period', '')})".strip())
            except Exception:
                action_window = None

            # ── The other half of the day ────────────────────────────────────
            # The windows to keep clear of, and the transits the tradition calls
            # difficult. Both are shared-sky or chart-specific in the same way the
            # favourable material is, so they ride alongside it rather than in a
            # separate card.
            avoid = []
            if panch.get("status") == "success":
                avoid = _avoid_windows(panch)
                if avoid:
                    first = avoid[0]
                    highlights.append(
                        f"Avoid for anything new: {first['name']} "
                        f"{first['start']}–{first['end']}")
                # Vishti (Bhadra) is the one karana classically shunned for
                # auspicious work — the panchanga has always known it, the digest
                # never asked.
                if (panch.get("karana") or {}).get("name") == "Vishti":
                    cautions.append(_caution(
                        "Vishti (Bhadra) karana runs today — classically avoided for "
                        "beginnings, journeys and anything auspicious", "today"))

            cautions.extend(_gochara_cautions(gochara, skip_planets=named_planets))
            cautions = _pick_cautions(cautions)

            return {
                "status": "success",
                "date": date_str,
                "place": place,
                "basis": basis,
                "panchanga": panch if panch.get("status") == "success" else None,
                "dasha": dasha_block,
                "transits": transit_block,
                "pravesh": pravesh,
                "action_window": action_window,
                "avoid_windows": avoid,
                "gochara": gochara,
                "highlights": highlights,
                # Kept apart from `highlights` deliberately: a hard transit listed
                # among neutral facts reads as another neutral fact.
                "cautions": cautions,
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
            cautions: List[Dict] = []
            named_planets = set()

            # Gochara verdicts as of today, for the same reason the daily card
            # carries them: without an honestly unfavourable signal available, every
            # window reads like every other window.
            try:
                gochara = AstrologyCompute.get_gochara_phala(
                    dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                    current_date=today_str, ayanamsa=ayanamsa)
                if gochara.get("status") != "success":
                    gochara = None
            except Exception as e:
                print(f"Period digest gochara skipped: {e}")
                gochara = None

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
                sat_house = sat.get("house_from_moon")
                if sat_house in (12, 1, 2):
                    phase = {12: "first (rising)", 1: "peak (janma)",
                             2: "final (setting)"}[sat_house]
                    highlights.append(f"Saturn in your {sat_house}th from the "
                                      f"Moon — Sade-Sati {phase} phase")
                elif sat_house in _SANI_FROM_MOON:
                    label, meaning = _SANI_FROM_MOON[sat_house]
                    highlights.append(f"{label}: Saturn in your {sat_house}th from the Moon")
                    cautions.append(_caution(f"{label} — {meaning}", "standing"))
                    named_planets.add("Saturn")
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

            cautions.extend(_gochara_cautions(gochara, skip_planets=named_planets))

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
                "gochara": gochara,
                "highlights": highlights,
                "cautions": _pick_cautions(cautions),
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
