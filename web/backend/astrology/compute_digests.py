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


# ── Tara Bala, Chandra Bala, Sarvatobhadra ──────────────────────────────────
# The three day-variable, chart-specific measures the digest was missing.
#
# Everything else personal in a daily card moves slowly: the dasha turns over in
# months, Jupiter-from-Moon in a year, Sade-Sati in two and a half. So consecutive
# days looked alike no matter how the prose was tuned. **Tara Bala changes every
# single day** — it is the count from the reader's birth star to today's star, it
# is the measure a panchang reader already knows, and it is the strongest single
# answer to "why does every digest read the same".
#
# All three are `today`-scoped by construction; none of them can become backdrop.

def _tarabala_entry(janma_nak, day_nak):
    """Today's Tara as a `(entry, tone)` pair, or `(None, None)` if either star is
    unknown. The classical name is always given with its meaning attached — the
    name on its own is decoration to anyone who hasn't met it."""
    if not janma_nak or not day_nak:
        return None, None
    name, tone = _tarabala(janma_nak, day_nak)
    meaning = TARABALA_MEANING.get(name, "")
    text = f"Tara Bala: {name} — {meaning}" if meaning else f"Tara Bala: {name}"
    return _caution(text, "today"), tone


def _chandrabala_entry(house_from_moon):
    """The Moon's sign counted from the natal Moon. Changes every ~2¼ days, and the
    table has been sitting in engine.py used by nothing but muhurta."""
    if not house_from_moon:
        return None, None
    if house_from_moon in CHANDRABALA_GOOD:
        return _caution(
            f"Chandra Bala: the Moon rides your {_ordinal(house_from_moon)} from "
            f"the natal Moon — a supportive placement", "today"), "good"
    if house_from_moon in CHANDRABALA_BAD:
        return _caution(
            f"Chandra Bala: the Moon rides your {_ordinal(house_from_moon)} from "
            f"the natal Moon — classically weak; keep the day's demands modest",
            "today"), "bad"
    return None, "neutral"


# Which Sarvatobhadra anchors are worth a line in a daily note, and how to name
# each one in prose. The chakra also tracks the birth weekday and tithi group, but
# a graha facing those says far less than one landing on the birth star — and every
# extra finding eats one of only four slots. Ordered by weight.
_SBC_DIGEST_ANCHORS = {
    "janma_nakshatra": "birth star",
    "moon_sign": "Moon sign",
}

# A graha on a chakra cell stays there as long as it stays in that nakshatra or
# sign — which for Rahu and Ketu is about six weeks and for Saturn far longer. So
# the same speed split the gochara layer uses applies here: a slow graha parked on
# the birth star is the season, not the morning, and must not be allowed to occupy
# a `today` slot every day for a month and a half.
_SBC_SLOW = {"Saturn", "Jupiter", "Rahu", "Ketu"}


def _sbc_entries(sbc):
    """Support/caution entries from the Sarvatobhadra findings.

    Returns `(supports, cautions)`. A graha *occupying* the birth-star cell acts on
    it directly; one on the mirrored cell is the chakra's **facing (saamne) vedha**.

    NOTE this vedha is not the gochara vedha reported elsewhere in the same digest:
    gochara vedha is house-based obstruction counted from the Moon, this one is the
    cell opposite across the 9×9 chakra. Same word, different system — so the
    wording here names the chakra explicitly, or a reader meets "vedha" twice in
    one message and assumes the digest is repeating itself."""
    supports, cautions = [], []
    for key, label in _SBC_DIGEST_ANCHORS.items():
        for f in (sbc or {}).get("findings", []):
            if f.get("anchor") != key:
                continue
            planet = f.get("planet")
            anchor = f.get("anchor_name") or f.get("anchor_label")
            if f.get("kind") == "occupation":
                text = f"{planet} sits on your {label} {anchor} in the Sarvatobhadra chakra"
            else:
                text = (f"{planet} faces your {label} {anchor} across the "
                        f"Sarvatobhadra chakra (saamne vedha)")
            scope = "standing" if planet in _SBC_SLOW else "today"
            (supports if f.get("tone") == "supportive" else cautions).append(
                _caution(text, scope))
    return supports, cautions


def _pick_supports(supports):
    """Same rationing as `_pick_cautions`, and for the same reason: a standing
    benefic would otherwise be reported as good news every morning for a year."""
    return _pick_cautions(supports)


def _fmt_day(date_str):
    """'2026-08-06' → 'Thu 6 Aug'. Dated advice is only useful if the date is
    readable at a glance in an email; an ISO string is not."""
    from datetime import datetime
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError):
        return date_str
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def _tarabala_window(janma_nak, place, lat, lon, tz, start_str, span_days,
                     from_date=None, max_days=40):
    """Day-by-day Tara Bala across a fortnight or month.

    Returns `{"days": [...], "best": [dates], "worst": [dates]}` — every day tagged,
    plus the two shortlists a reader actually wants: which dates in this window are
    well-starred for them, and which to keep light.

    `from_date` trims those shortlists to days that have not already gone. A
    Maasa Pravesha month opens on the solar ingress, which can be three weeks
    before the reader opens the digest — advice about last Tuesday is noise.

    This is the fortnightly/monthly digests' answer to the same monotony problem
    the daily card had. Those readings are built almost entirely from slow material
    — the dasha, the progressed lagna, a couple of ingresses — so consecutive
    windows read alike. A dated list of *this* person's good and bad days is
    specific, actionable, and different every window.
    """
    if not janma_nak:
        return None
    from datetime import datetime, timedelta
    try:
        y, m, d = map(int, start_str.split("-"))
    except (TypeError, ValueError, AttributeError):
        return None
    # The nakshatra running at noon is a sky fact; the place only fixes which
    # noon. Any of the caller's own coordinates give the same star for the day.
    place_obj = drik.Place(place or "", lat or 13.0827, lon or 80.2707,
                           tz if tz is not None else 5.5)
    start = datetime(y, m, d)
    days, best, worst = [], [], []
    for offset in range(max(1, min(int(span_days or 0) + 1, max_days))):
        day = start + timedelta(days=offset)
        date_str = f"{day.year:04d}-{day.month:02d}-{day.day:02d}"
        try:
            jd = swe.julday(day.year, day.month, day.day, 12)
            day_nak = drik.nakshatra(jd, place_obj)[0]
        except Exception:
            continue
        name, tone = _tarabala(janma_nak, day_nak)
        days.append({"date": date_str, "nakshatra": NAKSHATRA_NAMES[day_nak - 1],
                     "tarabala": name, "tone": tone})
        if from_date and date_str < from_date:
            continue  # already past — still charted, just not recommended
        if tone == "very_good":
            best.append(date_str)
        elif tone == "bad":
            worst.append(date_str)
    if not days:
        return None
    return {"days": days, "best": best, "worst": worst}


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

            # The chakra's read of today against this chart's sensitive points.
            # Cheap (~2ms) and, unlike the slow gochara layer, it moves daily.
            try:
                sbc = AstrologyCompute.get_sarvatobhadra_chakra(
                    dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz,
                    current_date=date_str, current_time=current_time,
                    current_tz=current_tz, ayanamsa=ayanamsa)
                if sbc.get("status") != "success":
                    sbc = None
            except Exception as e:
                print(f"Daily digest sarvatobhadra skipped: {e}")
                sbc = None

            highlights = []
            cautions = []
            supports = []
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
                    # _ordinal, not f"{n}th": Sade-Sati's houses are 12, 1 and 2,
                    # so this line has been reading "1th"/"2th" for two of its
                    # three phases. Same for Jupiter below, which takes any house.
                    highlights.append(f"Saturn is in your {_ordinal(sat_house)} from "
                                      f"the Moon — Sade-Sati {phase} phase"
                                      + _bindu_note(sat))
                elif sat_house in _SANI_FROM_MOON:
                    # The two hard Saturn transits outside Sade-Sati. Named, because
                    # a reader who knows the term deserves to see it, and explained,
                    # because one who doesn't deserves to know what it means.
                    label, meaning = _SANI_FROM_MOON[sat_house]
                    highlights.append(f"{label}: Saturn in your {_ordinal(sat_house)} "
                                      f"from the Moon" + _bindu_note(sat))
                    cautions.append(_caution(f"{label} — {meaning}", "standing"))
                    # Named here, so don't repeat it as a bare gochara verdict below.
                    named_planets.add("Saturn")
                if jup:
                    highlights.append(
                        f"Jupiter transits your {_ordinal(jup.get('house_from_moon'))} "
                        f"from the Moon ({jup.get('sign_name')}){_bindu_note(jup)}")
                # ── The arudha frame (§60) ──────────────────────────────────
                # A slow mover crossing the Arudha Lagna or the Upapada is read
                # for the *visible* face of a matter — standing, reputation, the
                # marriage — where the Moon-referenced verdict above speaks to
                # how it is lived. Reported only for the houses the tradition
                # actually reads (5 of 12 from AL, 3 of 12 from UL): silence the
                # rest of the time is the point, or the daily note gains a line
                # of Jaimini vocabulary every single morning.
                for pname, p in (("Saturn", sat), ("Jupiter", jup)):
                    if not p:
                        continue
                    for short, label, table in (
                            ("al", "Arudha Lagna", AL_HOUSE_SIGNIFICATIONS),
                            ("ul", "Upapada", UL_HOUSE_SIGNIFICATIONS)):
                        h = p.get(f"house_from_{short}")
                        if h not in table:
                            continue
                        where = (f"is on your {label}" if h == 1
                                 else f"transits your {_ordinal(h)} from the {label}")
                        highlights.append(f"{pname} {where} — {table[h]}")
                        # One arudha line per graha, AL before UL — the same
                        # single-line budget the Moon-referenced lines above take.
                        break

                retro = [name for name, p in planets.items() if p.get("retrograde")]
                if retro:
                    highlights.append("Retrograde now: " + ", ".join(retro))
                transit_block = {
                    "planets": planets,
                    "upcoming": transits.get("upcoming", []),
                    "natal": transits.get("natal", {}),
                    "arudhas": transits.get("arudhas"),
                    "retrograde": retro,
                    "sade_sati": sat.get("house_from_moon") in (12, 1, 2),
                }
                for u in transits.get("upcoming", []):
                    verb = "re-enters" if u.get("retrograde_reentry") else "enters"
                    highlights.append(
                        f"{u['planet']} {verb} {u['to_sign']} on {u['date']}")

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

            # ── Tara Bala / Chandra Bala: today, for this chart ───────────────
            # Both read off numbers already computed above — the day's nakshatra
            # from the panchanga, the janma star and the Moon's house from the
            # transit block — so they cost nothing beyond the lookup.
            tarabala = None
            janma_nak = ((transit_block or {}).get("natal", {})
                         .get("moon", {}).get("nakshatra_index"))
            day_nak = ((panch.get("nakshatra") or {}).get("index")
                       if panch.get("status") == "success" else None)
            entry, tone = _tarabala_entry(janma_nak, day_nak)
            if entry:
                name = entry["text"].split(":", 1)[1].split("—")[0].strip()
                tarabala = {"name": name, "tone": tone,
                            "day_nakshatra": (panch.get("nakshatra") or {}).get("name"),
                            "janma_nakshatra": (transit_block or {}).get("natal", {})
                            .get("moon", {}).get("nakshatra")}
                (supports if tone in ("very_good", "good") else cautions).append(entry)

            chandrabala = None
            if transit_block:
                moon_house = (transit_block.get("planets", {})
                              .get("Moon", {}).get("house_from_moon"))
                entry, tone = _chandrabala_entry(moon_house)
                chandrabala = {"house_from_moon": moon_house, "tone": tone}
                if entry:
                    (supports if tone == "good" else cautions).append(entry)

            sbc_supports, sbc_cautions = _sbc_entries(sbc)
            supports.extend(sbc_supports)
            cautions.extend(sbc_cautions)

            # The day's one clearly good hour belongs with the other supports, not
            # only buried in the highlights list.
            if action_window:
                supports.append(_caution(
                    f"Favourable window: {action_window['name']} "
                    f"{action_window['start']}–{action_window['end']}", "today"))

            cautions.extend(_gochara_cautions(gochara, skip_planets=named_planets))
            for row in (gochara or {}).get("results", []):
                # The favourable half of the same classical verdict. Slow grahas are
                # backdrop here exactly as they are on the caution side.
                if row.get("tone") == "good" and row.get("planet") in _GOCHARA_CAUTION_PLANETS:
                    _, scope = _GOCHARA_CAUTION_PLANETS[row["planet"]]
                    supports.append(_caution(
                        f"{row['planet']} transits the "
                        f"{_ordinal(row.get('house_from_moon'))} from your natal Moon "
                        f"— gochara: Favourable", scope))

            cautions = _pick_cautions(cautions)
            supports = _pick_supports(supports)

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
                "tarabala": tarabala,
                "chandrabala": chandrabala,
                "sarvatobhadra": sbc,
                "highlights": highlights,
                # Kept apart from `highlights` deliberately: a hard transit listed
                # among neutral facts reads as another neutral fact — and a day that
                # is genuinely well-starred deserves somewhere concrete to say so.
                "cautions": cautions,
                "supports": supports,
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
            supports: List[Dict] = []
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
            for row in (gochara or {}).get("results", []):
                if row.get("tone") == "good" and row.get("planet") in _GOCHARA_CAUTION_PLANETS:
                    _, scope = _GOCHARA_CAUTION_PLANETS[row["planet"]]
                    supports.append(_caution(
                        f"{row['planet']} transits the "
                        f"{_ordinal(row.get('house_from_moon'))} from your natal Moon "
                        f"— gochara: Favourable", scope))

            # Which days in this window are well-starred for this chart. The one
            # genuinely day-by-day thing a fortnight or month reading can offer.
            janma_nak = ((transit_block or {}).get("natal", {})
                         .get("moon", {}).get("nakshatra_index"))
            tarabala = _tarabala_window(janma_nak, place, lat, lon, tz_offset,
                                        start_str, span_days, from_date=today_str)
            if tarabala:
                # Into supports/cautions rather than highlights: these are advice,
                # not facts about the sky, and they are the one thing in a month
                # reading that is genuinely different for this person on these days.
                # Inserted at the front, not appended: over a fortnight or a month
                # a dated list of *this* person's good and bad days outranks any
                # single transit verdict, and the rationing keeps only the first few.
                if tarabala["best"]:
                    supports.insert(0, _caution(
                        "Well-starred days ahead (Tara Bala): "
                        + ", ".join(_fmt_day(d) for d in tarabala["best"][:6]), "today"))
                if tarabala["worst"]:
                    cautions.insert(0, _caution(
                        "Days to keep light (Tara Bala): "
                        + ", ".join(_fmt_day(d) for d in tarabala["worst"][:6]), "today"))

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
                "tarabala": tarabala,
                "highlights": highlights,
                "cautions": _pick_cautions(cautions),
                "supports": _pick_supports(supports),
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
