"""
Tool registry for the agentic ("tool-call") Ask-AI mode.

Each tool is a thin, provider-neutral wrapper over an `AstrologyCompute` static.
The model is shown only the *free* parameters of each tool (e.g. `varga_factor`);
the birth details (dob/tob/place/lat/lon/tz) and the ayanamsa are **injected by
the backend at dispatch time**, never supplied by the model — so a question can
never be redirected to a different person or ayanamsa.

Two consumers:
  - `tool_specs()` returns provider-neutral specs (name/description/JSON-schema of
    params). `llm_service` formats these into OpenAI `tools`, Gemini
    `function_declarations`, or the prompt-based JSON-protocol instructions.
  - `dispatch(name, model_args, birth_details, ayanamsa)` validates the name,
    coerces args, runs the handler, and returns a JSON-serialisable result dict.

Result shapes deliberately mirror the per-section shapes assembled by
`chart_context.build_chart_context`, so a section reads the same whether it was
pre-seeded into the prompt or fetched on demand via a tool.
"""
from typing import Any, Callable, Dict, List, Optional

from astrology import AstrologyCompute, DEFAULT_AYANAMSA, SUPPORTED_VARGAS
from chart_context import _running_dasha_chain


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _args(birth_details: Dict[str, Any]) -> Dict[str, Any]:
    """Map a BirthDetails dict onto the dob/tob/place/lat/lon/tz kwargs every
    AstrologyCompute method takes."""
    return {
        "dob": birth_details["dob"],
        "tob": birth_details["tob"],
        "place": birth_details.get("place", ""),
        "lat": birth_details.get("latitude"),
        "lon": birth_details.get("longitude"),
        "tz": birth_details.get("timezone"),
    }


class ToolError(Exception):
    """Raised for an unknown tool name or invalid arguments."""


# --------------------------------------------------------------------------- #
# Handlers — each returns a JSON-serialisable dict
# --------------------------------------------------------------------------- #
def _natal_chart(bd, ayanamsa, **_):
    args = _args(bd)
    chart = AstrologyCompute.calculate_birth_chart(ayanamsa=ayanamsa, **args)
    if "error" in chart:
        return chart
    d1 = chart.get("d1_chart", {})
    moon = d1.get("Moon", {})
    sun = d1.get("Sun", {})
    return {
        "lagna": chart.get("lagna", {}),
        "moon_sign": {
            "sign_name": moon.get("sign_name", "Unknown"),
            "rasi": moon.get("rasi", 0),
            "nakshatra": moon.get("nakshatra", "Unknown"),
            "nakshatra_pada": moon.get("nakshatra_pada", 0),
        },
        "sun_sign": {
            "sign_name": sun.get("sign_name", "Unknown"),
            "rasi": sun.get("rasi", 0),
            "nakshatra": sun.get("nakshatra", "Unknown"),
            "nakshatra_pada": sun.get("nakshatra_pada", 0),
        },
        "planetary_positions": d1,
    }


def _dasha_chain(bd, ayanamsa, dhasa_type: str = "vimsottari", **_):
    args = _args(bd)
    dashas = AstrologyCompute.get_dashas(dhasa_type=dhasa_type, **args)
    if dashas.get("status") == "failed":
        return dashas
    result = {
        "current_dasha": dashas.get("current_dasha", {}),
        "next_dasha": dashas.get("next_dasha", {}),
        "current_bhukthi": dashas.get("current_bhukthi", {}),
    }
    # The precise running Maha -> Bhukti -> Antara -> Sookshma chain (Vimsottari).
    if dhasa_type == "vimsottari":
        result["dasha_tree"] = _running_dasha_chain(args, dashas)
    return result


def _dasha_children(bd, ayanamsa, lords_path: Optional[List[str]] = None, **_):
    if not lords_path or not isinstance(lords_path, list):
        raise ToolError("get_dasha_children requires a non-empty 'lords_path' list "
                        "of dasha lords from Maha downward, e.g. ['Venus', 'Sun'].")
    args = _args(bd)
    res = AstrologyCompute.get_dasha_children(lords_path=lords_path, **args)
    if res.get("status") != "success":
        return res
    return {"lords_path": lords_path, "children": res.get("children", [])}


def _yogas(bd, ayanamsa, **_):
    y = AstrologyCompute.get_yogas(ayanamsa=ayanamsa, **_args(bd))
    return {"yogas": y.get("yogas", []) if y.get("status") == "success" else []}


def _doshas(bd, ayanamsa, **_):
    d = AstrologyCompute.get_doshas(ayanamsa=ayanamsa, **_args(bd))
    return {"doshas": d.get("doshas", []) if d.get("status") == "success" else []}


def _transits(bd, ayanamsa, **_):
    t = AstrologyCompute.get_transits(ayanamsa=ayanamsa, **_args(bd))
    if t.get("status") != "success":
        return t
    return {
        "transit_date": t.get("transit_date"),
        "natal": t.get("natal", {}),
        "planets": t.get("planets", {}),
        "upcoming": t.get("upcoming", []),
    }


def _ashtakavarga(bd, ayanamsa, **_):
    av = AstrologyCompute.get_ashtakavarga(ayanamsa=ayanamsa, **_args(bd))
    if av.get("status") != "success":
        return av
    # Sarva is the high-signal summary; Bhinna is large, so omit it.
    return {
        "signs": av.get("signs", []),
        "sarva": av.get("sarva", []),
        "sarva_total": av.get("sarva_total"),
    }


def _shadbala(bd, ayanamsa, **_):
    sb = AstrologyCompute.get_shadbala(ayanamsa=ayanamsa, **_args(bd))
    if sb.get("status") != "success":
        return sb
    # Per-planet totals/ratio/rank only (drop the six raw components for economy).
    return {"shadbala": [
        {"planet": p["planet"], "total_rupa": p["total_rupa"],
         "strength_ratio": p["strength_ratio"], "rank": p["rank"],
         "sufficient": p["sufficient"]}
        for p in sb.get("planets", [])
    ]}


def _chart_details(bd, ayanamsa, **_):
    return AstrologyCompute.get_chart_details(ayanamsa=ayanamsa, **_args(bd))


def _aspects(bd, ayanamsa, **_):
    a = AstrologyCompute.get_aspects(ayanamsa=ayanamsa, **_args(bd))
    if a.get("status") != "success":
        return a
    return {"planets": a.get("planets", []), "note": a.get("note")}


def _divisional_chart(bd, ayanamsa, varga_factor: Optional[int] = None, **_):
    try:
        factor = int(varga_factor)
    except (TypeError, ValueError):
        raise ToolError("get_divisional_chart requires an integer 'varga_factor'.")
    if factor == 1:
        raise ToolError("For the D1/Rasi (natal) chart use get_natal_chart, not "
                        "get_divisional_chart.")
    if factor not in SUPPORTED_VARGAS:
        supported = ", ".join(str(f) for f in sorted(SUPPORTED_VARGAS) if f != 1)
        raise ToolError(f"varga_factor {factor} is not supported. "
                        f"Choose one of: {supported}.")
    vc = AstrologyCompute.calculate_divisional_chart(
        varga_factor=factor, ayanamsa=ayanamsa, **_args(bd))
    if vc.get("status") != "success":
        return vc
    return {
        "varga": vc.get("varga"),
        "code": vc.get("code"),
        "name": vc.get("name"),
        "significance": vc.get("significance"),
        "lagna": vc.get("lagna", {}),
        "planets": vc.get("planets", {}),
    }


def _panchanga(bd, ayanamsa, date: Optional[str] = None, **_):
    a = _args(bd)
    return AstrologyCompute.get_panchanga(
        date=date, place=a["place"], lat=a["lat"], lon=a["lon"], tz=a["tz"])


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_EMPTY_PARAMS = {"type": "object", "properties": {}, "required": []}

_VARGA_DESC = "; ".join(
    f"{f}={SUPPORTED_VARGAS[f][0]} ({SUPPORTED_VARGAS[f][2]})"
    for f in sorted(SUPPORTED_VARGAS) if f != 1
)


class _Tool:
    __slots__ = ("name", "description", "parameters", "handler")

    def __init__(self, name: str, description: str,
                 parameters: Dict[str, Any], handler: Callable):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.handler = handler


TOOLS: Dict[str, _Tool] = {t.name: t for t in [
    _Tool(
        "get_natal_chart",
        "Natal (D1/Rasi) chart: Lagna, Sun & Moon signs/nakshatras, and the "
        "rasi/degrees/nakshatra of all nine grahas. Call this first if the natal "
        "placements were not already provided.",
        _EMPTY_PARAMS, _natal_chart,
    ),
    _Tool(
        "get_dasha_chain",
        "The currently-running dasha periods. For Vimsottari this returns the full "
        "active chain Maha -> Bhukti -> Antara -> Sookshma plus the next Maha dasha. "
        "Use for timing events.",
        {"type": "object", "properties": {
            "dhasa_type": {"type": "string", "default": "vimsottari",
                           "description": "Dasha system; usually 'vimsottari'."}},
         "required": []},
        _dasha_chain,
    ),
    _Tool(
        "get_dasha_children",
        "Drill into the sub-periods of a specific Vimsottari node. Provide the lords "
        "from Maha downward, e.g. ['Venus'] for Venus's Bhuktis, or ['Venus','Sun'] "
        "for the Antaras within Venus-Sun. Use to time events more precisely than the "
        "running chain.",
        {"type": "object", "properties": {
            "lords_path": {"type": "array", "items": {"type": "string"},
                           "description": "Dasha lords from Maha downward."}},
         "required": ["lords_path"]},
        _dasha_children,
    ),
    _Tool(
        "get_yogas",
        "Named yogas present in the Rasi chart (name + description). Use for "
        "personality, strengths, and special combinations.",
        _EMPTY_PARAMS, _yogas,
    ),
    _Tool(
        "get_doshas",
        "Common doshas with present/absent status and descriptions (e.g. Mangal/"
        "Kuja, Kaal Sarpa, Sade Sati). Use for marriage, obstacles, afflictions.",
        _EMPTY_PARAMS, _doshas,
    ),
    _Tool(
        "get_transits",
        "Current planetary transits (Gochara) over the natal chart: each planet's "
        "sign/degree/nakshatra, house from natal Lagna and Moon, retrograde flag, "
        "plus upcoming sign ingresses. Use for current/near-future timing.",
        _EMPTY_PARAMS, _transits,
    ),
    _Tool(
        "get_ashtakavarga",
        "Sarva Ashtakavarga: combined benefic bindus per sign (higher = more "
        "supportive), with the total out of 337. Use to gauge which signs/houses "
        "are strong.",
        _EMPTY_PARAMS, _ashtakavarga,
    ),
    _Tool(
        "get_shadbala",
        "Shadbala planetary strength: total rupas, strength ratio (>=1.0 is "
        "sufficient) and rank per planet. Use to judge which planets can deliver "
        "their results.",
        _EMPTY_PARAMS, _shadbala,
    ),
    _Tool(
        "get_chart_details",
        "Additional natal chart details (house-by-house breakdown and related "
        "specifics). Use when a question needs house-level detail beyond the natal "
        "placements.",
        _EMPTY_PARAMS, _chart_details,
    ),
    _Tool(
        "get_aspects",
        "Graha drishti (planetary aspects): for each graha, the houses and planets "
        "it aspects (incl. the Mars 4/8, Jupiter 5/9, Saturn 3/10 special aspects), "
        "the planets it aspects by rasi (sign) drishti, and a 0-100% strength per "
        "graha->planet aspect (100 = full). Use to judge influences on a planet/house.",
        _EMPTY_PARAMS, _aspects,
    ),
    _Tool(
        "get_divisional_chart",
        "A divisional (varga) chart for a life area, with its Lagna and planet "
        "placements. Pick the varga_factor by topic — " + _VARGA_DESC + ".",
        {"type": "object", "properties": {
            "varga_factor": {"type": "integer",
                             "enum": [f for f in sorted(SUPPORTED_VARGAS) if f != 1],
                             "description": "Divisional factor, e.g. 9 for Navamsa "
                                            "(marriage), 10 for Dasamsa (career)."}},
         "required": ["varga_factor"]},
        _divisional_chart,
    ),
    _Tool(
        "get_panchanga",
        "Daily almanac (panchanga) for a date at the birth place: tithi, vara, "
        "nakshatra, yoga, karana and key timings. Defaults to today if no date is "
        "given. Use for muhurta / auspicious-timing questions.",
        {"type": "object", "properties": {
            "date": {"type": "string",
                     "description": "Date as YYYY-MM-DD; defaults to today."}},
         "required": []},
        _panchanga,
    ),
]}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
# Map each toggleable context section to the tool that fetches it on demand.
# Used by the tri-state (seed / tool / off) control in "Smart lookup" mode: a
# section set to "tool" exposes its tool; "seed" or "off" do not (seeded data is
# already in the prompt, off means excluded entirely).
SECTION_TOOL: Dict[str, str] = {
    "dasha_tree": "get_dasha_chain",
    "yogas": "get_yogas",
    "doshas": "get_doshas",
    "transits": "get_transits",
    "ashtakavarga": "get_ashtakavarga",
    "shadbala": "get_shadbala",
    "aspects": "get_aspects",
}

# Tools with no section toggle — always available in tool mode so the model can
# fetch the natal base, drill dashas, pull a varga, or read the panchanga.
ALWAYS_TOOLS: List[str] = [
    "get_natal_chart", "get_chart_details", "get_dasha_children",
    "get_divisional_chart", "get_panchanga",
]


def tool_names_for_sections(sections: Optional[Dict[str, Any]]) -> Optional[List[str]]:
    """Resolve which tools to expose in Smart-lookup mode from the tri-state
    `sections` map (values "seed" | "tool" | "off", or legacy bools).

    Returns None when `sections` is None (legacy/unspecified → expose every tool,
    the original behaviour). Otherwise: the always-on tools, plus the tool for any
    section explicitly set to "tool" (a section unspecified in the map also gets
    its tool, so the model is never blind to data the user didn't pin)."""
    if sections is None:
        return None
    names = list(ALWAYS_TOOLS)
    for sec, tool in SECTION_TOOL.items():
        v = sections.get(sec, "tool")
        if v is True:
            state = "seed"
        elif v is False:
            state = "off"
        else:
            state = v if v in ("seed", "tool", "off") else "tool"
        if state == "tool" and tool not in names:
            names.append(tool)
    return names


def tool_specs(names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Provider-neutral specs. `names` optionally restricts/orders the set (e.g.
    to expose only the sections not already seeded into the prompt)."""
    selected = names if names is not None else list(TOOLS)
    return [{
        "name": TOOLS[n].name,
        "description": TOOLS[n].description,
        "parameters": TOOLS[n].parameters,
    } for n in selected if n in TOOLS]


# Friendly display metadata for the human-facing "AI capabilities" page. The
# model never sees `label`/`category`; they only shape how the catalog reads to
# a person. Tools are listed here in the order they should appear.
_DISPLAY: Dict[str, Dict[str, str]] = {
    "get_natal_chart":      {"label": "Natal chart",            "category": "Core chart"},
    "get_chart_details":    {"label": "House-by-house detail",  "category": "Core chart"},
    "get_aspects":          {"label": "Graha drishti (aspects)", "category": "Core chart"},
    "get_divisional_chart": {"label": "Divisional (varga) charts", "category": "Core chart"},
    "get_dasha_chain":      {"label": "Running dasha periods",  "category": "Timing"},
    "get_dasha_children":   {"label": "Dasha sub-periods",      "category": "Timing"},
    "get_transits":         {"label": "Current transits (Gochara)", "category": "Timing"},
    "get_panchanga":        {"label": "Panchanga almanac",      "category": "Timing"},
    "get_yogas":            {"label": "Yogas",                  "category": "Strengths & afflictions"},
    "get_doshas":           {"label": "Doshas",                 "category": "Strengths & afflictions"},
    "get_ashtakavarga":     {"label": "Ashtakavarga",          "category": "Strengths & afflictions"},
    "get_shadbala":         {"label": "Shadbala strength",      "category": "Strengths & afflictions"},
}


def tool_catalog() -> List[Dict[str, Any]]:
    """Human-facing catalog of every tool the model may call, each with a
    friendly label, a category for grouping, the model-facing description, and
    its raw JSON-schema parameters. Backs the read-only /api/ai/tools endpoint.
    Ordered by `_DISPLAY`, with any tool missing from it appended at the end."""
    ordered = list(_DISPLAY) + [n for n in TOOLS if n not in _DISPLAY]
    out: List[Dict[str, Any]] = []
    for n in ordered:
        t = TOOLS.get(n)
        if t is None:
            continue
        meta = _DISPLAY.get(n, {})
        out.append({
            "name": t.name,
            "label": meta.get("label", n.replace("get_", "").replace("_", " ").title()),
            "category": meta.get("category", "Other"),
            "description": t.description,
            "parameters": t.parameters,
        })
    return out


def dispatch(name: str, model_args: Optional[Dict[str, Any]],
             birth_details: Dict[str, Any],
             ayanamsa: str = DEFAULT_AYANAMSA) -> Dict[str, Any]:
    """Execute one tool call. Raises ToolError for an unknown name; other handler
    failures are returned as `{"error": ...}` so the loop can feed them back to
    the model rather than crashing."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"Unknown tool '{name}'. Available: {', '.join(TOOLS)}.")
    kwargs = {k: v for k, v in (model_args or {}).items()}
    try:
        return tool.handler(birth_details, ayanamsa, **kwargs)
    except ToolError:
        raise
    except TypeError as e:
        # Almost always an unexpected/missing model-supplied argument.
        raise ToolError(f"Invalid arguments for '{name}': {e}")
    except Exception as e:
        return {"error": f"{name} failed: {e}"}
