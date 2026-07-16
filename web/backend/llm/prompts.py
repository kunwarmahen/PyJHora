"""Prompt builders and context rendering — every `_build_*_prompt`, the chart-context block, and the small formatting helpers.

Part of the §4c llm_service split — methods moved verbatim from the
single LLMService class. These are instance methods, so the mixin
composes over `self` with no other changes.
"""
from .base import *  # noqa: F401,F403


class PromptsMixin:

    def _build_quiz_gen_prompt(self, chart_data: Dict[str, Any], topics: List[str],
                               level: str, num_mcq: int, num_free: int,
                               focus_note: str) -> str:
        topic_lines = "\n".join(
            f"- {t}: {self.QUIZ_TOPICS[t]}" for t in topics if t in self.QUIZ_TOPICS
        ) or f"- planets: {self.QUIZ_TOPICS['planets']}"
        level_guide = {
            "beginner": "Beginner: test recall of single placements and their plain meaning "
                        "(which sign/house a planet is in, what a house signifies).",
            "intermediate": "Intermediate: combine two factors (lord placement + aspect, "
                            "dignity of a house lord, what a present yoga implies).",
            "advanced": "Advanced: synthesize multiple factors (dasha + transit timing, "
                        "varga corroboration, strength/ashtakavarga weighed together).",
        }.get(level, "Beginner")
        return (
            self._render_context_block(chart_data)
            + "\n\n=== YOUR TASK: WRITE A QUIZ ABOUT THIS CHART ===\n"
            + f"Create exactly {num_mcq} multiple-choice and {num_free} free-text "
              "(open-ended) questions that teach the student to read THIS chart.\n\n"
            + "Difficulty: " + level_guide + "\n\n"
            + "Cover these topics (spread the questions across them):\n" + topic_lines + "\n"
            + (f"\nFocus emphasis: {focus_note}\n" if focus_note else "")
            + "\nRULES:\n"
            + "1. Every question MUST reference the real placements above (e.g. 'Your Moon "
              "is in Scorpio in the 4th house — what does that suggest about ...'). Never "
              "ask about factors not present in the chart data.\n"
            + "2. Multiple-choice: exactly 4 plausible options, ONE correct; put its index "
              "(0-3) in correct_index. Make distractors believable, not silly.\n"
            + "3. Free-text: list 2-4 'expected_points' — the key ideas a correct answer "
              "should contain — used later for grading.\n"
            + "4. 'rationale' explains the correct answer citing the specific chart factors.\n"
            + "5. Keep questions clear and answerable from the chart; avoid trick wording.\n\n"
            + "Reply with ONLY this JSON (no prose, no code fences):\n"
            + '{"questions": [\n'
            + '  {"topic": "planets", "difficulty": "beginner", "format": "mcq", '
              '"question": "...", "options": ["...","...","...","..."], '
              '"correct_index": 0, "rationale": "..."},\n'
            + '  {"topic": "dashas", "difficulty": "beginner", "format": "free", '
              '"question": "...", "expected_points": ["...","..."], "rationale": "..."}\n'
            + "]}"
        )

    def _build_quiz_grade_prompt(self, chart_data: Dict[str, Any],
                                 free_items: List[Dict[str, Any]],
                                 answers: Dict[str, str]) -> str:
        blocks = []
        for it in free_items:
            pts = "; ".join(it.get("expected_points", [])) or "(none provided)"
            ans = (answers.get(it["id"]) or "").strip() or "(no answer given)"
            blocks.append(
                f"--- Question {it['id']} (topic: {it.get('topic')}) ---\n"
                f"Question: {it.get('question')}\n"
                f"Expected key points: {pts}\n"
                f"Reference rationale: {it.get('rationale') or '(none)'}\n"
                f"STUDENT'S ANSWER: {ans}"
            )
        questions_block = "\n\n".join(blocks)
        return (
            self._render_context_block(chart_data)
            + "\n\n=== YOUR TASK: GRADE THESE FREE-TEXT ANSWERS ===\n"
            + "Grade each student answer against the expected key points AND the real "
              "chart facts above. Award partial credit. Be encouraging but honest.\n\n"
            + questions_block
            + "\n\nFor each question return: a score from 0.0 to 1.0; a verdict of "
              "'correct' (>=0.8), 'partial' (0.34-0.79) or 'incorrect' (<0.34); a short "
              "'what_was_right'; a short 'what_was_wrong' (empty string if fully correct); "
              "and 'reasoning' — a detailed explanation of the right answer citing the "
              "specific chart factors, so the student learns WHY.\n\n"
            + "Reply with ONLY this JSON (no prose, no code fences):\n"
            + '{"grades": [\n'
            + '  {"id": "q3", "score": 0.5, "verdict": "partial", "what_was_right": "...", '
              '"what_was_wrong": "...", "reasoning": "..."}\n'
            + "]}"
        )

    # ── Composed long-form "Life Report" (§5.11) ───────────────────────────
    # Ordered chapters; each is generated as its own focused prompt sharing the
    # full chart context, then stitched into one document (print-ready + saved).
    LIFE_REPORT_CHAPTERS = [
        ("personality", "Personality & Self",
         "the Lagna (1st house) and its lord, the Moon (mind/emotions) and the Sun "
         "(soul/ego) by sign, house and nakshatra; the overall temperament, natural "
         "strengths and inner conflicts."),
        ("career", "Career & Vocation",
         "the 10th house, its lord and occupants, the D10 (Dasamsa) if present, the "
         "Sun/Saturn/Mercury condition, and Amatyakaraka themes; likely fields, work "
         "style and the arc of professional life."),
        ("wealth", "Wealth & Resources",
         "the 2nd (accumulated wealth) and 11th (gains) houses and their lords, the "
         "role of Jupiter and Venus, and any Dhana yogas; earning capacity, savings "
         "habits and financial ups and downs — no specific figures or guarantees."),
        ("relationships", "Relationships & Marriage",
         "the 7th house and its lord, Venus (and Jupiter for a woman's chart), the D9 "
         "(Navamsa) and the Upapada (UL); partnership temperament, what one seeks in a "
         "partner and the general relationship arc."),
        ("health", "Health & Vitality",
         "the 6th (illness/resilience) and 8th (chronic/longevity) houses and their "
         "lords, the Lagna lord's strength and any afflictions; constitutional "
         "tendencies and lifestyle themes — framed as wellbeing, never diagnosis."),
        ("dharma", "Dharma & Purpose",
         "the 9th house (fortune/dharma) and its lord, Jupiter, the Atmakaraka and "
         "Karakamsa; guiding values, spiritual leanings and life direction."),
        ("outlook", "Current Period & Outlook",
         "the running Vimsottari maha/bhukti, the active Saturn transit (Sade Sati/"
         "Ashtama/Kantaka if any) and the major upcoming ingresses; the tone of the "
         "next few years and where to focus."),
    ]

    def _build_life_report_chapter_prompt(self, chart_data: Dict[str, Any],
                                          title: str, focus: str, name: str) -> str:
        return (
            self._render_context_block(chart_data)
            + f"\n\nYou are composing one chapter of a long-form Vedic astrology life "
            f"report for {name}. This chapter is **{title}**.\n\n"
            f"Focus on: {focus}\n\n"
            "Write a flowing, personalised ~320-word chapter in warm but precise "
            "language. Cite the specific placements/lords/yogas/dashas behind each "
            "point (this is a THIS-chart reading, not generic horoscope text). Do NOT "
            "repeat the chart data as a list; weave it into prose. Start directly with "
            "the reading — no chapter heading (it's added by the layout). No medical, "
            "legal, lifespan or specific-financial predictions; frame sensitive areas "
            "constructively."
        )

    def _build_chart_analysis_prompt(self, chart_data: Dict[str, Any], question: str) -> str:
        """Single-shot prompt: chart context block followed by the user's question."""
        return (
            self._render_context_block(chart_data)
            + f"\n\nUser's Question: {question}\n\n"
            + "Provide a detailed, personalized answer based on this specific birth chart."
        )

    def _build_prediction_prompt(self, chart_data: Dict[str, Any], prediction_type: str) -> str:
        """Build prompt for predictions, using the full structured chart context
        (D1 + dasha chain + yogas + doshas + transits + vargas) when available."""

        type_specific = {
            "general": "overall life path, personality, and general predictions",
            "health": "health constitution, potential health issues, and wellness recommendations",
            "career": "career inclinations, professional success factors, and recommended fields",
            "relationships": "relationship patterns, marriage timing, and compatibility factors"
        }
        focus = type_specific.get(prediction_type, type_specific["general"])

        return (
            self._render_context_block(chart_data)
            + f"\n\nBased on THIS SPECIFIC BIRTH CHART above, provide detailed "
            + f"{prediction_type} predictions focusing on {focus}.\n\n"
            + "Your prediction should cover:\n"
            + "1. Key strengths and characteristics from their specific placements (cite the houses/lords/karakas).\n"
            + "2. Challenges and areas for growth indicated by their chart.\n"
            + "3. Opportunities in the near future based on the running dasha and current transits.\n"
            + "4. Practical remedies or recommendations specific to their placements.\n"
            + "5. Auspicious timing considerations grounded in the dasha chain.\n\n"
            + "Be specific, insightful, personalized, and encouraging. Do NOT ask for "
            + "more information — you have the complete chart and today's date."
        )

    def _build_compatibility_prompt(self, male_chart: Dict[str, Any],
                                   female_chart: Dict[str, Any], koota_score: int,
                                   marriage: Optional[Dict[str, Any]] = None) -> str:
        """Build prompt for compatibility analysis"""

        male_lagna = male_chart.get("lagna", {})
        male_moon = male_chart.get("moon_sign", {})
        male_sun = male_chart.get("sun_sign", {})
        female_lagna = female_chart.get("lagna", {})
        female_moon = female_chart.get("moon_sign", {})
        female_sun = female_chart.get("sun_sign", {})

        prompt = f"""You are an expert Vedic astrologer specializing in marriage compatibility. Below are the COMPLETE, ACCURATELY CALCULATED birth charts for both partners from {SITE_NAME} software.

=== MALE BIRTH CHART ===
Lagna (Ascendant): {male_lagna.get('sign_name', 'Unknown')} in {male_lagna.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {male_moon.get('sign_name', 'Unknown')} in {male_moon.get('nakshatra', 'Unknown')} nakshatra (Pada {male_moon.get('pada', 'Unknown')})
Sun Sign: {male_sun.get('sign_name', 'Unknown')}

=== FEMALE BIRTH CHART ===
Lagna (Ascendant): {female_lagna.get('sign_name', 'Unknown')} in {female_lagna.get('nakshatra', 'Unknown')} nakshatra
Moon Sign: {female_moon.get('sign_name', 'Unknown')} in {female_moon.get('nakshatra', 'Unknown')} nakshatra (Pada {female_moon.get('pada', 'Unknown')})
Sun Sign: {female_sun.get('sign_name', 'Unknown')}

=== COMPATIBILITY SCORE ===
Ashta Koota Score: {koota_score}/36 (Calculated using traditional Vedic methods)
{self._format_marriage_block(marriage)}
Interpretation:
- 28-36: Excellent compatibility
- 24-27: Good compatibility
- 18-23: Average compatibility (workable with effort)
- Below 18: Challenging compatibility

Based on these SPECIFIC CHARTS and the {koota_score}/36 Ashta Koota score, provide a comprehensive compatibility analysis:

1. Overall compatibility assessment - interpret the {koota_score}/36 score in context
2. Strengths in the relationship based on their specific placements
3. Potential challenges indicated by their charts and how to overcome them
4. Mental and emotional compatibility (Moon signs and nakshatras)
5. Long-term relationship prospects
6. Practical recommendations for a harmonious marriage

IMPORTANT: Use the actual chart data provided above. Be balanced, specific to their placements, insightful, and constructive. Do not ask for more information."""

        return prompt

    def _build_comparison_prompt(self, chart_a: Dict[str, Any], chart_b: Dict[str, Any],
                                 name_a: str, name_b: str) -> str:
        """Build a neutral, relationship-agnostic two-chart comparison prompt.

        Unlike compatibility (which assumes marriage/Guna Milan), this contrasts the
        two charts as individuals — useful for any pairing (friends, family, the same
        person across a rectification, etc.)."""

        def block(name: str, chart: Dict[str, Any]) -> str:
            lagna = chart.get("lagna", {})
            moon = chart.get("moon_sign", {})
            sun = chart.get("sun_sign", {})
            return (
                f"=== {name} ===\n"
                f"Lagna (Ascendant): {lagna.get('sign_name', 'Unknown')} in "
                f"{lagna.get('nakshatra', 'Unknown')} nakshatra\n"
                f"Moon: {moon.get('sign_name', 'Unknown')} in {moon.get('nakshatra', 'Unknown')} "
                f"nakshatra (Pada {moon.get('nakshatra_pada', 'Unknown')})\n"
                f"Sun: {sun.get('sign_name', 'Unknown')}\n"
                f"Planets:\n{self._format_planets(chart.get('planetary_positions', {}))}"
            )

        prompt = f"""You are an expert Vedic astrologer. Below are two COMPLETE, ACCURATELY CALCULATED birth charts from {SITE_NAME} software. Compare and contrast them as two individuals. This is NOT a marriage/compatibility (Guna Milan) reading — make no assumptions about the nature of any relationship between them.

{block(name_a, chart_a)}

{block(name_b, chart_b)}

Provide a clear side-by-side comparison covering:

1. Personality & temperament — contrast their Lagna and overall disposition
2. Mind & emotions — contrast their Moon signs/nakshatras
3. Vitality, ego & self-expression — contrast their Sun
4. Notable similarities (shared signs, nakshatras, or planetary patterns)
5. Notable differences and how their natures diverge
6. A short, neutral synthesis of how the two charts compare

IMPORTANT: Use the actual chart data above. Be specific to their placements, balanced, and concise. Refer to them as "{name_a}" and "{name_b}". Do not score them and do not ask for more information."""

        return prompt

    def _build_kaala_chakra_prompt(self, kaala: Dict[str, Any], name: str) -> str:
        """Plain-language Kaala Chakra (wheel of directions) reading prompt.

        The wheel is already computed — which grahas colour which compass
        direction — so the model turns that into practical direction guidance
        (travel, where to face, which way to push a matter)."""
        base = kaala.get("base_star", {})
        dir_lines = []
        for d in kaala.get("directions", []):
            occ = []
            for c in d.get("cells", []):
                for p in c.get("planets", []):
                    occ.append(f"{p['name']}{' (malefic)' if p.get('malefic') else ' (benefic)'}"
                               f" on {c['star']}")
            dir_lines.append(
                f"- {d.get('direction')} [{d.get('tone')}] — "
                f"{', '.join(occ) if occ else 'no grahas here'}")

        inner = []
        for c in kaala.get("inner", []):
            for p in c.get("planets", []):
                inner.append(f"{p['name']} on {c['star']}")

        return f"""You are an expert Vedic astrologer explaining the **Kaala Chakra** (the wheel of directions) to {name}, who is not an astrologer. Everything below is ALREADY COMPUTED by {SITE_NAME} — trust it and interpret it; do not recompute.

HOW IT WORKS: the 28 nakshatras are arranged as a wheel counted from a base star (here the Sun's star). Four stars sit at the hub, and the other 24 form eight spokes — and **each spoke IS a compass direction**. A graha landing on a spoke colours that direction: benefics make it supportive, malefics make it rough. The classical use is practical — which way to travel, face, or push a matter.

=== THIS PERSON'S WHEEL ({kaala.get('transit_date')}) ===
Base star (from the Sun): {base.get('name')}
At the hub: {', '.join(inner) if inner else 'nothing'}

=== THE EIGHT DIRECTIONS ===
{chr(10).join(dir_lines)}

Favourable now: {', '.join(kaala.get('favourable') or []) or 'none stand out'}
Best avoided now: {', '.join(kaala.get('avoid') or []) or 'none'}

Write ~200 words of plain English:
1. Which directions are supportive right now and which are better avoided, and WHY (name the graha responsible).
2. What that means practically — travel, a journey, where to sit/face for important work, which way to push a matter.
3. Note any direction that is mixed (both benefic and malefic) as "workable but not clean".
4. If a direction has no grahas, say plainly that it is neutral — that is useful information, not a gap.

RULES: The DIRECTIONS block above is authoritative — never contradict it. Be practical and calm; this is a timing/direction aid, not a warning. No jargon without a one-line gloss. End with: "Direction guidance is a traditional aid — weigh it alongside practical judgement."
"""

    def _build_kota_chakra_prompt(self, kota: Dict[str, Any], name: str) -> str:
        """Plain-language Kota Chakra (the fort) reading prompt.

        The fort logic is already computed (which grahas have reached which
        enclosure, whether they are malefic, and where the two defenders stand);
        the model translates that into protection/health guidance a non-astrologer
        can act on. Deliberately no fear-mongering: Kota questions are usually
        asked when someone is anxious."""
        star = kota.get("birth_star", {})
        ring_lines = []
        for ring in kota.get("rings", []):
            occupants = []
            for c in ring.get("cells", []):
                for p in c.get("transit", []):
                    occupants.append(
                        f"{p['name']}"
                        f"{' (malefic)' if p.get('malefic') else ' (benefic)'}"
                        f" on {c['star']}")
            ring_lines.append(
                f"- {ring.get('name')} — {ring.get('description')}\n"
                f"  Grahas here now: {', '.join(occupants) if occupants else 'none'}")

        finding_lines = [f"- ({f.get('tone')}) {f.get('text')}"
                         for f in kota.get("findings", [])]

        return f"""You are an expert Vedic astrologer explaining the **Kota Chakra** (the fort) to {name}, who is not an astrologer. All the chakra logic below is ALREADY COMPUTED by {SITE_NAME} — trust it and interpret it; do not recompute or ask for more data.

HOW THE FORT WORKS: the 28 nakshatras are laid out as four concentric enclosures counted from the person's birth star. Read it outward-in — Baahya (outer wall) is the approach, Praakaara the rampart, Durgantara the inner fort, and Sthamba the central pillar (the most sensitive point). A MALEFIC graha transiting into the inner enclosures presses on the fort; a BENEFIC there defends it. The Kota Swami is the fort's defender and the Kota Paala its guard.

=== THIS PERSON'S FORT ({kota.get('transit_date')}) ===
Birth star: {star.get('name')} (pada {star.get('pada')}), Moon in {kota.get('moon_sign')}
Kota Swami (defender): {kota.get('kota_lord')}
Kota Paala (guard): {kota.get('kota_paala')}

=== THE FOUR ENCLOSURES, OUTER TO INNER ===
{chr(10).join(ring_lines)}

=== COMPUTED FINDINGS ===
{chr(10).join(finding_lines) if finding_lines else '- nothing notable'}

Write ~250 words of plain English:
1. What the fort looks like right now — is the pressure at the walls or has it reached the inner rings?
2. What the malefics that HAVE reached the inner enclosures suggest to stay watchful about (health, energy, security, peace of mind) — describe tendencies, never diagnose.
3. Where the protection is: benefics in the fort, and where the Swami and Paala stand.
4. One or two practical, grounded suggestions.

RULES: The ENCLOSURES and COMPUTED FINDINGS above are authoritative — never contradict them. If a graha is listed in an enclosure, it IS there; do not say it has not reached one. Be calm, balanced and constructive — this chakra is usually consulted when someone is worried, so do NOT alarm. No predictions of death, disease or disaster. No jargon without a one-line gloss. End with: "This is a traditional chakra reading, not medical or professional advice."
"""

    def _build_tripataki_prompt(self, trip: Dict[str, Any], name: str) -> str:
        """Plain-language Tripataki Chakra (vedha) reading prompt.

        The vedha is already computed from the Tajaka rules (movable<->dual except
        the 3rd, fixed<->fixed, dual<->movable except the 11th), read on the Moon
        and the Lagna. The model only interprets."""
        vedha_lines = []
        for v in trip.get("vedha", []):
            hits = v.get("obstructed_by", [])
            if hits:
                who = ", ".join(
                    f"{h['planet']} from {h['from_sign']}"
                    f" ({'benefic' if h.get('benefic') else 'malefic'})" for h in hits)
            else:
                who = "nothing — this point is unobstructed"
            vedha_lines.append(
                f"- {v.get('target')} in {v.get('sign')} (a {v.get('sign_class')} sign; "
                f"can be obstructed only from {', '.join(v.get('vedha_signs', []))})\n"
                f"  Obstructed by: {who}  [tone: {v.get('tone')}]")

        return f"""You are an expert Vedic astrologer explaining the **Tripataki Chakra** to {name}, who is not an astrologer. All the vedha below is ALREADY COMPUTED by {SITE_NAME} from the classical Tajaka rules — trust it and interpret it; do not recompute.

HOW IT WORKS: the twelve rasis sit around the three "pataki" (banner) lines. The chakra is read through **vedha** — mutual obstruction between signs: a movable sign is obstructed from the dual signs (except the dual in the 3rd from it), a fixed sign from the other fixed signs, and a dual sign from the movable signs (except the movable in the 11th from it). Customarily the vedha is judged on the **Moon** (the mind and day-to-day flow) and the **Lagna** (the self and body).

=== THIS PERSON'S CHAKRA ({trip.get('transit_date')}) ===
Natal Lagna: {trip.get('natal_lagna')} · Transiting Moon: {trip.get('transit_moon')}

=== VEDHA ===
{chr(10).join(vedha_lines) if vedha_lines else '- none computed'}

Write ~200 words of plain English:
1. What obstruction on the Moon means for them right now (mood, mental flow, the feel of things) — and note whether the obstructing grahas are benefic or malefic, since a benefic vedha inconveniences rather than harms.
2. What obstruction on the Lagna means (self, body, how plans land).
3. Anything unobstructed — say so plainly, it is good news worth naming.
4. One practical takeaway.

RULES: The VEDHA block above is authoritative — never contradict it; if a graha is listed as obstructing, it IS. Be balanced and constructive, never fatalistic. Gloss any Sanskrit term in a few words. Be honest that this is a broad, one-moment overview — the chakra gives the *nature* of what dominates, not specific events. End with: "Tripataki is classically a Varshaphal (annual) tool; this reads its vedha rules for the moment you selected."
"""

    def _build_sarvatobhadra_prompt(self, sbc: Dict[str, Any], name: str) -> str:
        """Build a plain-language Sarvatobhadra Chakra (transit) reading prompt.

        The chakra logic is already computed (occupation + facing/saamne vedha on
        the native's sensitive points); the model's job is to translate the
        structured findings into something a non-astrologer can act on."""
        anchors = sbc.get("anchors", {})
        anchor_lines = []
        for a in anchors.values():
            anchor_lines.append(f"- {a.get('label')}: {a.get('name')}")

        findings = sbc.get("findings", [])
        if findings:
            find_lines = []
            for f in findings:
                kind = ("a graha sitting ON it" if f.get("kind") == "occupation"
                        else "vedha (obstruction) facing it across the chakra")
                find_lines.append(
                    f"- {f.get('planet')} ({f.get('planet_nature')}, {f.get('tone')}) — "
                    f"{kind} → {f.get('anchor_label')} ({f.get('anchor_name')})"
                )
            findings_block = "\n".join(find_lines)
        else:
            findings_block = "- No graha is currently occupying or casting vedha on the native's sensitive points (a quiet, neutral window on the chakra)."

        pan = sbc.get("transit_panchanga", {})
        pan_line = (
            f"Today's tithi group: {pan.get('tithi_group')} "
            f"({'matches' if pan.get('same_tithi_group') else 'differs from'} the birth tithi group); "
            f"today's weekday: {pan.get('weekday')} "
            f"({'matches' if pan.get('same_weekday') else 'differs from'} the birth weekday)."
        )

        planets = sbc.get("planets", [])
        planet_line = ", ".join(
            f"{p.get('name')} in {p.get('nakshatra')}/{p.get('sign_name')}"
            f"{' (retrograde)' if p.get('retrograde') else ''}"
            for p in planets
        )

        return f"""You are a warm, plain-spoken Vedic astrologer explaining a Sarvatobhadra Chakra reading to someone with NO astrology background. Avoid jargon; when you must use a term (vedha, nakshatra), explain it in a few words.

The Sarvatobhadra Chakra is a 9×9 grid of all the stars, signs, syllables, tithis and weekdays. We map where the planets are TODAY onto it and check the person's most sensitive cells: their birth star, Moon sign, name star, birth tithi and birth weekday. A planet "occupying" a sensitive cell, or a planet "facing" it from across the grid (called vedha, meaning obstruction), activates that part of life — gently if the planet is a natural benefic (Jupiter, Venus, Mercury, Moon), more testingly if it is a malefic (Saturn, Mars, Rahu, Ketu, Sun).

Reading for: {name}
Transit date: {sbc.get('transit_date')} {sbc.get('transit_time')}

The person's sensitive points on the chakra:
{chr(10).join(anchor_lines)}

Where the planets sit today: {planet_line}

{pan_line}

What the chakra flags right now (already computed — trust these):
{findings_block}

Write a clear, encouraging reading (about 500 words) with these parts:
1. **The headline** — one or two sentences on the overall tone of this period for {name} (supportive, mixed, or a time for care).
2. **What's being touched** — for each flagged planet above, say in everyday language what it tends to stir up and which life area (e.g. Saturn → patience, work, delays; Jupiter → growth, opportunity, optimism), tied to which sensitive point it hits.
3. **What to expect & do** — 2-4 concrete, gentle suggestions for the weeks ahead.
4. End with one short line of reassurance.

Be specific to the findings above — do not invent placements that aren't listed. If nothing is flagged, say plainly that this is a calm, unremarkable window and give light general guidance. Do NOT predict death, disease, disasters, or precise dates. Close with a brief reminder that this is for reflection, not a substitute for professional advice."""

    def _build_varshaphal_prompt(self, v: Dict[str, Any], name: str) -> str:
        """Build a plain-language year-ahead (Varshaphal / Tajaka) forecast prompt.

        The annual chart, Muntha, year-lord, Sahams, Tajaka yogas and annual
        dasha are already computed; the model's job is to weave them into a
        grounded, encouraging forecast for the year."""
        year = v.get("year")
        entry = v.get("year_entry", {})
        muntha = v.get("muntha", {})
        yl = v.get("year_lord") or {}

        lagna = v.get("lagna", {})
        planets = v.get("planets", {})
        placements = ", ".join(
            f"{p}: {d.get('sign_name')}" for p, d in planets.items()
        )

        sahams = v.get("sahams", [])
        saham_lines = "\n".join(
            f"- {s.get('name')} ({s.get('significance')}): {s.get('sign_name')} "
            f"(house {s.get('house')})"
            for s in sahams
        ) or "- (none computed)"

        yogas = v.get("tajaka_yogas", [])
        if yogas:
            yoga_lines = "\n".join(
                f"- {y.get('name')}"
                + (f" [{'/'.join(y.get('pair'))}]" if y.get("pair") else "")
                + f": {y.get('description')}"
                for y in yogas
            )
        else:
            yoga_lines = "- No notable Tajaka yoga this year (a steady, unremarkable year on this measure)."

        periods = v.get("annual_dasha", {}).get("periods", [])
        dasha_lines = "\n".join(
            f"- {p.get('lord_name')}: {p.get('start')} → {p.get('end')}"
            + (" (running now)" if p.get("current") else "")
            for p in periods
        ) or "- (none computed)"

        return f"""You are a warm, plain-spoken Vedic astrologer giving a YEAR-AHEAD reading (Varshaphal, the annual solar-return chart in the Tajaka system) to someone with little astrology background. Avoid jargon; when you must use a term (Muntha, Saham, dasha), explain it in a few words.

The Varshaphal is a fresh chart cast for the moment the Sun returns to its birth position each year. It is read for that one year only, alongside the natal chart. Key annual factors are already computed for you — trust them, do not invent placements.

Reading for: {name}
Year: {year} (solar-year begins {entry.get('date')} {entry.get('time')})
Annual Ascendant (Lagna): {lagna.get('sign_name')}
Planet placements this year: {placements}
Muntha (the progressed point that advances one sign a year; the year's spotlight): {muntha.get('sign_name')} — house {muntha.get('house')} of the annual chart
Year-lord (Varsheshwara, the planet governing the year): {yl.get('planet', 'undetermined')}

Sahams (sensitive points, like signposts for specific matters):
{saham_lines}

Tajaka yogas active this year (already computed — trust these):
{yoga_lines}

Annual dasha (Mudda / Varsha Vimsottari — sub-periods within the year, each ruled by a planet):
{dasha_lines}

Write a clear, encouraging year-ahead reading (about 500 words) with these parts:
1. **The headline** — one or two sentences on the overall tone and theme of {year} for {name}, anchored in the Muntha house and the year-lord.
2. **What the year emphasises** — translate the Muntha house, the year-lord's nature, and 2-3 of the most relevant Sahams into everyday life areas (work, money, relationships, health, learning, home).
3. **Timing within the year** — use the annual dasha sequence to note which stretches look more active or supportive, in plain terms.
4. **What to do** — 2-4 concrete, gentle suggestions for the year.
5. End with one short line of reassurance.

Be specific to the factors above — do not invent anything not listed. Do NOT predict death, disease, disasters, or precise dates. Close with a brief reminder that this is for reflection and planning, not a substitute for professional advice."""

    def _build_pancha_pakshi_prompt(self, p: Dict[str, Any], name: str) -> str:
        """Build a plain-language day-timing reading from the Pancha Pakshi data.

        The birth bird, the day's best/worst windows and the segment timeline are
        already computed; the model turns them into gentle 'good times for X'
        guidance for the day."""
        bird = p.get("birth_bird", {})
        best = p.get("best_times", [])
        avoid = p.get("avoid_times", [])

        best_lines = "\n".join(
            f"- {b.get('start')}–{b.get('end')} ({b.get('phase')}): "
            f"{b.get('main_activity')}/{b.get('sub_activity')} — {b.get('effect')}"
            for b in best
        ) or "- (none)"
        avoid_lines = "\n".join(
            f"- {a.get('start')}–{a.get('end')} ({a.get('phase')}): "
            f"{a.get('main_activity')}/{a.get('sub_activity')} — {a.get('effect')}"
            for a in avoid
        ) or "- (none)"

        return f"""You are a warm, plain-spoken guide explaining PANCHA PAKSHI SASTRA — an old South-Indian (Tamil Siddha) system of timing the day. In it, each person has a "birth bird" (from their birth star), and the day is divided into windows where that bird is Ruling, Eating, Walking, Sleeping or Dying — from strongest to weakest. You favour the strong windows for important actions and rest during the weak ones. Explain simply; avoid jargon.

Reading for: {name}
Date: {p.get('date')} ({p.get('weekday')}, {p.get('paksha')} paksha)
Birth bird: {bird.get('name')} (from birth star {bird.get('star_name')})
Sunrise {p.get('sunrise')}, sunset {p.get('sunset')}.

The strongest windows today (best for important or demanding activities):
{best_lines}

The weakest windows today (better for rest, routine, low-stakes tasks):
{avoid_lines}

Write a short, friendly day-guide (about 250-300 words):
1. **Your bird today** — one or two sentences on what having the {bird.get('name')} as the birth bird means in this system, kept light.
2. **Best times** — translate the strong windows into concrete "good for…" suggestions (starting important work, meetings, travel, exercise, decisions), with the clock times.
3. **Quieter times** — note the weak windows as good for rest, chores, reflection.
4. End with one short, encouraging line.

Use the clock times given. Do NOT invent windows not listed. Do NOT make medical, financial or fated claims. Close with a one-line reminder that this is a traditional timing aid for reflection, not a rule to live by."""

    def _build_sensitive_points_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Turn the computed Sphutas, Sahams and Argala into a gentle, plain
        explanation. All values are already computed — the model interprets."""
        sphuta = (d.get("sphuta") or {}).get("sphutas", [])
        sahams = (d.get("sahams") or {}).get("sahams", [])
        argala = (d.get("argala") or {}).get("houses", [])

        sph_lines = "\n".join(
            f"- {s['name']} ({s['significance']}): {s['sign_name']} {s['degrees']}°, "
            f"house {s['house']}" for s in sphuta[:12]
        ) or "- (none)"
        # Only the sahams likely to matter most, to keep the prompt lean.
        key = {"Punya", "Vidya", "Yasas", "Karma", "Artha", "Vivaha", "Puthra",
               "Roga", "Laabha", "Rajya", "Jeeva"}
        sah_lines = "\n".join(
            f"- {s['name']} ({s['significance']}): {s['sign_name']}, house {s['house']}"
            for s in sahams if s['name'] in key
        ) or "- (none)"
        arg_lines = "\n".join(
            f"- House {h['bhava']} ({h['sign_name']}): net {h['net']}"
            for h in argala if h.get('net') not in (None, 'none', 'balanced')
        )[:800] or "- (mostly balanced)"

        return f"""You are a warm, plain-spoken Vedic astrologer explaining a chart's SENSITIVE POINTS to {name}. These are technical helper points, so translate them into everyday meaning and never overwhelm with jargon.

SPHUTAS (sensitive longitudes derived from the chart):
{sph_lines}

Key SAHAMS (Arabic-part-like points for life themes):
{sah_lines}

ARGALA (which houses receive strong planetary "intervention" support vs obstruction):
{arg_lines}

Write a friendly ~300-word note:
1. **What these are** — one or two sentences: sensitive supporting points that fine-tune a reading, not core predictions.
2. **A few highlights** — pick 3-4 of the most telling points (e.g. a Saham for career/wealth/marriage sitting in a notable house, or a house with strong argala) and say plainly what they gently emphasise.
3. **How to use them** — note they colour and confirm the main chart rather than override it.
Keep it encouraging and non-deterministic. Do NOT dwell on Mrityu/Apamrithyu points or make any health, death, financial or fated claims. Close with a one-line reminder that these are supportive nuances for reflection."""

    def _build_celestial_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the current Vedic clock + retrograde snapshot in plain terms."""
        clock = d.get("clock") or {}
        retro = d.get("retrograde") or {}
        panch = clock.get("panchanga") or {}
        hora = clock.get("current_hora") or {}
        retro_now = retro.get("retrograde_now") or []
        stations = "\n".join(
            f"- {p['planet']} turns {p['next_station']['becomes']} on {p['next_station']['date']}"
            for p in retro.get("planets", []) if p.get("next_station")
        ) or "- (none upcoming in range)"

        return f"""You are a warm, plain-spoken guide explaining the CURRENT SKY in Vedic terms to {name}, tying the traditional day-clock to what the planets are doing right now. Keep it simple and grounded.

Date: {clock.get('date')} at {clock.get('place') or 'the chosen place'}
Sunrise {clock.get('sunrise')}, sunset {clock.get('sunset')} (day length {clock.get('day_length_hours')} h).
Running hora (planetary hour) lord: {hora.get('planet')} ({'benefic' if hora.get('benefic') else 'malefic'}).
Panchanga now: tithi {panch.get('tithi')}, nakshatra {panch.get('nakshatra')}, yoga {panch.get('yoga')}.
Planets retrograde right now: {', '.join(retro_now) if retro_now else 'none'}.
Upcoming direction changes (stations):
{stations}

Write a friendly ~250-word note:
1. **The Vedic day** — explain the ghati/hora idea in a sentence, then what the current hora lord tends to favour (e.g. Jupiter-hora good for learning, Mercury for communication), lightly.
2. **Retrograde now** — for any planet currently retrograde, explain in everyday terms what retrograde traditionally invites (review, revisit, slow down) — NOT doom.
3. **What's coming** — mention the next station date(s) as gentle "watch for a shift" notes.
End with one encouraging line. Do NOT make fated, medical or financial claims; frame retrogrades as invitations to reflect, not warnings."""

    def _build_almanac_prompt(self, d: Dict[str, Any]) -> str:
        """Turn the day's panchanga + planetary hours into a friendly day-guide."""
        p = d.get("panchanga") or {}
        hours = (d.get("hours") or {}).get("horas", [])
        tithi = p.get("tithi") or {}
        nak = p.get("nakshatra") or {}
        yoga = p.get("yoga") or {}
        karana = p.get("karana") or {}
        vaara = p.get("vaara") or {}
        hijri = p.get("hijri") or {}

        def _rng(x):
            return f"{x.get('start')}–{x.get('end')}" if x and x.get("start") else "—"

        # A couple of upcoming benefic day-horas as favourable windows.
        good = [h for h in hours if h.get("period") == "day" and h.get("benefic")]
        good_lines = "\n".join(
            f"- {h['planet']} hora {h['start']}–{h['end']}" for h in good[:4]
        ) or "- (none listed)"
        engine = "Surya-Siddhanta" if p.get("system") == "surya_siddhanta" else "Drik"

        return f"""You are a warm, plain-spoken almanac guide explaining today's PANCHANGA (the Vedic daily almanac) in everyday language. Keep it simple, practical and encouraging — no heavy jargon.

Date: {p.get('date')} ({vaara.get('name')}) at {p.get('place') or 'the chosen place'} — computed with the {engine} engine.
Sunrise {p.get('sunrise')}, sunset {p.get('sunset')}.
The five limbs:
- Tithi (lunar day): {tithi.get('name')} ({tithi.get('paksha')} paksha){', ends ' + tithi.get('ends') if tithi.get('ends') else ''}
- Nakshatra (star): {nak.get('name')}{' pada ' + str(nak.get('pada')) if nak.get('pada') else ''}
- Yoga: {yoga.get('name')}
- Karana: {karana.get('name')}
Auspicious window — Abhijit muhurta: {_rng(p.get('abhijit'))}.
Periods to avoid — Rahu Kalam {_rng(p.get('rahu_kalam'))}, Yamaganda {_rng(p.get('yamaganda'))}, Gulika {_rng(p.get('gulika'))}.
Favourable planetary hours (benefic day-horas):
{good_lines}
Hijri (Islamic) date: {(str(hijri.get('day')) + ' ' + hijri.get('month_name') + ' ' + str(hijri.get('year')) + ' AH') if hijri else 'n/a'}.

Write a friendly ~250-300 word day-guide:
1. **The day's mood** — what this tithi + nakshatra + weekday combination traditionally feels like, in a sentence or two.
2. **Good windows** — point to the Abhijit muhurta and a benefic hora as good times for important tasks (starting things, meetings, decisions), with the clock times.
3. **Go gently** — note the Rahu Kalam / Yamaganda / Gulika windows as times to avoid launching anything important, framed lightly.
4. End with one short, encouraging line.

Use only the times given; do NOT invent windows. Do NOT make medical, financial, legal or fated claims. Close with a one-line reminder that the panchanga is a traditional rhythm-of-the-day aid for reflection, not a rule to live by."""

    def _build_muhurta_prompt(self, m: Dict[str, Any]) -> str:
        """Explain the recommended auspicious windows for the chosen activity."""
        windows = m.get("best_windows", [])[:8]
        win_lines = "\n".join(
            f"- {w['date']} {w['start']}–{w['end']} · {w['label']} ({w['quality']}) — {w['reason']}"
            for w in windows
        ) or "- (no clearly auspicious window found in this range)"

        # A few of the strongest days for context.
        days = sorted(m.get("days", []), key=lambda d: -d.get("score", 0))[:4]
        day_lines = "\n".join(
            f"- {d['date']} ({d['weekday']}): {d['rating']} — {d['nakshatra']['name']} nakshatra, "
            f"{d['tithi']['name']} tithi, {d['yoga']['name']} yoga"
            for d in days
        ) or "- (none)"

        return f"""You are a warm, practical Vedic muhurta (electional astrology) guide helping someone pick an auspicious time for: **{m.get('activity_label', 'their activity')}**, between {m.get('start_date')} and {m.get('end_date')} at {m.get('place') or 'the chosen place'}.

The engine has already scored each day from its Panchanga (nakshatra, tithi, weekday, yoga) and, avoiding Rahu Kalam / Yamaganda / Gulika, extracted concrete time windows.

Top recommended windows (use ONLY these — do not invent times):
{win_lines}

Strongest days in the range:
{day_lines}

Write a friendly ~250-word note:
1. **Best pick** — recommend the single strongest window (date + clock time) and say plainly WHY (which nakshatra / tithi / hora makes it good).
2. **Alternatives** — mention 1–2 backup windows.
3. **What to avoid** — remind them the choppy periods (Rahu Kalam etc.) are already excluded, and to keep the activity within the given window.
Keep it grounded and encouraging. Do NOT make fated, medical, legal or financial guarantees. Close with one line noting muhurta is a traditional aid to timing, and personal readiness matters too."""

    def _build_prashna_prompt(self, p: Dict[str, Any]) -> str:
        """A Prashna (horary) reading of the moment-chart for the question asked."""
        lagna = p.get("lagna") or {}
        moon = p.get("moon") or {}
        sun = p.get("sun") or {}
        panch = p.get("panchanga") or {}
        moment = p.get("moment") or {}
        planets = p.get("planets") or {}

        # Compact one-line placements for the nine grahas.
        plines = "\n".join(
            f"- {name}: {info.get('sign_name')} {round(info.get('degrees', 0), 1)}°"
            f"{' (retrograde)' if info.get('retrograde') else ''}, "
            f"{info.get('nakshatra')} nakshatra"
            for name, info in planets.items()
        )
        tithi = panch.get("tithi") or {}
        nak = panch.get("nakshatra") or {}

        question = p.get("question") or "(no specific question given — read the general tenor)"

        return f"""You are an experienced Vedic PRASHNA (horary) astrologer. A chart has been cast for the exact MOMENT the question was asked — in Prashna, this moment-chart itself answers the question; no birth data is used. Read it in that spirit: the Ascendant is the querent, the Moon is the mind and the matter asked about, and the relevant house/lord shows the outcome.

The question: "{question}"

Moment: {moment.get('date')} {moment.get('time')} at {p.get('place') or 'the chosen place'}
Ascendant (Lagna): {lagna.get('sign_name')} {round(lagna.get('degrees', 0), 1)}°
Moon: {moon.get('sign_name')}, {moon.get('nakshatra')} nakshatra pada {moon.get('nakshatra_pada')}
Sun: {sun.get('sign_name')}
Running hora (planetary hour) lord: {p.get('hora_lord') or 'n/a'}
Panchanga: {tithi.get('name')} tithi ({tithi.get('paksha')} paksha), {nak.get('name')} nakshatra.
Planetary placements at the moment:
{plines}

Write a focused ~300-word horary reading:
1. **The lay of the chart** — one line on the Ascendant + the Moon's condition (its sign, nakshatra, whether it's waxing/strong), since the Moon is central in Prashna.
2. **The answer** — address the question directly: lean toward a "likely yes", "likely no", or "mixed / conditional", grounded in the relevant house, its lord, and the Moon's placement/aspects. Be honest about ambiguity.
3. **Timing** — if the chart suggests a timeframe (from the Moon's nakshatra, the lord's position, or an applying aspect), give a gentle sense of when.
4. **Guidance** — one practical, encouraging suggestion.
Reason from the placements given; cite the factors behind your read. Do NOT make medical, legal or financial guarantees, and frame the answer as astrological guidance, not certainty."""

    def _build_daily_digest_prompt(self, d: Dict[str, Any], name: str) -> str:
        """A warm personalized 'today' reading tying panchanga + dasha + transits."""
        panch = d.get("panchanga") or {}
        dasha = d.get("dasha") or {}
        transits = d.get("transits") or {}
        tithi = panch.get("tithi") or {}
        nak = panch.get("nakshatra") or {}
        vaara = panch.get("vaara") or {}
        highlights = "\n".join(f"- {h}" for h in d.get("highlights", [])) or "- (a quiet day)"
        bhukti = (dasha.get("bhukti") or {})
        upcoming = "\n".join(
            f"- {u['planet']} enters {u['to_sign']} on {u['date']}"
            for u in transits.get("upcoming", [])
        ) or "- (none imminent)"
        retro = transits.get("retrograde", [])

        return f"""You are a warm, encouraging personal Vedic astrologer writing {name}'s DAILY briefing for {d.get('date')}. Tie together the day's almanac, their current dasha period, and the sky's transits into one short, grounded note. Speak TO them ("you"), plainly.

Today's panchanga: {vaara.get('name')}, {tithi.get('paksha')} {tithi.get('name')}, {nak.get('name')} nakshatra.
Current dasha: {dasha.get('maha_lord', 'n/a')} Mahadasha{', ' + bhukti.get('lord') + ' Bhukti' if bhukti.get('lord') else ''} (Mahadasha runs to {dasha.get('maha_end', 'n/a')}).
Sade-Sati active: {'yes' if transits.get('sade_sati') else 'no'}.
Retrograde now: {', '.join(retro) if retro else 'none'}.
Upcoming ingresses:
{upcoming}
Key highlights the engine flagged:
{highlights}

Write a friendly ~200-word daily note:
1. **Today's tone** — what the tithi + nakshatra + weekday invite, in a sentence or two.
2. **Your bigger arc** — a line tying it to the current dasha/bhukti (and Sade-Sati or a nearing dasha change if flagged), framed constructively.
3. **A gentle nudge** — one practical suggestion for making the most of today.
End on an encouraging line. Do NOT make fated, medical, legal or financial claims; keep it a supportive daily reflection."""

    def _build_period_digest_prompt(self, d: Dict[str, Any], name: str, period: str) -> str:
        """A warm fortnight / month reading tying the running dasha to the window's
        transit events and its progressed (pravesha) chart. Which chart that is
        depends on the rung + basis the compute layer actually cast:
        Paksha Pravesha (fortnight), Maasa Pravesha (solar month) or the
        birth-tithi return (lunar month)."""
        is_fortnight = period == "fortnight"
        basis = d.get("basis") or "solar"
        panch = d.get("panchanga") or {}
        dasha = d.get("dasha") or {}
        transits = d.get("transits") or {}
        pravesh = d.get("pravesh") or {}
        tithi = panch.get("tithi") or {}
        nak = panch.get("nakshatra") or {}
        vaara = panch.get("vaara") or {}
        bhukti = (dasha.get("bhukti") or {})
        retro = transits.get("retrograde", [])
        events = d.get("events", [])
        event_lines = "\n".join(
            f"- {e['date']}: {e['text']}" for e in events
        ) or "- (no sign-changes or stations this window)"

        # Name the rung honestly — the reader should know which chart they're being read.
        noun = "fortnight" if is_fortnight else "month"
        if is_fortnight:
            paksha = pravesh.get("paksha") or "lunar"
            chart_name = f"{paksha} Paksha Pravesha chart (the lunar fortnight)"
            horizon = (f"the {paksha} Paksha you are in — the lunar fortnight, the half of "
                       f"the lunar month running from its first tithi to the next paksha")
        elif basis == "lunar":
            chart_name = "lunar-month chart (your birth tithi returning, ~29.5 days)"
            horizon = "the lunar month you are in (your natal tithi recurring)"
        else:
            chart_name = "Maasa Pravesha chart (the Tajaka monthly solar return)"
            horizon = "the solar month you are in (a Maasa Pravesha window)"

        pravesh_block = ""
        if pravesh:
            lagna = pravesh.get("lagna") or {}
            yogas = pravesh.get("tajaka_yogas") or []
            yoga_lines = "\n".join(
                f"- {y['name']}"
                + (f" ({'/'.join(y['pair'])})" if y.get("pair") else "")
                + (f": {y['description']}" if y.get("description") else "")
                for y in yogas
            ) or "- (none notable)"
            # Muntha and the year-lord are deliberately NOT given to the model here.
            # Both are reckoned from the age in *years*, so they hold the same value
            # for every fortnight and every month of a given year — feed them to a
            # fortnightly reading and the model will dutifully explain a constant as
            # if it were news about this window. (The annual reading still gets them.)
            pravesh_block = f"""
Progressed chart for this {noun} — the {chart_name}, cast at the moment the window opened:
- Lagna: {lagna.get('sign_name')}
- Active Tajaka yogas in it:
{yoga_lines}
"""

        window = f"{d.get('start_date')} → {d.get('end_date')} ({d.get('span_days')} days)"

        return f"""You are a warm, encouraging personal Vedic astrologer writing {name}'s briefing for {horizon}: {window}. Weave their current dasha period together with the progressed chart for this {noun} and the sky's movements across the window into one grounded, supportive note. Speak TO them ("you"), plainly.

Window opened on: {vaara.get('name')}, {tithi.get('name')}, {nak.get('name')} nakshatra.
Current dasha: {dasha.get('maha_lord', 'n/a')} Mahadasha{', ' + bhukti.get('lord') + ' Bhukti' if bhukti.get('lord') else ''} (Mahadasha runs to {dasha.get('maha_end', 'n/a')}).
Sade-Sati active: {'yes' if transits.get('sade_sati') else 'no'}. Retrograde now: {', '.join(retro) if retro else 'none'}.
Transit events falling inside this window (sign-ingresses & retrograde stations):
{event_lines}
{pravesh_block}
Key highlights the engine flagged:
{chr(10).join(f'- {h}' for h in d.get('highlights', [])) or '- (a steady window)'}

Write a friendly ~{'230' if is_fortnight else '260'}-word note on this {noun}:
1. **The theme of this {noun}** — what the dasha/bhukti and the progressed Lagna set as the backdrop, framed constructively.
2. **What shifts and when** — walk through the 2–3 most meaningful transit events above (an ingress, a retrograde station, a Tajaka yoga), naming their dates so they can plan around them.
3. **A gentle plan** — one or two practical suggestions for making the most of this {noun}.
Reason only from the data above; do not invent placements. End on an encouraging line. Do NOT make fated, medical, legal or financial claims; keep it a supportive forward-looking reflection."""

    # Each rung of the lunar pravesha ladder, as the reading should frame it:
    # (what the window is, the horizon word, the target length).
    _PRAVESHA_RUNGS = {
        "tithi": ("the moment the running **tithi** opens — a lunar 'day' of roughly 24 hours",
                  "day", 180),
        "paksha": ("the moment the current **paksha** (lunar fortnight) opens — the waxing or "
                   "waning half of the lunar month, about 15 days",
                   "fortnight", 220),
        "month": ("the moment {name}'s **birth tithi recurs** — a lunar month of about 29.5 days",
                  "month", 240),
        "annual": ("the moment {name}'s **natal tithi and lunar month recur** — a lunar-year "
                   "return of roughly 354 days (384 in an adhika-masa year)",
                   "year", 280),
    }

    def _build_tithi_pravesha_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Reading of a chart on the lunar (tithi) pravesha ladder.

        One prompt for all four rungs. The year-reckoned panels — Muntha, year-lord,
        Sahams — exist only on the annual rung (they are derived from the age in
        *years*, so they are meaningless for a single tithi), and the prompt simply
        omits them below it rather than inviting the model to read noise."""
        lagna = d.get("lagna") or {}
        window = d.get("window") or {}
        planets = d.get("planets") or {}
        yogas = d.get("tajaka_yogas") or []

        rung = d.get("rung", "annual")
        what_it_is, horizon, words = self._PRAVESHA_RUNGS.get(
            rung, self._PRAVESHA_RUNGS["annual"])
        what_it_is = what_it_is.format(name=name)
        is_annual = rung == "annual"

        planet_lines = "\n".join(
            f"- {p}: {v.get('sign_name')} {v.get('degrees')}°"
            for p, v in planets.items()
        ) or "- (none)"

        # The year-only block. Below the annual rung there is nothing honest to put here.
        annual_block = ""
        if is_annual:
            muntha = d.get("muntha") or {}
            yl = d.get("year_lord") or {}
            yoga_lines = "\n".join(
                f"- {y['name']}"
                + (f" ({'/'.join(y['pair'])})" if y.get("pair") else "")
                + (f": {y['description']}" if y.get("description") else "")
                for y in yogas
            ) or "- (none notable)"
            # These are the Tajaka *chart* judgements — Ithasala/Eesarpha (applying and
            # separating by degree) and Ishkavala/Induvara (house distribution). They
            # read the geometry of the chart in front of them, so they are at home on a
            # lunar return; the year-reckoned Tajaka devices are not, and are labelled
            # for the model as the solar imports they are.
            annual_block = f"""- Muntha (progressed ascendant, reckoned in solar years): {muntha.get('sign_name')}, house {muntha.get('house')} of this chart
- Year-lord: {yl.get('planet', 'n/a')}
Applying / separating aspects in this chart:
{yoga_lines}
"""

        # The running compressed Tithi Ashtottari lord — the sharpest thing to say about
        # a short window, where a maha period may last only hours.
        dasha_line = ""
        ta = d.get("tithi_ashtottari") or {}
        running = next((p for p in ta.get("periods") or [] if p.get("current")), None)
        if running:
            dasha_line = (
                f"\nRunning period of this window's **compressed Tithi Ashtottari** "
                f"(the whole 108-unit cycle fitted into this {horizon}): "
                f"**{running.get('lord_name')}**, {running.get('start')} → {running.get('end')}.\n")

        return f"""You are a warm, grounded Vedic astrologer reading {name}'s **{'Tithi Pravesha' if is_annual else 'lunar pravesha'}** chart. Explain what has already been computed; do not recompute or invent placements.

**What this chart is.** It is cast for {what_it_is}. This is the *lunar* ladder: where the Tajaka/Varshaphal charts time things from the Sun's return, these time them from the Moon–Sun relationship at birth. Traditionally the lunar side is read for the emotional, domestic and mental texture of a period, alongside (not instead of) the solar chart.

This {horizon}: **{d.get('label', 'n/a')}**, running {window.get('start_at') or window.get('start')} → {window.get('end_at') or window.get('end')} ({window.get('span_days')} days).

Chart cast at the pravesha moment:
- Lagna: {lagna.get('sign_name')} {lagna.get('degrees')}°
{annual_block}Planets:
{planet_lines}
{dasha_line}
Write a grounded ~{words}-word reading:
1. **The tone of the {horizon}** — what the Lagna and its lord set as the backdrop{', and what the Muntha activates' if is_annual else ''}.
2. **Where the emphasis falls** — 2–3 of the most telling placements above{' or applying/separating aspects' if is_annual else ''}, and the areas of life they touch{', plus what the running dasha lord colours' if running else ''}.
3. **How to work with it** — one or two calm, practical suggestions{'' if is_annual else f', scaled to a {horizon} — concrete and near-term, not life-defining'}.
Close with a line noting that this chart is read *alongside* the solar one, and that it is indicative rather than fated. Do NOT make medical, legal or financial predictions."""

    def _build_bhrigu_markers_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Read the Nadi/Bhrigu yearly markers: the Moon-based annual progression
        and the Bhrigu Bindu activations."""
        bb = d.get("bhrigu_bindu") or {}
        prog = d.get("progression") or []
        acts = d.get("activations") or []

        prog_lines = "\n".join(
            f"- Age {p['age']} ({p['year']}): {p['sign_name']} (lord {p['sign_lord']})"
            + (f", natal {', '.join(p['planets'])} here" if p.get("planets") else ", empty sign")
            + (" ← Bhrigu Bindu sign" if p.get("is_bhrigu_bindu") else "")
            + (" ← natal Moon sign" if p.get("is_moon_sign") else "")
            for p in prog
        ) or "- (none)"

        act_lines = "\n".join(
            f"- {a['date']}: {a['planet']} enters {a['sign_name']} ({a['target']} sign)"
            for a in acts
        ) or "- (none in the searched horizon)"

        return f"""You are a thoughtful Vedic astrologer explaining {name}'s **Bhrigu / Nadi-style yearly markers**. Two classical, clearly-labelled devices have been pre-computed — read them, do not recompute or invent placements.

**1. Annual progression (Nadi one-sign-per-year from the Moon).** The natal Moon is in {d.get('moon_sign')}. Each year of life the "marker sign" advances by one rasi; the natal planets sitting in that sign are what the year activates. Current age: {d.get('age_now')}.
{prog_lines}

**2. Bhrigu Bindu (the Rahu–Moon midpoint, a Nadi sensitive point).** It sits in {bb.get('sign_name')} at {bb.get('degrees')}°, house {bb.get('house_from_lagna')} from the Lagna (lord {bb.get('sign_lord')}). The next Jupiter/Saturn transits that activate the Bhrigu Bindu and Moon signs:
{act_lines}

Write a grounded ~280-word note:
1. **The theme of the coming years** — walk through 2–3 of the most notable progressed years above (those with natal planets, or the Bhrigu-Bindu / Moon-sign years) and what area of life the sign + its occupants suggest.
2. **Milestone triggers** — mention the nearest Jupiter or Saturn activation date and why a slow-planet touching the Bhrigu Bindu is treated as a turning-point in Nadi thought.
3. **How to use it** — one calm, practical line.
Reason only from the markers given. Frame everything as a traditional predictive *aid* — evocative, not fated. Do NOT make medical, legal or financial predictions. Close with one line noting these are indicative markers, and free will shapes the outcome."""

    def _build_timeline_window_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Read a single point on the life timeline: the running dasha, the Saturn
        phase, and the transits clustering around that date."""
        maha = d.get("maha") or {}
        bhukti = d.get("bhukti") or {}
        sat = d.get("saturn_phase") or {}
        ingr = d.get("ingresses") or []
        ecl = d.get("eclipses") or []

        dasha_line = "Dasha could not be resolved for this date."
        if maha:
            dasha_line = (f"Mahadasha of **{maha.get('lord')}** "
                          f"({maha.get('start_date')} → {maha.get('end_date')})")
            if bhukti:
                dasha_line += (f", Bhukti of **{bhukti.get('lord')}** "
                               f"({bhukti.get('start_date')} → {bhukti.get('end_date')})")
        sat_line = ("Saturn is not in a Sade Sati / Ashtama / Kantaka position "
                    "from the Moon around this date.")
        if sat:
            sat_line = (f"{sat.get('description')} — Saturn in {sat.get('sign_name')} "
                        f"({sat.get('start_date')} → {sat.get('end_date')}).")
        ingr_lines = "\n".join(
            f"- {i['date']}: {i['planet']} enters {i['to_sign']}" for i in ingr
        ) or "- (no major slow-planet ingress within ~9 months)"
        ecl_lines = "\n".join(
            f"- {e['date']}: {e['kind']} eclipse in {e['nakshatra']}"
            + (f" — on your natal {', '.join(e['natal_planets'])}'s nakshatra"
               if e.get("on_natal_nakshatra") else "")
            for e in ecl
        ) or "- (none within ~9 months)"

        return f"""You are a grounded Vedic astrologer reading a single window in {name}'s life timeline: the period around **{d.get('target_date')}**. Everything below has been pre-computed — reason from it, do not recompute or invent placements. The natal Moon is in {d.get('moon_sign')}.

**Running dasha:** {dasha_line}
**Saturn (gochara) phase:** {sat_line}
**Slow-planet ingresses nearby:**
{ingr_lines}
**Eclipses nearby:**
{ecl_lines}

Write a focused ~260-word reading of this window:
1. **The governing period** — what the Mahadasha lord + Bhukti lord combination classically colours this stretch of life with (the dasha lord sets the theme, the bhukti lord the sub-theme).
2. **Saturn's weather** — if a Sade Sati / Ashtama / Kantaka phase is active, explain its character honestly but calmly (a period of maturing, responsibility and consolidation — not doom); if none, say the Saturn pressure is lighter now.
3. **Turning-point transits** — mention the nearest ingress or a natal-nakshatra eclipse as a timing marker for shifts.
Reason only from what's given. Be encouraging and practical, never fatalistic. Do NOT make medical, legal or financial predictions or name specific outcomes/dates of misfortune. Close with one line noting this is an indicative reading and free will shapes how a period is lived."""

    def _build_friendships_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the compound friendships + house-lord placements + exchanges."""
        matrix = d.get("matrix") or []
        hl = d.get("house_lords") or []
        pari = d.get("parivartana") or []
        m_lines = "\n".join(
            f"- {row['planet']}: "
            + ", ".join(f"{r['to']} {r['label']}" for r in row["relations"] if not r.get("self"))
            for row in matrix
        ) or "- (none)"
        hl_lines = "\n".join(
            f"- Lord of H{h['house']} ({h['signification']}) is {h['lord']}, "
            f"placed in H{h['lord_house']} ({h['lord_house_signification']})"
            for h in hl if h.get("lord_house")
        ) or "- (none)"
        pari_line = (
            "; ".join(f"{p['planets'][0]}↔{p['planets'][1]} (H{p['houses'][0]}/H{p['houses'][1]})"
                      for p in pari)
            if pari else "none")
        return f"""You are a precise Vedic astrologer explaining the **planetary relationships** in {name}'s chart. All values are pre-computed (compound = natural friendship folded with this chart's temporal placement) — read them, do not recompute.

**Compound friendships** (Adhimitra=great friend, Mitra=friend, Sama=neutral, Shatru=enemy, Adhishatru=great enemy):
{m_lines}

**House-lord placements** (where each bhava's lord actually sits — the engine of that house's results):
{hl_lines}

**Parivartana (mutual sign exchange):** {pari_line}

Write a grounded ~260-word reading:
1. **The alliances that matter** — note 1–2 planets sitting in a great-friend's or great-enemy's sign/company and what that does to how they cooperate (a planet among friends works smoothly; among enemies, with friction).
2. **How the houses are wired** — read 2–3 of the most telling house-lord placements (e.g. lord of the 1st in the 10th links self to career); use the significations given, in plain terms.
3. **Any exchange** — if a Parivartana exists, explain that the two houses' affairs are tied together; if none, say so.
Reason only from the data. Relationships shade *how* results come, they are not good/bad verdicts. No medical, lifespan, legal or financial predictions. Close with one encouraging line."""

    def _build_saturn_transits_prompt(self, d: Dict[str, Any], name: str) -> str:
        """A grounded, calm reading of the Sade Sati / Saturn transits."""
        cur = d.get("current") or {}
        periods = d.get("sade_sati_periods") or []
        cur_ss = cur.get("sade_sati")
        cur_ash = cur.get("ashtama")
        cur_kan = cur.get("kantaka")
        if cur_ss:
            status = (f"Currently in **Sade Sati — {cur_ss.get('current_phase')} phase** "
                      f"({cur_ss.get('start_date')} → {cur_ss.get('end_date')}).")
        elif cur_ash:
            status = (f"Not in Sade Sati now, but in **Ashtama Shani** (Saturn 8th from "
                      f"the Moon, {cur_ash.get('start_date')} → {cur_ash.get('end_date')}).")
        elif cur_kan:
            status = (f"Not in Sade Sati now, but in **Kantaka Shani** (Saturn 4th from "
                      f"the Moon, {cur_kan.get('start_date')} → {cur_kan.get('end_date')}).")
        else:
            status = "Not in Sade Sati, Ashtama or Kantaka Shani at present — Saturn's pressure on the Moon is light right now."
        p_lines = "\n".join(
            f"- {p['start_date']} → {p['end_date']}"
            + (" (current)" if p.get("is_current") else " (past)" if p.get("is_past") else " (upcoming)")
            + ": " + ", ".join(
                f"{ph['phase']} in {ph['sign_name']} ({ph['start_date']}→{ph['end_date']})"
                for ph in p.get("phases", []))
            for p in periods
        ) or "- (none in the scanned window)"
        return f"""You are a calm, wise Vedic astrologer explaining **Sade Sati and Saturn's transits** over {name}'s natal Moon (in {d.get('moon_sign')}). Everything is pre-computed — read it, do not recompute. Saturn (Shani) is the teacher: his transits mature and consolidate, they are not doom.

**Right now:** {status}

**Sade Sati cycles (Saturn over the 12th → 1st → 2nd from the Moon, ~7½ years each):**
{p_lines}

Write a grounded, reassuring ~280-word reading:
1. **What's happening now** — explain the current status plainly. If a Sade Sati / Ashtama / Kantaka phase is running, describe its character honestly but calmly (responsibility, slowing down, maturing, letting go of what no longer serves) and roughly when it eases. If nothing is running, say so and reassure.
2. **The rhythm of the cycles** — note that Sade Sati recurs about every 30 years and that each is a chapter of growth, not punishment; mention the phase structure (rising = build-up, peak = core lessons, setting = integration).
3. **How to move through it well** — 2–3 practical, dignified suggestions (discipline, service, patience, simplicity), and point them to the Remedies page for traditional Shani upayas.
Reason only from the data. NEVER predict misfortune, illness, death, financial ruin or specific bad events — Sade Sati is a period of growth, not a curse. Close with one genuinely encouraging line."""

    def _build_strength_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the strength picture: Shadbala, Bhava Bala and Vimsopaka."""
        planets = d.get("planets") or []
        bhava = d.get("bhava_bala") or []
        vim = d.get("vimsopaka") or []
        p_lines = "\n".join(
            f"- {p['planet']}: {p['total_rupa']} / {p['required_rupa']} rupa "
            f"(ratio {p['strength_ratio']}, rank {p['rank']}"
            + ("" if p.get("sufficient") else ", below required") + ")"
            for p in sorted(planets, key=lambda x: x.get("rank", 9))
        ) or "- (none)"
        b_lines = "\n".join(
            f"- H{b['house']} ({b['signification']}): {b['rupa']} rupa, ratio {b['strength_ratio']}"
            for b in sorted(bhava, key=lambda x: x.get("rank", 13))[:4]
        ) or "- (none)"
        v_lines = "\n".join(
            f"- {v['planet']}: {v['shodhasavarga']}/20 (16-varga)"
            for v in sorted(vim, key=lambda x: x.get("shodhasavarga", 0), reverse=True)[:4]
        ) or "- (none)"
        return f"""You are a precise Vedic astrologer explaining {name}'s **planetary strength**. All values are pre-computed — read them, do not recompute. Strength says how *capably* a planet or house delivers its results, not whether the results are good or bad.

**Shadbala** (six-fold strength; a planet is sufficient when its ratio ≥ 1.0), strongest first:
{p_lines}

**Bhava Bala** (house strength) — the strongest houses:
{b_lines}

**Vimsopaka Bala** (varga-dignity, out of 20) — the best-placed planets across divisional charts:
{v_lines}

Write a grounded ~270-word reading:
1. **The powerhouses** — the 1–2 strongest grahas (high Shadbala ratio + high Vimsopaka) and what they can reliably deliver (via their karakatva + the houses they rule/occupy).
2. **What needs support** — the 1–2 weakest (ratio < 1 or low), framed constructively — these areas ask for conscious effort, not doom; a natural place to mention that the Remedies page suggests upayas for exactly these.
3. **Which life-areas are well-founded** — read the 1–2 strongest houses (Bhava Bala) in plain terms.
Reason only from the numbers given. Never equate "strong" with "good" or "weak" with "bad" — a strong malefic can act forcefully. No medical, lifespan, legal or financial predictions. Close with one encouraging line."""

    def _build_nakshatra_profile_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Warm layman reading of the janma-nakshatra + this month's tarabala."""
        p = d.get("profile") or {}
        cal = d.get("tarabala_calendar") or []
        good_days = [c for c in cal if c.get("tone") in ("very_good", "good")]
        bad_days = [c for c in cal if c.get("tone") == "bad"]
        good_line = ", ".join(c["date"] for c in good_days[:6]) or "none in this window"
        bad_line = ", ".join(c["date"] for c in bad_days[:6]) or "none in this window"
        return f"""You are a warm, plain-spoken Vedic astrologer introducing {name} to their **birth star (janma-nakshatra)** — the single most personal point in the chart for a lay reader. No jargon dumps; explain any term in a few words.

Their birth star: **{p.get('name')}** (pada {p.get('pada')}), ruled by **{p.get('lord')}**, in the sign {d.get('moon_sign')}.
- Presiding deity: {p.get('deity')}
- Symbol: {p.get('symbol')}
- Temperament (gana): {p.get('gana')}   ·   Animal (yoni): {p.get('yoni')}
- Constitution (nadi): {p.get('nadi')}   ·   Quality (guna): {p.get('guna')}   ·   Varna: {p.get('varna')}
- Traditional theme: {p.get('theme')}
- Auspicious naming syllable: {p.get('naming_syllable')}

Tarabala (star-strength) for the next 27 days: favourable days include {good_line}; days to keep low-key include {bad_line}.

Write a friendly ~260-word profile:
1. **Who you are** — the personality and gifts this birth star classically confers, drawing on the deity, symbol and theme (2 short paragraphs).
2. **Your rhythm this month** — explain in one line what tarabala means (your personal good/challenging days as the Moon circles the sky), then point to when to push forward vs rest, using the dates above.
3. One grounded, encouraging closing line.
This is a personality-and-timing sketch, not prediction. No medical, financial, lifespan or legal claims."""

    def _build_gochara_phala_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Warm reading of the Moon-referenced gochara-phala with vedha."""
        rows = d.get("results") or []
        def line(r):
            tag = {"good": "favourable", "caution": "favourable but blocked by vedha",
                   "bad": "not favourable"}.get(r.get("tone"), r.get("verdict"))
            extra = ""
            if r.get("obstructed_by"):
                extra = f" (blocked by {', '.join(r['obstructed_by'])})"
            return f"- {r['planet']}: {r['house_from_moon']}th from Moon → {tag}{extra}"
        body = "\n".join(line(r) for r in rows) or "- (no data)"
        return f"""You are a warm, plain-spoken Vedic astrologer giving {name} the classical **gochara-phala** (Moon-referenced transit reading) that panchang readers use — different from a degree-by-degree transit chart. Explain terms simply.

How it works (say this briefly in your own words): each planet's transit is judged by how many signs away it is from the birth Moon. Some positions are classically favourable; but a favourable result can be cancelled by **vedha** — another planet sitting in a specific "obstruction" sign. Today's picture ({d.get('transit_date')}), Moon sign {d.get('moon_sign')}:
{body}

Write a friendly ~240-word reading:
1. **The supportive transits right now** — name the clearly favourable ones and what areas of life they lift (in everyday terms).
2. **Blocked or testing transits** — explain any vedha-blocked or unfavourable ones gently, as areas to be patient with, not doom.
3. One practical, encouraging closing line about the overall tone of this window.
Base everything only on the list above. No medical, financial, lifespan or legal predictions."""

    def _build_avasthas_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the planetary avasthas (Baladi / Jagradadi / Deeptadi)."""
        planets = d.get("planets") or []
        lines = "\n".join(
            f"- **{p['planet']}** ({p['sign_name']} {p['degrees']}°, {p['dignity']}): "
            f"Baladi {p['baladi']['state']} ({p['baladi']['meaning']}, {p['baladi']['strength']}); "
            f"Jagradadi {p['jagradadi']['state']} ({p['jagradadi']['meaning']}); "
            f"Deeptadi {p['deeptadi']['state']} ({p['deeptadi']['description']}) [{p['deeptadi']['tone']}]"
            for p in planets
        ) or "- (none)"
        return f"""You are a precise Vedic astrologer explaining the **avasthas** (planetary states) in {name}'s chart. These describe the *mood and vitality* each graha carries — how ready it is to give its results — and complement raw strength (Shadbala). They have already been computed; read them, do not recompute.

Three classical schemes per planet:
- **Baladi** (age): Bala infant → Kumara → **Yuva (prime, strongest)** → Vriddha → Mrita (dead, gives nothing) — by the planet's degree in its sign.
- **Jagradadi** (wakefulness): Jagrat (awake, full results) / Swapna (dreaming, partial) / Sushupti (asleep, weak) — by dignity.
- **Deeptadi** (temperament): from Deepta (radiant, exalted) through to Vikala (combust), Khala (with a malefic) and Kopa (in a planetary war).

{lines}

Write a grounded ~260-word note:
1. **The brightest and the dimmest** — name the 1–2 planets in the best states (e.g. Yuva + Jagrat + Deepta/Swastha) and the 1–2 in the weakest (Mrita, Sushupti, Vikala/Deena), and what life-areas they govern (via each planet's natural karakatva).
2. **How to read a mixed state** — pick one planet whose schemes disagree (e.g. strong Baladi but asleep Jagradadi) and explain what that tension suggests about how its results arrive.
3. **Practical takeaway** — one calm, constructive line.
Reason only from the states given. Treat avasthas as a *nuance of vitality*, never a verdict; do NOT make medical, lifespan, legal or financial predictions. Close with one encouraging line."""

    def _build_planet_conditions_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the classical planet-condition flags that colour a reading."""
        flagged = d.get("flagged") or []
        if not flagged:
            lines = "No special point-conditions stood out — the grahas sit in ordinary dignity."
        else:
            lines = "\n".join(
                f"- **{p['planet']}** ({p['sign_name']} {p['degrees']}°, house {p['house']}): "
                + ", ".join(
                    f['label'] + (f" with {f['partner']} ({f['separation']}° apart)"
                                  if f.get('partner') else "")
                    + f" [{f['tone']}]"
                    for f in p['flags'])
                for p in flagged
            )
        c = d.get("counts") or {}
        return f"""You are a precise Vedic astrologer explaining the **special point-conditions** ("flags") in {name}'s chart — the classical states that modify how a planet delivers its results but don't show on a plain Kundali. They have already been computed; read them, do not recompute or invent placements.

Flagged planets ({c.get('benefic',0)} benefic, {c.get('challenging',0)} challenging, {c.get('neutral',0)} neutral):
{lines}

Write a clear ~260-word note:
1. **What stands out** — walk through the 2–3 most significant flags. Explain each briefly in plain terms: e.g. *combust* = a planet's significations are "burnt"/strained by proximity to the Sun; *vargottama* / *pushkara* = strengthening, well-placed; *gandanta* = a sensitive karmic "knot"; *mrityu bhaga* / *marana karaka* = a delicate, testing placement; *graha yuddha* = two planets in a war of strength; *retrograde* = an internalised, revisiting quality.
2. **The balance** — is the chart net-supported or net-tested by these conditions, and which life-areas (via the planet's house/karakatva) each touches?
3. **How to hold it** — one grounded, constructive line.
Reason only from the flags given. Be honest but never alarming — these are nuances, not verdicts. Do NOT make medical, legal, financial or lifespan predictions (mrityu bhaga is a classical *degree*, NOT a statement about death). Close with one calm, encouraging line."""

    def _build_remedies_prompt(self, d: Dict[str, Any], name: str) -> str:
        """Explain the suggested per-planet remedies, warmly and responsibly."""
        rems = d.get("remedies") or []
        if not rems:
            body = "No planet came out clearly weak or afflicted in this chart — a reassuring sign."
            rem_lines = ""
        else:
            body = (f"{len(rems)} planet(s) came out weak or afflicted "
                    "(debilitated, shadbala-deficient, or in a dusthana).")
            rem_lines = "\n".join(
                f"- **{r['planet']}** ({r['reason']}): gemstone {r['gemstone']}, "
                f"mantra \"{r['mantra']}\" (~{r.get('mantra_count')} times), deity {r['deity']}, "
                f"day {r['day']}, charity: {r['donation']}, colour {r['color']}."
                for r in rems
            )

        return f"""You are a warm, responsible Vedic astrologer explaining traditional **remedial measures (upaya)** for {name}. The chart's weak/afflicted planets and the classical remedies for each have already been computed — explain them, do not invent new ones.

{body}
{rem_lines}

Write a caring ~260-word note:
1. **What's asking for support** — in plain language, which planet(s) are running weak and what life-areas they touch (keep it constructive, never alarming).
2. **The gentlest remedies first** — emphasise that mantra, charity (daana), fasting on the planet's weekday, and devotion are the safe, accessible upayas anyone can begin; walk through 1–2 concretely.
3. **On gemstones** — note clearly that gemstones and yantras are powerful and should be worn ONLY after consulting a qualified astrologer, never self-prescribed.
Frame all of this as **traditional guidance and devotional practice, not medical, psychological, legal or financial advice**, and not a guarantee of results. Close by reminding them that sincere effort and good conduct are themselves the strongest remedy."""

    def _build_kp_prompt(self, d: Dict[str, Any], name: str) -> str:
        """A Krishnamurti Paddhati (KP) reading grounded in cuspal sub-lords,
        the four-fold significators and the ruling planets."""
        planets = d.get("planets") or []
        cusps = d.get("cusps") or []
        sig = d.get("significators") or {}
        rp = (d.get("ruling_planets") or {}).get("planets") or []

        p_lines = "\n".join(
            f"- {p['body']}: {p['sign_name']} {p['degrees']}° (house {p['house']}), "
            f"sign lord {p['sign_lord']}, star lord {p['star_lord']}, sub lord {p['sub_lord']}"
            for p in planets)
        c_lines = "\n".join(
            f"- Cusp {c['house']}: {c['sign_name']}, sub lord {c['sub_lord']}"
            for c in cusps)
        s_lines = "\n".join(
            f"- {planet}: signifies houses {', '.join(str(h) for h in info.get('houses', []))} "
            f"(star lord {info.get('star_lord')})"
            for planet, info in sig.items())

        return f"""You are an expert **KP (Krishnamurti Paddhati)** astrologer reading {name}'s chart. KP judges results by the **sub-lord** of the relevant cusp and by a planet's **star (nakshatra) lord** — a planet gives the results of the houses signified by its star lord first. Everything below is already computed on the KP (Krishnamurti) ayanamsa — read it, do not recompute.

Ascendant & planets (sign / star / sub lords):
{p_lines}

Cuspal sub-lords:
{c_lines}

Four-fold significators (houses each planet signifies):
{s_lines}

Ruling planets right now: {', '.join(rp) if rp else 'n/a'}.

Write a focused ~320-word KP reading:
1. **How to read this chart in KP** — one or two lines on what the Ascendant sub-lord and the chart's overall significator pattern suggest.
2. **Two or three life areas** — pick houses that matter (e.g. 7th for marriage, 10th for career, 2nd/11th for wealth) and judge them from their **cuspal sub-lord** and its significations; name the planets that promise each result.
3. **Timing hint** — note that KP times events by the dasha of a house's significators, and mention the ruling planets as the day's active lords.
Reason strictly from the sub-lords and significators given; cite them. Frame it as astrological guidance, not certainty, and avoid medical/legal/financial guarantees."""

    def _build_kp_horary_prompt(self, d: Dict[str, Any], question: str) -> str:
        """A KP horary (1-249) judgement for the querent's number + question."""
        asc = d.get("ascendant") or {}
        planets = d.get("planets") or []
        rp = (d.get("ruling_planets") or {}).get("planets") or []
        moment = d.get("moment") or {}
        p_lines = "\n".join(
            f"- {p['body']}: {p['sign_name']} {p['degrees']}°, star lord {p['star_lord']}, sub lord {p['sub_lord']}"
            for p in planets)
        q = question or "(no specific question given — read the general tenor)"
        return f"""You are an expert **KP horary (Prasna)** astrologer. The querent chose the number **{asc.get('number')}** (of 1-249), which fixes the horary Ascendant at **{asc.get('sign_name')} {asc.get('degrees')}°** — sign lord {asc.get('sign_lord')}, star lord {asc.get('star_lord')}, **sub lord {asc.get('sub_lord')}**. The planets are cast for the moment the question was asked ({moment.get('date')} {moment.get('time')}).

The question: "{q}"

Planetary sub-lords at the moment:
{p_lines}

Ruling planets: {', '.join(rp) if rp else 'n/a'}.

Write a ~280-word KP horary judgement:
1. **The Ascendant sub-lord** — in KP horary this is decisive; read what {asc.get('sub_lord')} as the Ascendant sub-lord indicates for the matter (its house significations and whether it favours the querent).
2. **The answer** — lean toward a "likely yes", "likely no", or "conditional", grounded in the sub-lord of the house that governs the question and the ruling planets. Be honest about ambiguity.
3. **Timing** — a gentle sense of when, from the significators/ruling planets.
Reason from the sub-lords given; cite them. Frame it as guidance, not certainty; no medical/legal/financial guarantees."""

    def _build_jaimini_prompt(self, d: Dict[str, Any], name: str) -> str:
        """A Jaimini reading built on the Chara Karakas, Karakamsa/Swamsa and argala."""
        ck = d.get("chara_karakas") or []
        kk = d.get("karakamsa") or {}
        sw = d.get("swamsa") or {}
        argala = d.get("argala") or []
        ck_lines = "\n".join(
            f"- {k['karaka']}: {k['planet']} in {k['sign_name']}"
            + (f" (house {k['house']})" if k.get('house') else "")
            for k in ck)
        arg_lines = "\n".join(
            f"- House {a['house']} ({a['sign_name']}): argala from {', '.join(a['argala']) or 'none'}; "
            f"virodhargala (counter) from {', '.join(a['virodhargala']) or 'none'}"
            for a in argala)
        return f"""You are an expert **Jaimini** astrologer reading {name}'s chart. Jaimini reasons from the **Chara Karakas** (the eight variable significators, ranked by longitude), the **Karakamsa** (the Atmakaraka's Navamsa sign — read like a second ascendant for the soul's agenda) and **argala** (planetary intervention on a house). Everything below is pre-computed — interpret it, do not recompute.

Chara Karakas:
{ck_lines}

Atmakaraka (soul planet): **{d.get('atmakaraka')}**.
Karakamsa: the Atmakaraka {kk.get('planet')} is in **{kk.get('sign_name')}** in the Navamsa; occupants there: {', '.join(kk.get('occupants', [])) or 'none'}; planets aspecting it (rasi drishti): {', '.join(kk.get('aspecting_planets', [])) or 'none'}.
Swamsa (Navamsa Lagna): **{sw.get('sign_name')}**; occupants: {', '.join(sw.get('occupants', [])) or 'none'}; aspected by: {', '.join(sw.get('aspecting_planets', [])) or 'none'}.

Argala (intervention) on the Lagna & 7th:
{arg_lines}

Write a ~320-word Jaimini reading:
1. **The soul's agenda (Karakamsa)** — what the Karakamsa sign, its occupants and the planets aspecting it say about calling, temperament and the deeper life theme (this is the heart of Karakamsa analysis).
2. **The Chara Karakas** — read 2-3 of the key karakas (Atma, Amatya, Dara) and what their placement suggests for self, career and partnership.
3. **Argala** — one line on where the Lagna receives supportive intervention vs a counter (virodhargala).
Reason from the factors given; cite them. Frame it as astrological insight, not fate; no medical/legal/financial guarantees."""

    def _build_now_chart_prompt(self, d: Dict[str, Any]) -> str:
        """Read the chart of the moment (the current sky) as a general tenor."""
        lagna = d.get("lagna") or {}
        planets = d.get("planets") or {}
        panch = d.get("panchanga") or {}
        moment = d.get("moment") or {}
        tithi = (panch.get("tithi") or {}) if panch else {}
        nak = (panch.get("nakshatra") or {}) if panch else {}
        vaara = (panch.get("vaara") or {}) if panch else {}
        p_lines = "\n".join(
            f"- {name}: {info.get('sign_name')} (house {info.get('house')})"
            for name, info in planets.items())
        return f"""You are a Vedic astrologer reading the **chart of the moment** — the current sky cast for {moment.get('date')} {moment.get('time')} at {d.get('place') or 'this place'}. This is not a birth chart; it reflects the tenor of the present time itself (like a mundane/prasna snapshot). Read it in that spirit.

Ascendant now: {lagna.get('sign_name')} {round(lagna.get('degrees', 0), 1)}°.
Panchanga: {vaara.get('name', 'n/a')}, {tithi.get('name', 'n/a')}, {nak.get('name', 'n/a')} nakshatra. Running hora lord: {d.get('hora_lord') or 'n/a'}.
Planets now:
{p_lines}

Write a short ~220-word reading of the moment:
1. **The mood of now** — what the rising sign + Moon's placement + the panchanga invite, in a couple of sentences.
2. **What's favoured / what to be mindful of** — 2-3 practical notes on the kinds of activity the current planetary positions support or caution against right now.
3. **A gentle close** — one grounding line.
Reason from the placements given; cite them. This is a reflective snapshot of the present, not a personal fated prediction — avoid medical/legal/financial claims."""

    def _build_rectification_prompt(self, r: Dict[str, Any], name: str) -> str:
        """Explain, in plain terms, why the suggested birth time fits better than
        the entered one. The rectification (method, delta, before/after Moon &
        Lagna) is already computed — the model only interprets it, gently, and
        always frames it as experimental."""
        method = r.get("method_label", r.get("method", "a suddhi check"))
        entered = r.get("entered", {})
        suggested = r.get("suggested") or {}
        before = r.get("before", {}) or {}
        after = r.get("after", {}) or {}
        b_moon = before.get("moon") or {}
        a_moon = after.get("moon") or {}
        b_lagna = before.get("lagna") or {}
        a_lagna = after.get("lagna") or {}
        delta = r.get("delta_minutes")
        rectified = r.get("rectified")

        method_expl = {
            "Nakshatra Suddhi": "checks the Moon's birth star (nakshatra) against the star expected from the exact birth moment (the ishtakaal), nudging the time so they agree",
            "Lagna Suddhi": "checks the rising sign (Lagna) against the Moon and Maandi in the Rasi and Navamsa, nudging the time so the Lagna falls in a supportive relationship to them",
            "Janma Suddhi": "checks the classical birth-time gender indication (from the ishtakaal remainder), nudging the time so it agrees with the stated gender",
        }.get(method, "nudges the birth time so a classical consistency check is satisfied")

        if rectified:
            outcome = (f"The entered time {entered.get('tob')} did NOT satisfy the check; "
                       f"the nearest time that does is {suggested.get('tob')} "
                       f"(a shift of about {delta} minutes).")
        elif r.get("already_consistent"):
            outcome = f"The entered time {entered.get('tob')} already satisfies the check — no shift was needed."
        else:
            outcome = "No time within the search window satisfied the check."

        return f"""You are a warm, plain-spoken Vedic astrologer explaining an EXPERIMENTAL birth-time rectification to someone with little astrology background. Avoid jargon; when you must use a term (nakshatra, lagna, ishtakaal), explain it in a few words.

Birth-time rectification tries to refine an uncertain recorded birth time so the chart is internally consistent by a classical rule. This is a HEURISTIC — a suggestion to verify against real life events, never an authoritative correction.

Person: {name}
Method used: {method} — this {method_expl}.
{outcome}

What moved (fast-changing points, within the small time shift):
- Moon star: was {b_moon.get('nakshatra')} pada {b_moon.get('pada')} ({b_moon.get('sign_name')}) → now {a_moon.get('nakshatra')} pada {a_moon.get('pada')} ({a_moon.get('sign_name')})
- Rising sign (Lagna): was {b_lagna.get('sign_name')} (star {b_lagna.get('nakshatra')}) → now {a_lagna.get('sign_name')} (star {a_lagna.get('nakshatra')})

Write a short, clear explanation (about 200-250 words) with:
1. **What was checked** — one or two sentences on what this method looks at, in everyday language.
2. **Why the suggested time fits better** — explain what boundary the suggested time snapped to (which star/pada or rising-sign the shift aligns), using only the before/after facts above. If nothing changed, say the entered time already looked consistent.
3. **How to verify** — 2-3 gentle, concrete suggestions (compare against known timed life events, confirm the recorded time with family/records, try another method).

Be specific to the facts above — do not invent placements. Do NOT predict death, disease, or precise future dates. End with one short line reminding that rectification is experimental and the recorded time, where reliable, should be trusted first."""

    def _build_event_rectification_prompt(self, r: Dict[str, Any], name: str) -> str:
        """Explain why the event-matched birth time fits the supplied life events.
        The candidate scan, the winning time, and the per-event dasha/transit matches
        are already computed deterministically — the model only narrates them, gently,
        and always frames the result as experimental."""
        entered = r.get("entered", {})
        suggested = r.get("suggested") or {}
        rectified = r.get("rectified")
        delta = r.get("delta_minutes")
        confidence = r.get("confidence")
        window = r.get("window_minutes")
        before = r.get("before", {}) or {}
        after = r.get("after", {}) or {}
        b_lagna = (before.get("lagna") or {})
        a_lagna = (after.get("lagna") or {})

        lines = []
        for ev in r.get("events", []):
            matched = ev.get("matched") or []
            m = ("; ".join(matched)) if matched else "no strong dasha/transit link found"
            lines.append(
                f"- {ev.get('type')} on {ev.get('date')}: running Mahadasha "
                f"{ev.get('maha')} / Bhukti {ev.get('bhukti')} → {m} (score {ev.get('score')})"
            )
        event_block = "\n".join(lines) or "- (no events)"

        if rectified:
            outcome = (f"The entered time {entered.get('tob')} was refined to "
                       f"{suggested.get('tob')} (a shift of about {delta} minutes), which "
                       f"scored best against the events (fit ≈ {confidence}%). The rising sign "
                       f"moved from {b_lagna.get('sign_name')} to {a_lagna.get('sign_name')}.")
        else:
            outcome = (f"The entered time {entered.get('tob')} already scored best against the "
                       f"events (fit ≈ {confidence}%); no shift was suggested.")

        return f"""You are a warm, plain-spoken Vedic astrologer explaining an EXPERIMENTAL, event-based birth-time rectification to someone with little astrology background. Avoid jargon; when you must use a term (dasha, bhukti, lagna, transit), explain it in a few words.

Event-based rectification takes known dated life events and finds the birth time whose planetary *timing* (the Vimsottari dasha period running at each event, plus Jupiter/Saturn transits) best lines up with what classically signifies each event. It is a HEURISTIC that gets stronger with more events — a suggestion to verify, never an authoritative correction. It searched within ±{window} minutes of the entered time.

Person: {name}
{outcome}

Per-event timing matches the calculation found (already computed — trust these, do not re-derive):
{event_block}

Write a short, clear explanation (about 220-280 words) with:
1. **How this works** — one or two sentences on the idea (matching event dates to the planetary periods that rule those matters).
2. **Why this time fits the events** — walk through 2-3 of the strongest event matches above in everyday language (e.g. "your marriage fell in a period ruled by the planet governing marriage in your chart"). Use only the matches listed.
3. **How confident to be** — be honest that the fit is ≈{confidence}% and improves with more events; a low fit means the events don't strongly pin the time.
4. **How to verify** — 2-3 gentle suggestions (add more well-dated events, cross-check the recorded time with family/records, compare with the rule-based methods).

Be specific to the matches above — do not invent placements or events. Do NOT predict death, disease, or precise future dates. End with one short line reminding that this is experimental and the recorded time, where reliable, should be trusted first."""

    def _format_marriage_block(self, marriage: Dict[str, Any]) -> str:
        """A compact 7th-house summary for both partners (§2.6), for the couple
        prompt. Empty string when no workspace data was supplied."""
        sh = (marriage or {}).get("seventh_house") or {}
        if not sh:
            return ""

        def _one(label: str, m: Dict[str, Any]) -> str:
            if not m:
                return ""
            lord = m.get("seventh_lord_condition") or {}
            ka = m.get("karakas") or {}
            ven = ka.get("Venus") or {}
            jup = ka.get("Jupiter") or {}
            ul = m.get("upapada") or {}
            occ = ", ".join(o.get("name", "") for o in m.get("occupants", [])) or "none"
            return (
                f"--- {label} ---\n"
                f"7th house: {m.get('seventh_sign', '?')} (lord {m.get('seventh_lord', '?')})\n"
                f"7th lord {m.get('seventh_lord', '?')}: {lord.get('sign', '?')}, "
                f"house {lord.get('house', '?')}, {lord.get('dignity', '?')}"
                f"{', retrograde' if lord.get('retrograde') else ''}, "
                f"navamsa {lord.get('navamsa_sign', '?')}\n"
                f"Occupants of 7th: {occ}\n"
                f"Venus (kalatra karaka): {ven.get('sign', '?')}, house {ven.get('house', '?')}, "
                f"{ven.get('dignity', '?')}, navamsa {ven.get('navamsa_sign', '?')}\n"
                f"Jupiter (husband karaka): {jup.get('sign', '?')}, house {jup.get('house', '?')}, "
                f"{jup.get('dignity', '?')}, navamsa {jup.get('navamsa_sign', '?')}\n"
                f"Upapada (UL): {ul.get('sign', '?')} (lord {ul.get('lord', '?')})\n"
            )

        return ("\n=== 7TH-HOUSE (MARRIAGE) ANALYSIS ===\n"
                + _one("MALE", sh.get("male"))
                + _one("FEMALE", sh.get("female")))

    def _format_planets(self, planets: Dict[str, Any]) -> str:
        """Format planetary positions for prompt"""
        result = []
        for planet, data in planets.items():
            result.append(f"- {planet}: {data.get('sign_name', 'Unknown')}")
        return "\n".join(result)

    def _render_context_block(self, chart_data: Dict[str, Any], tool_mode: bool = False) -> str:
        """Render the chart context (no question) — reused by the single-shot prompt
        and as the system message for streaming/multi-turn chat. When `tool_mode` is
        set the closing instructions acknowledge the context may be partial and the
        model should fetch the rest via tools (rather than claiming it's complete)."""

        from datetime import datetime

        # Get current date for Dasha period identification
        current_date = datetime.now().strftime("%Y-%m-%d")

        # Extract key information
        lagna_info = chart_data.get("lagna", {})
        moon_info = chart_data.get("moon_sign", {})
        sun_info = chart_data.get("sun_sign", {})
        planets = chart_data.get("planetary_positions", {})
        birth_details = chart_data.get("birth_details", {})

        # Build comprehensive chart description
        # Birth-time reliability caveat: when the time is unknown/approximate the
        # Lagna and everything hanging off it (houses, vargas, bhava, dasha balance)
        # is unreliable, so the model must be told to lean Moon-referenced.
        accuracy = (chart_data.get("time_accuracy") or "exact").lower()
        accuracy_note = ""
        if accuracy == "unknown":
            accuracy_note = (
                "\n\n⚠ BIRTH TIME UNKNOWN. The Ascendant (Lagna), the house cusps, the "
                "divisional (varga) charts and the exact dasha balance are UNRELIABLE and "
                "must NOT be used for firm judgements. Read this chart **Moon-referenced** "
                "(Chandra Lagna) — planets counted from the Moon, Moon-sign and nakshatra "
                "based indications, Sun-sign — and clearly caveat anything that depends on "
                "the Lagna or houses.")
        elif accuracy == "approximate":
            accuracy_note = (
                "\n\n⚠ BIRTH TIME APPROXIMATE. The Lagna and house cusps may be off by a "
                "sign or houses may shift; treat house-based and varga details as tentative "
                "and prefer robust Moon- and Sun-referenced indications. Suggest birth-time "
                "rectification for precision.")

        chart_description = f"""TODAY'S DATE: {current_date}

Birth Details:
- Date of Birth: {birth_details.get('dob', 'Unknown')}
- Time of Birth: {birth_details.get('tob', 'Unknown')}
- Place of Birth: {birth_details.get('place', 'Unknown')}{accuracy_note}

Lagna (Ascendant):
- Sign: {lagna_info.get('sign_name', 'Unknown')} (House #{lagna_info.get('house', 'Unknown')})
- Nakshatra: {lagna_info.get('nakshatra', 'Unknown')} Pada {lagna_info.get('nakshatra_pada', 'Unknown')}
- Degrees: {lagna_info.get('degrees', 'Unknown')}°

Moon Sign (Chandra Rasi):
- Sign: {moon_info.get('sign_name', 'Unknown')} (Rasi #{moon_info.get('rasi', 'Unknown')})
- Nakshatra: {moon_info.get('nakshatra', 'Unknown')} Pada {moon_info.get('nakshatra_pada', 'Unknown')}

Sun Sign (Surya Rasi):
- Sign: {sun_info.get('sign_name', 'Unknown')} (Rasi #{sun_info.get('rasi', 'Unknown')})
- Nakshatra: {sun_info.get('nakshatra', 'Unknown')} Pada {sun_info.get('nakshatra_pada', 'Unknown')}

Planetary Positions (All 9 Grahas):"""

        # Add planetary positions with nakshatras
        for planet, data in planets.items():
            nakshatra_info = ""
            if data.get('nakshatra'):
                nakshatra_info = f", Nakshatra: {data.get('nakshatra', 'Unknown')} Pada {data.get('nakshatra_pada', 'Unknown')}"
            chart_description += f"\n- {planet}: {data.get('sign_name', 'Unknown')} sign (Rasi #{data.get('rasi', 'Unknown')}), {data.get('degrees', 0):.2f}°{nakshatra_info}"

        # Divisional charts (vargas) — compact one line per chart for token economy
        vargas = chart_data.get("vargas", [])
        if vargas:
            chart_description += "\n\nDivisional Charts (Vargas):"
            for v in vargas:
                lagna_sign = v.get("lagna", {}).get("sign_name", "?")
                placements = ", ".join(
                    f"{name} {p.get('sign_name', '?')}"
                    for name, p in v.get("planets", {}).items()
                )
                chart_description += (
                    f"\n- {v.get('code', '?')} {v.get('name', '')} "
                    f"({v.get('significance', '')}): Asc {lagna_sign}; {placements}"
                )

        # Add Dasha information
        current_dasha = chart_data.get("current_dasha", {})
        next_dasha = chart_data.get("next_dasha", {})
        current_bhukthi = chart_data.get("current_bhukthi", {})
        dasha_tree = chart_data.get("dasha_tree", [])

        if dasha_tree:
            # Preferred: the precise running chain Maha -> Bhukti -> Antara -> Sookshma
            chart_description += f"\n\nCurrently Active Vimsottari Dasha Chain (as of {current_date}):"
            for node in dasha_tree:
                chart_description += (
                    f"\n- {node.get('level_name', 'Level')}: {node.get('lord', 'Unknown')} "
                    f"({node.get('start_date', '?')} to {node.get('end_date', '?')})"
                )
        elif current_dasha:
            chart_description += f"\n\nCurrent Dasha (Vimsottari):"
            chart_description += f"\n- Maha Dasha: {current_dasha.get('lord', 'Unknown')} ({current_dasha.get('start_date', 'Unknown')} to {current_dasha.get('end_date', 'Unknown')})"
            chart_description += f"\n- Duration: {current_dasha.get('duration_years', 0)} years"

        if current_bhukthi and current_bhukthi.get('periods'):
            chart_description += f"\n\nAll Sub-periods (Antar Dasha / Bhukti) within {current_dasha.get('lord', 'Unknown')} Maha Dasha:"
            # Show ALL sub-periods so LLM can identify which one is current
            for period in current_bhukthi.get('periods', []):
                chart_description += f"\n- {period.get('lord', 'Unknown')}: {period.get('start_date', 'Unknown')} to {period.get('end_date', 'Unknown')} ({period.get('duration_months', 0)} months)"

        if next_dasha:
            chart_description += f"\n\nNext Maha Dasha:"
            chart_description += f"\n- {next_dasha.get('lord', 'Unknown')} starting {next_dasha.get('start_date', 'Unknown')}"

        # Yogas present in the chart (name + short description; token-budgeted)
        yogas = chart_data.get("yogas", [])
        if yogas:
            chart_description += f"\n\nYogas Present in the Chart ({len(yogas)}):"
            for y in yogas:
                desc = (y.get("description") or "").strip()
                if len(desc) > 140:
                    desc = desc[:137].rstrip() + "..."
                chart_description += f"\n- {y.get('name', 'Unknown')}" + (f": {desc}" if desc else "")

        # Doshas — list present ones with detail, name-only for absent
        doshas = chart_data.get("doshas", [])
        if doshas:
            present = [d for d in doshas if d.get("present")]
            absent = [d for d in doshas if not d.get("present")]
            chart_description += f"\n\nDoshas:"
            if present:
                chart_description += "\n- Present:"
                for d in present:
                    desc = (d.get("description") or "").strip()
                    if len(desc) > 140:
                        desc = desc[:137].rstrip() + "..."
                    chart_description += f"\n  • {d.get('name', 'Unknown')}" + (f": {desc}" if desc else "")
            else:
                chart_description += "\n- Present: none"
            if absent:
                chart_description += "\n- Absent: " + ", ".join(d.get("name", "?") for d in absent)

        # Current transits (Gochara) over the natal chart
        transits = chart_data.get("transits", {})
        t_planets = transits.get("planets", {}) if isinstance(transits, dict) else {}
        if t_planets:
            chart_description += f"\n\nCurrent Transits (Gochara) as of {transits.get('transit_date', current_date)}:"
            chart_description += "\n(house counted from natal Lagna / natal Moon)"
            for name, p in t_planets.items():
                retro = " [Retrograde]" if p.get("retrograde") else ""
                chart_description += (
                    f"\n- {name}: {p.get('sign_name', '?')} {p.get('degrees', 0):.1f}° "
                    f"({p.get('nakshatra', '?')}), house {p.get('house_from_lagna', '?')} "
                    f"from Lagna / {p.get('house_from_moon', '?')} from Moon{retro}"
                )
            for u in transits.get("upcoming", []):
                chart_description += (
                    f"\n- Upcoming: {u.get('planet', '?')} enters {u.get('to_sign', '?')} "
                    f"(from {u.get('from_sign', '?')}) on {u.get('date', '?')}"
                )

        # Ashtakavarga — Sarva (combined) bindus per sign (higher = more supportive)
        ashtakavarga = chart_data.get("ashtakavarga", {})
        sav = ashtakavarga.get("sarva") if isinstance(ashtakavarga, dict) else None
        if sav:
            signs = ashtakavarga.get("signs", [])
            pairs = ", ".join(
                f"{signs[i] if i < len(signs) else i}: {v}" for i, v in enumerate(sav)
            )
            chart_description += (
                f"\n\nSarva Ashtakavarga (bindus per sign, total "
                f"{ashtakavarga.get('sarva_total', sum(sav))}/337):\n- {pairs}"
            )

        # Shadbala — per-planet strength (ratio >= 1.0 means sufficiently strong)
        shadbala = chart_data.get("shadbala", [])
        if shadbala:
            chart_description += "\n\nShadbala (planetary strength, rupas):"
            for p in shadbala:
                flag = "" if p.get("sufficient") else " (below required)"
                chart_description += (
                    f"\n- {p.get('planet', '?')}: {p.get('total_rupa', '?')} rupa, "
                    f"ratio {p.get('strength_ratio', '?')}, rank {p.get('rank', '?')}{flag}"
                )

        # Graha drishti (aspects) — one compact line per aspecting graha, with the
        # Parashari sphuta strength (%) so partial aspects can be weighed.
        aspects = chart_data.get("aspects", {})
        a_planets = aspects.get("planets", []) if isinstance(aspects, dict) else []
        if a_planets:
            chart_description += "\n\nGraha Drishti (aspects; strength 0-100%, 100 = full):"
            for a in a_planets:
                houses = ", ".join(
                    f"{h['house']}({h['strength']}%)" for h in a.get("aspects_houses", [])
                )
                pl = ", ".join(
                    f"{p.get('planet', '?')} {p.get('strength', 0)}%"
                    for p in a.get("aspects_planets", [])
                ) or "none"
                special = " [special aspects]" if a.get("special_aspect") else ""
                chart_description += (
                    f"\n- {a.get('planet', '?')}{special}: houses {houses or 'none'}; "
                    f"planets {pl}"
                )
                rasi_pl = a.get("rasi_drishti_planets", [])
                if rasi_pl:
                    chart_description += f"; rasi-drishti on {', '.join(rasi_pl)}"

        # Arudha padas — AL (perceived image/status), UL (spouse), A2..A11, each the
        # sign the arudha occupies. One compact line.
        arudhas = chart_data.get("arudhas", {})
        ar_padas = arudhas.get("padas", []) if isinstance(arudhas, dict) else []
        if ar_padas:
            items = ", ".join(
                f"{p.get('short', '?')} {p.get('sign_name', '?')}" for p in ar_padas
            )
            chart_description += (
                "\n\nArudha Padas (AL=perceived image/status, UL=spouse; sign each "
                f"arudha occupies): {items}"
            )

        # Planet conditions ("flags") — the classical point-states that modify how a
        # planet delivers results (combust/vargottama/gandanta/…). One line each.
        conditions = chart_data.get("conditions", {})
        cond_flagged = conditions.get("flagged", []) if isinstance(conditions, dict) else []
        if cond_flagged:
            chart_description += (
                "\n\nPlanet Conditions (classical flags; benefic=strengthening, "
                "challenging=straining, neutral=nuance):"
            )
            for p in cond_flagged:
                fl = ", ".join(
                    f"{f.get('label', '?')}"
                    + (f" with {f['partner']}" if f.get("partner") else "")
                    + f" [{f.get('tone', '?')}]"
                    for f in p.get("flags", [])
                )
                chart_description += (
                    f"\n- {p.get('planet', '?')} ({p.get('sign_name', '?')}, "
                    f"house {p.get('house', '?')}): {fl}"
                )

        # Avasthas (planetary states) — Baladi / Jagradadi / Deeptadi per graha,
        # a vitality/mood nuance complementing Shadbala. One compact line each.
        avasthas = chart_data.get("avasthas", [])
        if avasthas:
            chart_description += (
                "\n\nAvasthas (planetary states — Baladi age / Jagradadi wakefulness "
                "/ Deeptadi temperament):"
            )
            for a in avasthas:
                chart_description += (
                    f"\n- {a.get('planet', '?')}: {a.get('baladi', '?')} / "
                    f"{a.get('jagradadi', '?')} / {a.get('deeptadi', '?')} "
                    f"[{a.get('tone', '?')}]"
                )

        # Friendships — house-lord placements + any Parivartana. The compound
        # matrix is a visual reference, so only the wiring is seeded here.
        friendships = chart_data.get("friendships", {})
        if isinstance(friendships, dict) and friendships.get("house_lords"):
            chart_description += "\n\nHouse-lord placements (lord of house → house it occupies):"
            for h in friendships["house_lords"]:
                chart_description += f"\n- L{h.get('house')} in H{h.get('lord_house')} ({h.get('lord')})"
            pari = friendships.get("parivartana", [])
            if pari:
                chart_description += "\nParivartana (mutual exchange): " + "; ".join(
                    f"{p['planets'][0]}↔{p['planets'][1]} (H{p['houses'][0]}/H{p['houses'][1]})"
                    for p in pari)

        # Nakshatra (birth star) profile — the Moon's janma-nakshatra attributes.
        nak = chart_data.get("nakshatra", {})
        if isinstance(nak, dict) and nak.get("name"):
            chart_description += (
                f"\n\nJanma-nakshatra (birth star): {nak.get('name')} pada {nak.get('pada')}, "
                f"lord {nak.get('lord')}, deity {nak.get('deity')}; "
                f"gana {nak.get('gana')}, yoni {nak.get('yoni')}, nadi {nak.get('nadi')}, "
                f"guna {nak.get('guna')}, varna {nak.get('varna')}. Theme: {nak.get('theme')}."
            )

        # Gochara-phala — Moon-referenced transit verdicts (with vedha).
        gp = chart_data.get("gochara_phala", {})
        if isinstance(gp, dict) and gp.get("results"):
            chart_description += (
                f"\n\nGochara-phala (Moon-referenced transits, Moon in {gp.get('moon_sign')}):"
            )
            for r in gp["results"]:
                blocked = (f", blocked by {', '.join(r['obstructed_by'])}"
                           if r.get("obstructed_by") else "")
                chart_description += (
                    f"\n- {r.get('planet')}: {r.get('house_from_moon')}th from Moon "
                    f"→ {r.get('verdict')}{blocked}"
                )

        # ── Chakras (§2.7) — only present when the section is seeded ──────
        sbc = chart_data.get("sarvatobhadra", {})
        if isinstance(sbc, dict) and sbc.get("findings"):
            chart_description += (
                f"\n\nSarvatobhadra Chakra (transits on the all-directions star grid, "
                f"{sbc.get('transit_date')}):"
            )
            for f in sbc["findings"]:
                kind = ("sits on" if f.get("kind") == "occupation" else "casts vedha on")
                chart_description += (
                    f"\n- {f.get('planet')} {kind} {f.get('on')} ({f.get('tone')})"
                )

        kota = chart_data.get("kota", {})
        if isinstance(kota, dict) and kota.get("rings"):
            chart_description += (
                f"\n\nKota Chakra (the fort — four enclosures from the birth star "
                f"{kota.get('birth_star')}; malefics reaching the inner rings press on it. "
                f"Kota Swami/defender: {kota.get('kota_swami')}, "
                f"Kota Paala/guard: {kota.get('kota_paala')}):"
            )
            for r in kota["rings"]:
                chart_description += (
                    f"\n- {r.get('ring')}: malefics {', '.join(r['malefics']) or 'none'}"
                    f"; benefics {', '.join(r['benefics']) or 'none'}"
                )

        kaala = chart_data.get("kaala", {})
        if isinstance(kaala, dict) and kaala.get("directions"):
            chart_description += (
                f"\n\nKaala Chakra (wheel of DIRECTIONS, from the Sun's star "
                f"{kaala.get('base_star')} — each spoke is a compass direction):"
            )
            for d in kaala["directions"]:
                who = ", ".join(d["malefics"] + d["benefics"]) or "no grahas"
                chart_description += (
                    f"\n- {d.get('direction')}: {d.get('verdict')} ({who})"
                )
            chart_description += (
                f"\n- Favourable: {', '.join(kaala.get('favourable') or []) or 'none'}"
                f"; best avoided: {', '.join(kaala.get('avoid') or []) or 'none'}"
            )

        trip = chart_data.get("tripataki", {})
        if isinstance(trip, dict) and trip.get("vedha"):
            chart_description += (
                f"\n\nTripataki Chakra (vedha/obstruction on the Moon and Lagna; "
                f"Lagna {trip.get('lagna')}, Moon {trip.get('moon')}):"
            )
            for v in trip["vedha"]:
                by = ", ".join(v.get("obstructed_by") or []) or "nothing — unobstructed"
                chart_description += (
                    f"\n- {v.get('target')} in {v.get('sign')}: {v.get('verdict')} — "
                    f"obstructed by {by}"
                )

        header = ("Below is birth chart data for this person, calculated using precise "
                  f"astronomical calculations from the {SITE_NAME} Vedic astrology software. "
                  "This is REAL, VERIFIED CHART DATA - not hypothetical."
                  if tool_mode else
                  "Below is the COMPLETE BIRTH CHART DATA for this person, calculated "
                  f"using precise astronomical calculations from the {SITE_NAME} Vedic "
                  "astrology software. This is REAL, VERIFIED CHART DATA - not "
                  "hypothetical.")
        title = "=== BIRTH CHART ===" if tool_mode else "=== COMPLETE BIRTH CHART ==="
        closing = (
            "Give practical, actionable guidance. Some sections may be omitted above — "
            "call the available tools to fetch any additional data you need rather than "
            "asking the user."
            if tool_mode else
            "Give practical, actionable guidance. Do NOT ask for more information — you "
            "have the complete chart and today's date.")

        context_block = f"""{header}

{title}

{chart_description}

=== END OF CHART DATA ===

IMPORTANT INSTRUCTIONS:
1. TODAY'S DATE is {current_date} - use it to determine which Dasha/sub-period is CURRENTLY active.
2. The planetary positions, signs, houses, nakshatras, divisional charts (vargas) and Dasha periods above were calculated accurately from the exact birth time and location.
3. Be specific to THIS chart: cite the placements/dashas/yogas behind your reasoning rather than giving generic horoscope text.
4. {closing}"""

        return context_block
