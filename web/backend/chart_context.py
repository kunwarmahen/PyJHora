"""
ChartContextBuilder — assembles one rich, structured astrological context for the
LLM from the existing compute layer:

  - natal chart (D1 planetary positions, Lagna/Sun/Moon)
  - the currently-running Vimsottari dasha chain (Maha -> Bhukti -> Antara ->
    Sookshma), recomputed at full precision via get_dasha_children
  - yogas present in the Rasi chart
  - doshas (present + absent)
  - current transits (Gochara) over the natal chart

Each section is toggleable so the request (and UI) can control what is sent and
the prompt stays token-budgeted. `build_chart_context` returns the structured
dict consumed by llm_service._build_chart_analysis_prompt.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from astrology import AstrologyCompute, DEFAULT_AYANAMSA, SUPPORTED_VARGAS

# Which context sections are included by default.
DEFAULT_SECTIONS = {
    "dasha_tree": True,
    "yogas": True,
    "doshas": True,
    "transits": True,
}

# Divisional charts included by default: D1 (natal), D9 (Navamsa), D10 (Dasamsa).
# D1 is always present as the natal `planetary_positions`; the extra vargas are
# computed and added in a dedicated section.
DEFAULT_VARGAS = [1, 9, 10]

_LEVEL_NAMES = {1: "Maha Dasha", 2: "Bhukti (Antardasha)",
                3: "Antara (Pratyantar)", 4: "Sookshma"}


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _find_current(periods: List[Dict[str, Any]], today: str) -> Optional[Dict[str, Any]]:
    """Return the period (with start_date/end_date in YYYY-MM-DD) covering today."""
    for p in periods or []:
        start = p.get("start_date", "")
        end = p.get("end_date", "9999-12-31")
        if start and start <= today <= end:
            return p
    return None


def _running_dasha_chain(args: Dict[str, Any], dashas: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Walk the active Vimsottari chain from Maha down to Sookshma.

    `args` are the dob/tob/place/lat/lon/tz kwargs for AstrologyCompute calls;
    `dashas` is the already-computed get_dashas() result (reused for levels 1-2).
    """
    today = _today_str()
    chain: List[Dict[str, Any]] = []

    current_maha = dashas.get("current_dasha") or {}
    if not current_maha.get("lord"):
        return chain

    chain.append({
        "level": 1,
        "level_name": _LEVEL_NAMES[1],
        "lord": current_maha["lord"],
        "start_date": current_maha.get("start_date"),
        "end_date": current_maha.get("end_date"),
    })

    # Level 2: current Bhukti from the already-computed sub-periods.
    bhukti_periods = (dashas.get("current_bhukthi") or {}).get("periods", [])
    current_bhukti = _find_current(bhukti_periods, today)
    if not current_bhukti:
        return chain
    chain.append({
        "level": 2,
        "level_name": _LEVEL_NAMES[2],
        "lord": current_bhukti["lord"],
        "start_date": current_bhukti.get("start_date"),
        "end_date": current_bhukti.get("end_date"),
    })

    # Levels 3-4: drill down via get_dasha_children, recomputed at full precision.
    path = [current_maha["lord"], current_bhukti["lord"]]
    for level in (3, 4):
        res = AstrologyCompute.get_dasha_children(lords_path=path, **args)
        if res.get("status") != "success":
            break
        current = _find_current(res.get("children", []), today)
        if not current:
            break
        chain.append({
            "level": level,
            "level_name": _LEVEL_NAMES[level],
            "lord": current["lord"],
            "start_date": current.get("start_date"),
            "end_date": current.get("end_date"),
        })
        path = path + [current["lord"]]

    return chain


def build_chart_context(birth_details: Dict[str, Any],
                        ayanamsa: str = DEFAULT_AYANAMSA,
                        sections: Optional[Dict[str, bool]] = None,
                        vargas: Optional[List[int]] = None) -> Dict[str, Any]:
    """Build the structured context dict for the LLM prompt.

    `birth_details` is a dict with dob, tob, place, latitude, longitude, timezone.
    `sections` overrides DEFAULT_SECTIONS to toggle individual context blocks.
    `vargas` is the list of divisional-chart factors to include (D1 is always the
    natal base; the rest are computed into a dedicated section).
    """
    sections = {**DEFAULT_SECTIONS, **(sections or {})}
    # Keep only supported factors, preserve order, dedupe.
    requested = vargas if vargas is not None else DEFAULT_VARGAS
    seen = set()
    varga_factors = []
    for f in requested:
        if f in SUPPORTED_VARGAS and f not in seen:
            seen.add(f)
            varga_factors.append(f)
    args = {
        "dob": birth_details["dob"],
        "tob": birth_details["tob"],
        "place": birth_details.get("place", ""),
        "lat": birth_details.get("latitude"),
        "lon": birth_details.get("longitude"),
        "tz": birth_details.get("timezone"),
    }

    chart = AstrologyCompute.calculate_birth_chart(ayanamsa=ayanamsa, **args)
    d1 = chart.get("d1_chart", {})
    moon = d1.get("Moon", {})
    sun = d1.get("Sun", {})

    ctx: Dict[str, Any] = {
        "birth_details": {
            "dob": birth_details["dob"],
            "tob": birth_details["tob"],
            "place": birth_details.get("place", ""),
        },
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

    # Dasha — always include the base current/next (cheap; used for fallback
    # rendering), plus the full running chain when requested.
    dashas = AstrologyCompute.get_dashas(**args)
    ctx["current_dasha"] = dashas.get("current_dasha", {})
    ctx["next_dasha"] = dashas.get("next_dasha", {})
    ctx["current_bhukthi"] = dashas.get("current_bhukthi", {})
    if sections.get("dasha_tree"):
        ctx["dasha_tree"] = _running_dasha_chain(args, dashas)

    if sections.get("yogas"):
        y = AstrologyCompute.get_yogas(ayanamsa=ayanamsa, **args)
        ctx["yogas"] = y.get("yogas", []) if y.get("status") == "success" else []

    if sections.get("doshas"):
        d = AstrologyCompute.get_doshas(ayanamsa=ayanamsa, **args)
        ctx["doshas"] = d.get("doshas", []) if d.get("status") == "success" else []

    if sections.get("transits"):
        t = AstrologyCompute.get_transits(ayanamsa=ayanamsa, **args)
        if t.get("status") == "success":
            ctx["transits"] = {
                "transit_date": t.get("transit_date"),
                "natal": t.get("natal", {}),
                "planets": t.get("planets", {}),
                "upcoming": t.get("upcoming", []),
            }

    # Divisional charts (vargas). D1 is already the natal `planetary_positions`,
    # so only the extra factors are computed into their own section.
    varga_charts = []
    for factor in varga_factors:
        if factor == 1:
            continue
        vc = AstrologyCompute.calculate_divisional_chart(
            varga_factor=factor, ayanamsa=ayanamsa, **args)
        if vc.get("status") == "success":
            varga_charts.append({
                "varga": vc.get("varga"),
                "code": vc.get("code"),
                "name": vc.get("name"),
                "significance": vc.get("significance"),
                "lagna": vc.get("lagna", {}),
                "planets": vc.get("planets", {}),
            })
    if varga_charts:
        ctx["vargas"] = varga_charts

    # Record what was included so the caller (and the "what was sent" modal) can
    # show it.
    ctx["_sections"] = sections
    ctx["_vargas"] = varga_factors
    return ctx
