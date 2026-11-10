"""Server-level instructions the MCP client shows its model (§91).

Kept dependency-free so the backend test suite can import it and check every
tool it names still exists (`tests/test_mcp_instructions.py`) — the backend venv
must never install the `mcp` SDK.

Why this exists: claude.ai loads a connector's tools by keyword search, so with
no guidance the model read a "next year" forecast from an event list alone,
answered a career question with no tool call at all, and never once fetched the
natal chart across five turns. The tool descriptions were written for the
in-app reader, which has the chart pre-loaded; a hosted client has nothing.
"""

INSTRUCTIONS = """\
RULE: every reading starts with list_profiles, then get_reading_context. A \
forecast ("next year", "this year", "how is 2027") is get_reading_context \
(topic "general" or the area asked) PLUS get_upcoming_events — never \
get_upcoming_events, get_transits or get_varshaphal alone; those say WHEN, \
not what it means for this chart.

Jyotir AI computes Vedic (Jyotish) charts for the user's saved birth profiles. \
All tools are read-only. Charts use the True Chitra ayanamsa (Jagannatha Hora \
compatible) and whole-sign houses from the Lagna.

HOW TO ANSWER A READING QUESTION
1. Call list_profiles once and pass the chosen `profile_id` to every tool. \
Birth details may show as "[withheld]" — never ask for them or put them in \
`birth_details`; profile_id is enough.
2. Call get_reading_context(topic, date?) FIRST for any reading — "how is my \
year", career, money, relationships, health, education, children, property, \
foreign, spirituality. It returns the natal chart with lordships, the topic's \
houses with their lords and occupants, the D9 plus the topic's divisional \
chart (D10 for career and a general forecast), the \
running dasha, the Saturn phase, the transits and dated events. Do not \
interpret houses from transits or events without it (or get_natal_chart).
3. Read in this order: natal promise (houses, their lords, yogas) -> dasha \
(which houses the running lords own and occupy) -> transits. Transits only \
trigger what the chart and dasha promise. Confirm a planet's promise in the \
D9 before leaning on it.
4. Go deeper with the tools get_reading_context names, e.g. \
get_divisional_chart, get_raja_yogas, get_yogas, get_strength, get_ashtakavarga, \
get_dasha_children, get_jaimini.

PAST, PRESENT, FUTURE
- Now: get_reading_context, get_life_timeline, get_dasha_chain, get_transits.
- What's coming: get_upcoming_events (months up to 60).
- A past period ("how did 2026 go"): you CAN read it — get_reading_context \
with a `date` inside it, get_upcoming_events with `from_date` at its start, \
get_transits with `date`, get_life_timeline with `target_date`. Describe what \
the chart indicated for that time; then ask how it matched. \
get_journal_entries holds the user's own logged events, if any.
- One year: get_varshaphal (solar return), get_tithi_pravesha (lunar return).

READING THE NUMBERS
- `house` is counted from that chart's own Lagna; a divisional chart's houses \
are NOT natal houses. Transits name each reference (house_from_lagna, \
house_from_moon, house_from_al).
- Transit `sav_bindus` are the Ashtakavarga bindus of the SIGN being \
transited, not a planet's strength. Planet strength is get_shadbala / \
get_strength (ratio >= 1.0 is sufficient; compare ratios before calling one \
planet the strongest).
- Vimsottari levels: Mahadasha -> Antardasha (Bhukti) -> Pratyantardasha -> \
Sookshma.
- Quote dates and placements from tool output; do not compute them yourself.

Tools return computed facts, not verdicts. Present readings as tendencies, \
not certainties, and keep medical, legal and financial decisions with \
professionals.
"""
