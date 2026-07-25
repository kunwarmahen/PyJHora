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

from astrology import (AstrologyCompute, DEFAULT_AYANAMSA, SUPPORTED_VARGAS,
                       SUPPORTED_DASHAS)
from chart_context import _running_dasha_chain
import rag


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


def _arudha_padas(bd, ayanamsa, **_):
    a = AstrologyCompute.get_arudha_padas(ayanamsa=ayanamsa, **_args(bd))
    if a.get("status") != "success":
        return a
    return {"arudha_padas": a.get("arudha_padas", []), "note": a.get("note")}


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


def _varshaphal(bd, ayanamsa, year: Optional[int] = None, **_):
    try:
        yr = int(year)
    except (TypeError, ValueError):
        raise ToolError("get_varshaphal requires an integer 'year' (e.g. 2026).")
    v = AstrologyCompute.get_varshaphal(year=yr, ayanamsa=ayanamsa, **_args(bd))
    if v.get("status") != "success":
        return v
    return {
        "year": v.get("year"),
        "age": v.get("age"),
        "year_entry": v.get("year_entry", {}),
        "lagna": v.get("lagna", {}),
        "planets": v.get("planets", {}),
        "muntha": v.get("muntha", {}),
        "year_lord": v.get("year_lord"),
        "sahams": v.get("sahams", []),
        "tajaka_yogas": v.get("tajaka_yogas", []),
        "annual_dasha": v.get("annual_dasha", {}),
    }


def _pravesh_summary(pravesh):
    if not pravesh:
        return None
    return {
        "lagna": pravesh.get("lagna"), "muntha": pravesh.get("muntha"),
        "year_lord": pravesh.get("year_lord"),
        "tajaka_yogas": pravesh.get("tajaka_yogas", []),
    }


def _fortnightly_digest(bd, ayanamsa, date: Optional[str] = None, **_):
    f = AstrologyCompute.get_fortnightly_digest(date=date, ayanamsa=ayanamsa, **_args(bd))
    if f.get("status") != "success":
        return f
    return {
        "start_date": f.get("start_date"), "end_date": f.get("end_date"),
        "span_days": f.get("span_days"), "window": f.get("window_label"),
        "dasha": f.get("dasha"), "events": f.get("events", []),
        "paksha_pravesha": _pravesh_summary(f.get("pravesh")),
        "highlights": f.get("highlights", []),
    }


def _monthly_digest(bd, ayanamsa, date: Optional[str] = None,
                    basis: Optional[str] = None, **_):
    b = "lunar" if str(basis or "solar").lower() == "lunar" else "solar"
    m = AstrologyCompute.get_monthly_digest(date=date, basis=b, ayanamsa=ayanamsa, **_args(bd))
    if m.get("status") != "success":
        return m
    return {
        "start_date": m.get("start_date"), "end_date": m.get("end_date"),
        "span_days": m.get("span_days"), "basis": b, "window": m.get("window_label"),
        "dasha": m.get("dasha"), "events": m.get("events", []),
        "monthly_pravesha": _pravesh_summary(m.get("pravesh")),
        "highlights": m.get("highlights", []),
    }


def _tithi_pravesha(bd, ayanamsa, year: Optional[int] = None,
                    date: Optional[str] = None, **_):
    yr = int(year) if year not in (None, "") else None
    t = AstrologyCompute.get_tithi_pravesha(year=yr, date=date, ayanamsa=ayanamsa, **_args(bd))
    if t.get("status") != "success":
        return t
    return {
        "label": t.get("label"), "window": t.get("window"),
        "lagna": t.get("lagna"), "planets": t.get("planets"),
        "muntha": t.get("muntha"), "year_lord": t.get("year_lord"),
        "tajaka_yogas": t.get("tajaka_yogas", []),
    }


def _raja_yogas(bd, ayanamsa, **_):
    r = AstrologyCompute.get_raja_yogas(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {"count": r.get("count"), "raja_yogas": r.get("raja_yogas", [])}


def _planet_conditions(bd, ayanamsa, **_):
    r = AstrologyCompute.get_planet_conditions(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    # Only the flagged planets matter to the model; drop the clean ones.
    return {"counts": r.get("counts"),
            "flagged": [{"planet": p["planet"], "sign": p["sign_name"],
                         "house": p["house"],
                         "conditions": [{"name": f["label"], "tone": f["tone"],
                                         **({"partner": f["partner"]} if f.get("partner") else {})}
                                        for f in p["flags"]]}
                        for p in r.get("flagged", [])]}


def _friendships(bd, ayanamsa, **_):
    r = AstrologyCompute.get_friendships(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {
        "matrix": [{"planet": row["planet"],
                    "relations": {x["to"]: x["label"] for x in row["relations"]
                                  if not x.get("self")}}
                   for row in r.get("matrix", [])],
        "house_lords": [{"house": h["house"], "lord": h["lord"],
                         "lord_in_house": h["lord_house"]}
                        for h in r.get("house_lords", [])],
        "parivartana": r.get("parivartana", []),
    }


def _avasthas(bd, ayanamsa, **_):
    r = AstrologyCompute.get_avasthas(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {"planets": [{"planet": p["planet"], "sign": p["sign_name"],
                         "dignity": p["dignity"],
                         "baladi": p["baladi"]["state"],
                         "jagradadi": p["jagradadi"]["state"],
                         "deeptadi": p["deeptadi"]["state"],
                         "deeptadi_tone": p["deeptadi"]["tone"]}
                        for p in r.get("planets", [])]}


def _saturn_transits(bd, ayanamsa, **_):
    r = AstrologyCompute.get_saturn_transits(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    cur = r.get("current") or {}
    return {
        "moon_sign": r.get("moon_sign"),
        "in_sade_sati": bool(cur.get("sade_sati")),
        "current_phase": (cur.get("sade_sati") or {}).get("current_phase"),
        "in_ashtama": bool(cur.get("ashtama")),
        "in_kantaka": bool(cur.get("kantaka")),
        "sade_sati_periods": [
            {"start": p["start_date"], "end": p["end_date"],
             "is_current": p["is_current"], "is_past": p["is_past"]}
            for p in r.get("sade_sati_periods", [])],
    }


def _kota_chakra(bd, ayanamsa, current_date: Optional[str] = None, **_):
    r = AstrologyCompute.get_kota_chakra(ayanamsa=ayanamsa, current_date=current_date,
                                         **_args(bd))
    if r.get("status") != "success":
        return r
    # Per-ring occupancy only — the 28 star cells are far too much for a prompt,
    # and the reading is about which grahas reached which enclosure.
    return {
        "transit_date": r.get("transit_date"),
        "birth_star": r.get("birth_star", {}).get("name"),
        "kota_swami": r.get("kota_lord"),
        "kota_paala": r.get("kota_paala"),
        "rings": [
            {"ring": ring["name"],
             "malefics": [p["name"] for c in ring["cells"] for p in c["transit"] if p["malefic"]],
             "benefics": [p["name"] for c in ring["cells"] for p in c["transit"] if not p["malefic"]]}
            for ring in r.get("rings", [])],
        "findings": [f["text"] for f in r.get("findings", [])],
    }


def _kaala_chakra(bd, ayanamsa, current_date: Optional[str] = None, **_):
    r = AstrologyCompute.get_kaala_chakra(ayanamsa=ayanamsa, current_date=current_date,
                                          **_args(bd))
    if r.get("status") != "success":
        return r
    return {
        "transit_date": r.get("transit_date"),
        "base_star": r.get("base_star", {}).get("name"),
        "directions": [
            {"direction": d["direction"], "verdict": d["tone"],
             "malefics": d["malefics"], "benefics": d["benefics"]}
            for d in r.get("directions", [])],
        "favourable": r.get("favourable", []),
        "avoid": r.get("avoid", []),
    }


def _tripataki_chakra(bd, ayanamsa, current_date: Optional[str] = None,
                      basis: Optional[str] = None, year: Optional[int] = None, **_):
    r = AstrologyCompute.get_tripataki_chakra(
        ayanamsa=ayanamsa, current_date=current_date,
        basis=basis or "transit", year=year, **_args(bd))
    if r.get("status") != "success":
        return r
    return {
        "basis": r.get("basis"),
        "date": r.get("transit_date"),
        "lagna": r.get("natal_lagna"),
        "moon": r.get("transit_moon"),
        "vedha": [
            {"target": v["target"], "sign": v["sign"], "sign_class": v["sign_class"],
             "verdict": v["tone"],
             "obstructed_by": [f"{h['planet']} from {h['from_sign']}"
                               for h in v["obstructed_by"]]}
            for v in r.get("vedha", [])],
    }


def _sarvatobhadra(bd, ayanamsa, current_date: Optional[str] = None, **_):
    r = AstrologyCompute.get_sarvatobhadra_chakra(
        ayanamsa=ayanamsa, current_date=current_date, **_args(bd))
    if r.get("status") != "success":
        return r
    # The 9x9 grid itself is far too large for a prompt; the findings ARE the reading.
    return {
        "transit_date": r.get("transit_date"),
        "anchors": {k: a.get("name") for k, a in (r.get("anchors") or {}).items()},
        "findings": [
            {"planet": f.get("planet"), "nature": f.get("planet_nature"),
             "kind": f.get("kind"), "tone": f.get("tone"), "on": f.get("label")}
            for f in r.get("findings", [])],
    }


def _dasha_periods(bd, ayanamsa, dhasa_type: str = "", **_):
    if not dhasa_type or dhasa_type not in SUPPORTED_DASHAS:
        raise ToolError(
            "get_dasha_periods requires a 'dhasa_type' from: "
            + ", ".join(SUPPORTED_DASHAS) + ". For Vimsottari use get_dasha_chain.")
    r = AstrologyCompute.get_dasha_periods(dhasa_type, **_args(bd))
    if r.get("status") != "success":
        return r
    from datetime import date as _date
    today = _date.today().isoformat()
    periods = r.get("periods", [])
    current = next((p for p in periods
                    if p["start_date"] <= today <= p["end_date"]), None)
    return {
        "dhasa_type": r.get("dhasa_type"),
        "name": r.get("name"),
        "lord_type": r.get("lord_type"),
        "chakra_refs": r.get("chakra_refs"),
        "current": current,
        # Cap the list — Sudarshana runs to 108 one-year periods, which would
        # dominate the prompt. 24 rows covers a lifetime for the multi-year raasi
        # systems and ~24 years of the yearly wheel; `current` is always included
        # above, and total_periods tells the model the list is truncated.
        "periods": periods[:24],
        "total_periods": len(periods),
    }


def _strength(bd, ayanamsa, **_):
    r = AstrologyCompute.get_strength(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {
        "shadbala": [{"planet": p["planet"], "total_rupa": p["total_rupa"],
                      "required_rupa": p["required_rupa"], "ratio": p["strength_ratio"],
                      "rank": p["rank"], "sufficient": p["sufficient"]}
                     for p in r.get("planets", [])],
        "bhava_bala": [{"house": b["house"], "signification": b["signification"],
                        "rupa": b["rupa"], "ratio": b["strength_ratio"]}
                       for b in r.get("bhava_bala", [])],
        "vimsopaka": [{"planet": v["planet"], "shodhasavarga": v["shodhasavarga"]}
                      for v in r.get("vimsopaka", [])],
    }


def _life_timeline(bd, ayanamsa, target_date: Optional[str] = None, **_):
    # A specific date → the "what's running" window context (maha/bhukti, Saturn
    # phase, nearby ingresses/eclipses). No date → a compact overview: the current
    # dasha, the active Saturn phase, and the next few slow-planet ingresses.
    if target_date:
        c = AstrologyCompute.get_timeline_window_context(
            target_date=target_date, ayanamsa=ayanamsa, **_args(bd))
        if c.get("status") != "success":
            return c
        return {"target_date": c.get("target_date"), "moon_sign": c.get("moon_sign"),
                "maha": c.get("maha"), "bhukti": c.get("bhukti"),
                "saturn_phase": c.get("saturn_phase"),
                "ingresses": c.get("ingresses", []), "eclipses": c.get("eclipses", [])}
    tl = AstrologyCompute.get_life_timeline(
        years_before=1, years_after=5, ayanamsa=ayanamsa, **_args(bd))
    if tl.get("status") != "success":
        return tl
    cur_maha = next((m for m in tl.get("maha_bands", []) if m.get("is_current")), None)
    cur_bhukti = next((b for b in tl.get("bhukti_bands", []) if b.get("is_current")), None)
    cur_sat = next((p for p in tl.get("saturn_phases", []) if p.get("is_current")), None)
    return {
        "moon_sign": tl.get("moon_sign"),
        "current_maha": cur_maha, "current_bhukti": cur_bhukti,
        "current_saturn_phase": cur_sat,
        "next_ingresses": tl.get("ingresses", [])[:6],
        "upcoming_eclipses": tl.get("eclipses", [])[:4],
    }


def _nadi(bd, ayanamsa, gender: Optional[int] = None, **_):
    # Nadi karaka reading: the fixed significators + placement by sign, the life
    # themes each karaka heads, and the slow-graha transit triggers.
    r = AstrologyCompute.get_nadi_reading(gender=gender, ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {
        "ascendant": r.get("ascendant"), "moon_sign": r.get("moon_sign"),
        "spouse_karaka": r.get("spouse_karaka"),
        "karakas": [
            {"planet": k["planet"], "signifies": k["significations"],
             "sign": k["sign_name"], "dispositor": k["sign_lord"],
             "star_lord": k["star_lord"], "conjunct": k["conjunct"]}
            for k in r.get("karakas", [])
        ],
        "themes": r.get("themes", []),
        "triggers": r.get("triggers", [])[:8],
    }


def _longevity(bd, ayanamsa, **_):
    r = AstrologyCompute.get_longevity(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {"category_name": r.get("category_name"),
            "category_desc": r.get("category_desc"),
            "factors": r.get("factors", [])}


def _pancha_pakshi(bd, ayanamsa, date: Optional[str] = None, **_):
    r = AstrologyCompute.get_pancha_pakshi(date=date, **_args(bd))
    if r.get("status") != "success":
        return r
    # Trim the full 10×5 timeline to the summary the model actually needs.
    return {
        "date": r.get("date"),
        "birth_bird": r.get("birth_bird", {}),
        "best_times": r.get("best_times", []),
        "avoid_times": r.get("avoid_times", []),
    }


def _sphuta(bd, ayanamsa, **_):
    r = AstrologyCompute.get_sphuta(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {"sphutas": r.get("sphutas", [])}


def _special_points(bd, ayanamsa, **_):
    r = AstrologyCompute.get_special_points(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {
        "lagna_sign_name": r.get("lagna_sign_name"),
        "special_lagnas": r.get("special_lagnas", []),
        "upagrahas": r.get("upagrahas", []),
        "varnadas": r.get("varnadas", []),
        "varnada_method_name": r.get("varnada_method_name"),
        "sphutas": r.get("sphutas", []),
        "interpreted": r.get("interpreted", []),
        "note": r.get("note"),
    }


def _sahams(bd, ayanamsa, **_):
    r = AstrologyCompute.get_sahams(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {"sahams": r.get("sahams", [])}


def _argala(bd, ayanamsa, **_):
    r = AstrologyCompute.get_argala(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    # Only the houses with a net argala/virodhargala are worth the tokens.
    houses = [h for h in r.get("houses", []) if h.get("net") not in (None, "none", "balanced")]
    return {"houses": houses}


def _kp(bd, ayanamsa, **_):
    a = _args(bd)
    r = AstrologyCompute.get_kp_details(dob=a["dob"], tob=a["tob"], place=a["place"],
                                        lat=a["lat"], lon=a["lon"], tz=a["tz"])
    if r.get("status") != "success":
        return r
    return {"planets": r.get("planets", []), "cusps": r.get("cusps", []),
            "significators": r.get("significators", {}),
            "ruling_planets": (r.get("ruling_planets") or {}).get("planets", [])}


def _jaimini(bd, ayanamsa, **_):
    r = AstrologyCompute.get_jaimini(ayanamsa=ayanamsa, **_args(bd))
    if r.get("status") != "success":
        return r
    return {"chara_karakas": r.get("chara_karakas", []),
            "atmakaraka": r.get("atmakaraka"),
            "karakamsa": r.get("karakamsa", {}), "swamsa": r.get("swamsa", {}),
            "argala": r.get("argala", [])}


def _vedic_clock(bd, ayanamsa, date: Optional[str] = None, **_):
    # Ephemeris-only (no ayanamsa): pass just the location fields.
    a = _args(bd)
    r = AstrologyCompute.get_vedic_clock(date=date, place=a["place"],
                                         lat=a["lat"], lon=a["lon"], tz=a["tz"])
    if r.get("status") != "success":
        return r
    return {"date": r.get("date"), "sunrise": r.get("sunrise"), "sunset": r.get("sunset"),
            "ghati": r.get("ghati"), "vighati": r.get("vighati"),
            "current_hora": r.get("current_hora"), "panchanga": r.get("panchanga")}


def _muhurta(bd, ayanamsa, activity: str = "general",
             start_date: Optional[str] = None, end_date: Optional[str] = None, **_):
    a = _args(bd)
    r = AstrologyCompute.get_muhurta(
        activity=activity, start_date=start_date, end_date=end_date,
        place=a["place"], lat=a["lat"], lon=a["lon"], tz=a["tz"])
    if r.get("status") != "success":
        return r
    return {
        "activity": r.get("activity"),
        "activity_label": r.get("activity_label"),
        "start_date": r.get("start_date"),
        "end_date": r.get("end_date"),
        "best_windows": r.get("best_windows", [])[:8],
    }


def _retrograde(bd, ayanamsa, date: Optional[str] = None, **_):
    a = _args(bd)
    r = AstrologyCompute.get_retrograde(date=date, place=a["place"],
                                        lat=a["lat"], lon=a["lon"], tz=a["tz"])
    if r.get("status") != "success":
        return r
    # Drop the heavy orbit arrays — the model only needs status + stations.
    planets = [{k: v for k, v in p.items() if k not in ("orbit_x", "orbit_y")}
               for p in r.get("planets", [])]
    return {"date": r.get("date"), "retrograde_now": r.get("retrograde_now", []),
            "planets": planets, "nodes": r.get("nodes", [])}


def _classical_texts(bd, ayanamsa, query: str = "", **_):
    if not query.strip():
        return {"error": "Provide a `query` describing the topic to look up."}
    passages = rag.retrieve(query, k=3)
    if not passages:
        return {"available": False,
                "note": "No classical-text corpus is indexed (or embeddings are "
                        "unavailable). Answer from chart logic without citations.",
                "passages": []}
    return {"available": True, "passages": passages}


def _journal_entries(bd, ayanamsa, category: Optional[str] = None, **_):
    # The journal is DB-backed (async) so it's pre-fetched by the endpoint and
    # injected onto birth_details as `_journal`; we just filter/return it here.
    entries = bd.get("_journal") or []
    if category:
        entries = [e for e in entries if e.get("category") == category]
    return {"count": len(entries), "entries": entries}


def _nakshatra_profile(bd, ayanamsa, current_date: Optional[str] = None, **_):
    r = AstrologyCompute.get_nakshatra_profile(
        ayanamsa=ayanamsa, current_date=current_date, **_args(bd))
    if r.get("status") != "success":
        return r
    cal = r.get("tarabala_calendar", [])
    return {
        "profile": r.get("profile"),
        "moon_sign": r.get("moon_sign"),
        "favourable_days": [c["date"] for c in cal if c["tone"] in ("very_good", "good")],
        "caution_days": [c["date"] for c in cal if c["tone"] in ("bad", "caution")],
    }


def _gochara_phala(bd, ayanamsa, current_date: Optional[str] = None, **_):
    r = AstrologyCompute.get_gochara_phala(
        ayanamsa=ayanamsa, current_date=current_date, **_args(bd))
    if r.get("status") != "success":
        return r
    return {
        "transit_date": r.get("transit_date"),
        "moon_sign": r.get("moon_sign"),
        "results": [{"planet": x["planet"], "house_from_moon": x["house_from_moon"],
                     "verdict": x["verdict"], "obstructed_by": x["obstructed_by"]}
                    for x in r.get("results", [])],
    }


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_EMPTY_PARAMS = {"type": "object", "properties": {}, "required": []}

_DASHA_KEYS = ", ".join(sorted(SUPPORTED_DASHAS))

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
        "get_arudha_padas",
        "Bhava arudhas of the Rasi chart: AL (Arudha Lagna = the perceived self, "
        "image, status and material manifestation), UL (Upapada = spouse/marriage), "
        "and A2..A11 for houses 2-11 — each the sign the arudha falls in. Use for "
        "questions about reputation, public image, how one is seen, or (via UL) the "
        "marriage partner.",
        _EMPTY_PARAMS, _arudha_padas,
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
    _Tool(
        "get_varshaphal",
        "Varshaphal / Tajaka annual (solar-return) horoscope for a target year: the "
        "annual Ascendant + planet signs, the Muntha (progressed point), the year-lord "
        "(Varsheshwara), key Sahams (sensitive points), present Tajaka yogas, and the "
        "annual Mudda dasha sub-periods. Use for 'how is <year> for me?' questions.",
        {"type": "object", "properties": {
            "year": {"type": "integer",
                     "description": "Target Gregorian year, e.g. 2026 (>= birth year)."}},
         "required": ["year"]},
        _varshaphal,
    ),
    _Tool(
        "get_fortnightly_digest",
        "A personalized fortnight reading anchored to the Paksha Pravesha chart: "
        "the running lunar fortnight (Shukla or Krishna paksha, ~14.8 days) with "
        "its Lagna/Muntha and Tajaka yogas, the running Vimsottari dasha, and the "
        "transit events (sign-ingresses & retrograde stations) inside the paksha. "
        "Use for 'how is my fortnight / this paksha?' questions.",
        {"type": "object", "properties": {
            "date": {"type": "string",
                     "description": "A date within the target paksha as YYYY-MM-DD; defaults to today."}},
         "required": []},
        _fortnightly_digest,
    ),
    _Tool(
        "get_monthly_digest",
        "A personalized month reading anchored to a progressed monthly chart, plus "
        "the running dasha and the month's transit events. basis='solar' (default) "
        "uses the Maasa Pravesha (Tajaka monthly solar return, ~30.4d); "
        "basis='lunar' uses the birth-tithi return (lunar month, ~29.5d). Either "
        "way the 'month' is that pravesha window, NOT a calendar month. Use for "
        "'how is my month / this month?' questions.",
        {"type": "object", "properties": {
            "date": {"type": "string",
                     "description": "A date within the target month as YYYY-MM-DD; defaults to today."},
            "basis": {"type": "string", "enum": ["solar", "lunar"], "default": "solar",
                      "description": "Which pravesha ladder to cast the monthly chart on."}},
         "required": []},
        _monthly_digest,
    ),
    _Tool(
        "get_tithi_pravesha",
        "Tithi Pravesha — the ANNUAL *lunar*-return chart, cast when the person's "
        "natal tithi and lunar month recur (~354 days). This is the lunar "
        "counterpart of the solar-return Varshaphal (get_varshaphal) and is read "
        "alongside it, classically for the year's emotional/domestic texture. "
        "Returns the TP Lagna, planets, Muntha, year-lord and Tajaka yogas. Use for "
        "'how is this year for me?' when a lunar-return view is wanted.",
        {"type": "object", "properties": {
            "year": {"type": "integer",
                     "description": "Target Gregorian year of the lunar return; defaults to the current TP window."},
            "date": {"type": "string",
                     "description": "A date inside the target TP window as YYYY-MM-DD; defaults to today."}},
         "required": []},
        _tithi_pravesha,
    ),
    _Tool(
        "get_life_timeline",
        "The dasha–transit life timeline. With NO target_date: a compact overview "
        "— the current Vimsottari Mahadasha + Bhukti, the active Sade Sati / Ashtama "
        "/ Kantaka Saturn phase (if any), and the next few Jupiter/Saturn/Rahu "
        "ingresses and eclipses. With a target_date (YYYY-MM-DD): 'what's running' "
        "at that point — the Maha/Bhukti covering it, the Saturn phase, and the "
        "ingresses/eclipses within ~9 months. Use for 'what's happening in my life "
        "now / around <date>', period timing, and Sade Sati questions.",
        {"type": "object", "properties": {
            "target_date": {"type": "string",
                            "description": "A date as YYYY-MM-DD to read that window; omit for a current overview."}},
         "required": []},
        _life_timeline,
    ),
    _Tool(
        "get_saturn_transits",
        "Sade Sati and Saturn's transits from the natal Moon: the ~7½-year Sade "
        "Sati cycles (rising/peak/setting phases with dates), Ashtama (8th) and "
        "Kantaka (4th) Shani periods, and whether any is running now. Use for "
        "'am I in Sade Sati?', Saturn-period timing, and Shani questions. Frame it "
        "as a period of maturing, never doom.",
        _EMPTY_PARAMS,
        _saturn_transits,
    ),
    _Tool(
        "get_strength",
        "The full strength picture: Shadbala (six-fold planetary strength — total "
        "vs required rupas, ratio, rank), Bhava Bala (strength of the 12 houses) and "
        "Vimsopaka Bala (varga-dignity 0-20 per planet). Use for 'which planets/"
        "houses are strong or weak' and to weigh whether a graha can deliver its "
        "promise. Strength ≠ good/bad — a strong malefic acts forcefully.",
        _EMPTY_PARAMS,
        _strength,
    ),
    _Tool(
        "get_friendships",
        "Planetary relationships in THIS chart: the compound-friendship matrix "
        "(natural folded with temporal placement — Adhimitra great-friend → "
        "Adhishatru great-enemy), the house-lord placements (which house each "
        "bhava's lord occupies) and any Parivartana (mutual sign exchange). Use to "
        "judge how planets cooperate and how houses are linked.",
        _EMPTY_PARAMS,
        _friendships,
    ),
    _Tool(
        "get_avasthas",
        "The planetary avasthas (states) for the seven grahas — Baladi (infant→"
        "dead by degree, Yuva=prime), Jagradadi (awake/dreaming/asleep by dignity) "
        "and Deeptadi (radiant…agitated). Describes each planet's *vitality and "
        "mood* — how ready it is to give results — complementing raw Shadbala. Use "
        "for nuanced strength questions and why a planet's results feel muted or lively.",
        _EMPTY_PARAMS,
        _avasthas,
    ),
    _Tool(
        "get_planet_conditions",
        "Classical point-conditions (\"flags\") per planet that modify how it "
        "delivers results but don't show on a plain chart: Combust (Asta), "
        "Vargottama, Pushkara Navamsa/Bhaga, Mrityu Bhaga, Marana Karaka Sthana, "
        "Gandanta, Graha Yuddha (planetary war) and Retrograde — each with a "
        "benefic/challenging/neutral tone. Use to sharpen dignity/strength "
        "judgements and when asked why a planet feels strong or strained.",
        _EMPTY_PARAMS,
        _planet_conditions,
    ),
    _Tool(
        "get_raja_yogas",
        "Dedicated Raja Yoga analysis of the natal (Rasi) chart: the fundamental "
        "Kendra-Trikona raja yogas (quadrant lord + trine lord, with a coarse "
        "strength) and the named special types (Dharma-Karmadhipati, Vipareeta, "
        "Neecha-Bhanga) with descriptions. Use for questions about power, status, "
        "success and rise in life.",
        _EMPTY_PARAMS,
        _raja_yogas,
    ),
    _Tool(
        "get_nadi",
        "Nadi karaka reading: reads the chart through the fixed natural "
        "significators (karakas) and their placement by SIGN — setting houses and "
        "aspects aside. Returns each graha's karakatwas, the sign it sits in (and "
        "its dispositor + star-lord), whom it is conjunct, the life themes each "
        "karaka heads (marriage → Venus/Jupiter, career → Saturn, etc.), and the "
        "next Jupiter/Saturn/Rahu transits into the pivotal karaka signs that time "
        "events. Use for karaka-based, conjunction-driven readings and Nadi-style "
        "event timing. Pass gender (0=male, 1=female) to foreground the right "
        "spouse karaka.",
        {"type": "object", "properties": {
            "gender": {"type": "integer", "enum": [0, 1],
                       "description": "0=male, 1=female — selects the spouse karaka."}},
         "required": []},
        _nadi,
    ),
    _Tool(
        "get_longevity",
        "Ayu (longevity) *category* — Alpa (short) / Madhya (medium) / Purna (long) "
        "— from the classical sign-pair Ayurdaya method, with the contributing "
        "factors. Returns a conditional category only, never a death date or age. "
        "Use ONLY when the person explicitly asks about vitality/longevity, and "
        "always frame it gently as conditional and multi-factorial.",
        _EMPTY_PARAMS,
        _longevity,
    ),
    _Tool(
        "get_pancha_pakshi",
        "Pancha Pakshi Sastra day-timing: the person's birth bird and today's (or a "
        "given date's) strongest and weakest activity windows (with clock times). "
        "Use for 'what is a good time today for X' muhurta-style questions.",
        {"type": "object", "properties": {
            "date": {"type": "string",
                     "description": "Date as YYYY-MM-DD; defaults to today."}},
         "required": []},
        _pancha_pakshi,
    ),
    _Tool(
        "get_sphuta",
        "The classical Sphutas — sensitive longitudes derived from the natal chart "
        "(Tri/Chatur/Pancha/Prana/Deha/Beeja/Kshetra/Tithi/Yoga/Yogi/Avayogi), each "
        "as a sign + degree + house. Supporting points that fine-tune longevity, "
        "vitality and progeny reasoning. Do not over-weight the Mrityu point.",
        _EMPTY_PARAMS,
        _sphuta,
    ),
    _Tool(
        "get_special_points",
        "Every non-planetary sensitive longitude in one table, as Jagannatha Hora "
        "prints them: the special lagnas (Bhava/Hora/Ghati/Vighati kaala lagnas, "
        "Sree, Indu, Bhrigu Bindu, Pranapada, Kunda, Varnada), the eleven upagrahas "
        "(six kaala-velas incl. Gulika/Maandi + five solar), Varnada V1..V12 and the "
        "Sphutas. Use Hora Lagna for wealth and income questions (judge the 2nd and "
        "11th from it), Ghati Lagna for power, authority and promotion questions "
        "(judge the 10th from it), Varnada Lagna for the chart's overall direction, "
        "and Gulika for chronic difficulty. The `interpreted` field lists the points "
        "that carry a settled classical rule — report the positions of the others but "
        "do NOT invent verdicts from them.",
        _EMPTY_PARAMS,
        _special_points,
    ),
    _Tool(
        "get_sahams",
        "The 36 natal Sahams (Arabic-part-like sensitive points) for life themes — "
        "Punya (fortune), Vidya (education), Karma (career), Artha (wealth), Vivaha "
        "(marriage), Puthra (children), Rajya (authority), Laabha (gains), etc. — each "
        "as a sign + house. Use to corroborate a specific life-area question.",
        _EMPTY_PARAMS,
        _sahams,
    ),
    _Tool(
        "get_argala",
        "Argala (planetary intervention) and Virodhargala (obstruction) per bhava: "
        "which houses receive strong supportive intervention vs obstruction from "
        "planets in the 2nd/4th/5th/11th (argala) and 12th/10th/9th/3rd (virodhargala). "
        "Use to judge which life areas are reinforced or blocked.",
        _EMPTY_PARAMS,
        _argala,
    ),
    _Tool(
        "get_vedic_clock",
        "Vedic day-clock now (or a given date): sunrise/sunset, the elapsed ghati/"
        "vighati, the running hora (planetary hour) lord, and the current panchanga "
        "limbs (tithi/nakshatra/yoga). Use for 'what is the vedic time / current hora' "
        "and muhurta-flavoured questions.",
        {"type": "object", "properties": {
            "date": {"type": "string",
                     "description": "Date as YYYY-MM-DD; defaults to today."}},
         "required": []},
        _vedic_clock,
    ),
    _Tool(
        "get_muhurta",
        "Muhurta (electional astrology): auspicious time windows for an activity over "
        "a date range at the birth place. activity ∈ general|marriage|travel|business|"
        "housewarming|education|medical. Returns ranked best windows (date + clock time) "
        "with the nakshatra/tithi/hora reason, avoiding Rahu Kalam/Yamaganda/Gulika. Use "
        "for 'when is a good time to <do X>' questions.",
        {"type": "object", "properties": {
            "activity": {"type": "string",
                         "enum": ["general", "marriage", "travel", "business",
                                  "housewarming", "education", "medical"],
                         "description": "The activity to time."},
            "start_date": {"type": "string",
                           "description": "Range start YYYY-MM-DD; defaults to today."},
            "end_date": {"type": "string",
                         "description": "Range end YYYY-MM-DD; defaults to +14 days."}},
         "required": []},
        _muhurta,
    ),
    _Tool(
        "get_retrograde",
        "Retrograde (Vakra) status now (or a given date): which grahas are retrograde "
        "and the next station (direction-change) dates for Mars/Mercury/Jupiter/Venus/"
        "Saturn. Use for 'is Mercury retrograde', 'what's retrograde now' questions.",
        {"type": "object", "properties": {
            "date": {"type": "string",
                     "description": "Date as YYYY-MM-DD; defaults to today."}},
         "required": []},
        _retrograde,
    ),
    _Tool(
        "get_kp",
        "Krishnamurti Paddhati (KP) view: the sign/star(nakshatra)/sub lord of the "
        "Ascendant and every graha, the 12 Placidus cuspal sub-lords, the four-fold "
        "house significators, and the current ruling planets. Use for KP-style "
        "questions ('what does the 7th cuspal sub-lord say', significators, ruling planets).",
        _EMPTY_PARAMS,
        _kp,
    ),
    _Tool(
        "get_jaimini",
        "Jaimini toolkit: the 8 Chara Karakas (with sign/house), the Karakamsa (the "
        "Atmakaraka's Navamsa sign) and Swamsa (D9 Lagna) with their occupants and "
        "Jaimini rasi-drishti aspects, and the argala on the Lagna & 7th. Use for "
        "Jaimini/Karakamsa questions about calling, soul-agenda, and self/partner.",
        _EMPTY_PARAMS,
        _jaimini,
    ),
    _Tool(
        "get_nakshatra_profile",
        "Janma-nakshatra (birth star) profile: the Moon's nakshatra + pada with its "
        "classical attributes (ruling planet, deity, symbol, gana, yoni, nadi, guna, "
        "varna, naming syllable, theme), plus this month's tarabala — the personal "
        "favourable/caution days as the Moon cycles the 27 stars. Use for "
        "personality-by-birth-star questions and 'which days are good for me'.",
        {"type": "object", "properties": {
            "current_date": {"type": "string",
                             "description": "Anchor date YYYY-MM-DD for the 27-day "
                                            "tarabala calendar; defaults to today."}},
         "required": []},
        _nakshatra_profile,
    ),
    _Tool(
        "get_gochara_phala",
        "Classical Moon-referenced gochara-phala with vedha: for each transiting "
        "graha, the house it occupies from the natal Moon, whether that is a "
        "favourable position, and whether a vedha (another graha in the obstruction "
        "house) cancels the good result. The panchang-tradition transit verdict, "
        "complementing the degree-based transit view. Use for 'how are the transits "
        "for me right now' questions.",
        {"type": "object", "properties": {
            "current_date": {"type": "string",
                             "description": "Transit date YYYY-MM-DD; defaults to today."}},
         "required": []},
        _gochara_phala,
    ),
    _Tool(
        "get_journal_entries",
        "The user's astro-journal: their own dated life events (career/relationship/"
        "health/move/… + free notes), each with the Vimsottari maha/bhukti that was "
        "running on that date. Use to ground timing questions in what actually "
        "happened in this person's life, or when asked how a past dasha/bhukti "
        "behaved for them. Optionally filter by category.",
        {"type": "object", "properties": {
            "category": {"type": "string",
                         "description": "Optional filter: career|relationship|family|"
                                        "health|finance|move|education|spiritual|loss|"
                                        "milestone|other."}},
         "required": []},
        _journal_entries,
    ),
    _Tool(
        "get_sarvatobhadra_chakra",
        "Sarvatobhadra Chakra: the transiting grahas mapped onto the all-directions "
        "star grid, reporting which of the native's sensitive points (birth star, "
        "Moon sign, birth tithi/weekday) each graha OCCUPIES or casts VEDHA "
        "(obstruction) on, with a supportive/stressful tone. Use for 'is today "
        "good/bad for me', muhurta-style day judgement and general auspiciousness.",
        {"type": "object", "properties": {
            "current_date": {"type": "string",
                             "description": "YYYY-MM-DD; defaults to today."}},
         "required": []},
        _sarvatobhadra,
    ),
    _Tool(
        "get_kota_chakra",
        "Kota Chakra (the fort): the 28 nakshatras as four concentric enclosures "
        "counted from the birth star — Baahya (outer wall), Praakaara (rampart), "
        "Durgantara (inner fort), Sthamba (central pillar). Reports which grahas "
        "have reached which enclosure (malefics pressure the fort, benefics defend "
        "it) plus the Kota Swami (defender) and Kota Paala (guard). Use for "
        "PROTECTION, safety and health-anxiety questions — the deeper a malefic "
        "has reached, the more personal the pressure.",
        {"type": "object", "properties": {
            "current_date": {"type": "string",
                             "description": "YYYY-MM-DD; defaults to today."}},
         "required": []},
        _kota_chakra,
    ),
    _Tool(
        "get_kaala_chakra",
        "Kaala Chakra (the wheel of directions): the 28 stars as eight spokes "
        "counted from the Sun's star, where EACH SPOKE IS A COMPASS DIRECTION. "
        "Reports which grahas colour which direction and a verdict per direction "
        "(supportive / best-avoided / mixed / neutral). Use for DIRECTION questions "
        "— which way to travel, which way to face for important work, which "
        "direction to push a matter. Nothing else in this toolset answers that.",
        {"type": "object", "properties": {
            "current_date": {"type": "string",
                             "description": "YYYY-MM-DD; defaults to today."}},
         "required": []},
        _kaala_chakra,
    ),
    _Tool(
        "get_tripataki_chakra",
        "Tripataki Chakra: vedha (mutual obstruction between signs) on the Moon "
        "and the Lagna — a broad overview of the NATURE of what dominates a period, "
        "not specific events. Set basis='annual' (optionally with a `year`) to read "
        "it on the Varshaphal/solar-return chart, which is its classical home; "
        "basis='transit' (default) reads the current moment.",
        {"type": "object", "properties": {
            "basis": {"type": "string", "enum": ["transit", "annual"],
                      "default": "transit",
                      "description": "'annual' = the Varshaphal solar-return chart."},
            "year": {"type": "integer",
                     "description": "Target year when basis='annual'; defaults to now."},
            "current_date": {"type": "string",
                             "description": "YYYY-MM-DD when basis='transit'."}},
         "required": []},
        _tripataki_chakra,
    ),
    _Tool(
        "get_dasha_periods",
        "Maha-period timeline for a NON-Vimsottari dasha system (for Vimsottari use "
        "get_dasha_chain). Pass `dhasa_type` — one of: " + _DASHA_KEYS + ". Graha "
        "systems return planet lords, raasi systems return signs, and "
        "sudharsana_chakra returns a triple (the active rasi on the Lagna, Moon and "
        "Sun wheels at once). Returns the current period plus the timeline. Use when "
        "a question calls for a second opinion on timing, or names a system.",
        {"type": "object", "properties": {
            "dhasa_type": {"type": "string",
                           "description": "Dasha system key, e.g. 'chara', 'yogini', "
                                          "'sudharsana_chakra'."}},
         "required": ["dhasa_type"]},
        _dasha_periods,
    ),
    _Tool(
        "search_classical_texts",
        "Search the local corpus of classical Jyotish texts (BPHS, Saravali, "
        "Phaladeepika, …) for passages relevant to a topic, so you can GROUND and "
        "CITE a point in the shastra (e.g. quote the source + reference) instead of "
        "asserting on your own authority. Pass a `query` describing the principle "
        "(e.g. 'results of exalted Jupiter in the 5th', 'Sade Sati effects'). If it "
        "returns available=false, no corpus is indexed — answer without citations.",
        {"type": "object", "properties": {
            "query": {"type": "string",
                      "description": "Topic/principle to look up in the classics."}},
         "required": ["query"]},
        _classical_texts,
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
    "arudhas": "get_arudha_padas",
    "conditions": "get_planet_conditions",
    "avasthas": "get_avasthas",
    "friendships": "get_friendships",
    "nakshatra": "get_nakshatra_profile",
    "gochara_phala": "get_gochara_phala",
    "sarvatobhadra": "get_sarvatobhadra_chakra",
    "kota": "get_kota_chakra",
    "kaala": "get_kaala_chakra",
    "tripataki": "get_tripataki_chakra",
    # Seeded by default (chart_context renders only the rule-bearing subset), but
    # section-toggled so the tool can still fetch the FULL table — every special
    # lagna, all eleven upagrahas, V1..V12 and the sphutas — on demand.
    "special_points": "get_special_points",
}

# Tools with no section toggle — always available in tool mode so the model can
# fetch the natal base, drill dashas, pull a varga, or read the panchanga.
ALWAYS_TOOLS: List[str] = [
    "get_natal_chart", "get_chart_details", "get_dasha_children",
    "get_divisional_chart", "get_panchanga", "get_varshaphal",
    "get_fortnightly_digest", "get_monthly_digest", "get_tithi_pravesha",
    "get_raja_yogas", "get_nadi", "get_longevity", "get_pancha_pakshi",
    "get_sphuta", "get_sahams", "get_argala",
    "get_vedic_clock", "get_retrograde", "get_muhurta",
    "get_kp", "get_jaimini", "get_life_timeline", "get_strength",
    "get_dasha_periods", "get_sarvatobhadra_chakra", "get_kota_chakra",
    "get_kaala_chakra", "get_tripataki_chakra",
    "get_saturn_transits",
    # get_nakshatra_profile / get_gochara_phala are section-toggled (SECTION_TOOL),
    # not always-on, so their Ask context chips can turn them off.
    "get_journal_entries", "search_classical_texts",
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
    "get_arudha_padas":     {"label": "Arudha padas (AL/UL)",    "category": "Core chart"},
    "get_planet_conditions": {"label": "Planet conditions (combustion, vargottama…)", "category": "Core chart"},
    "get_avasthas":         {"label": "Avasthas (planetary states)", "category": "Core chart"},
    "get_friendships":      {"label": "Planetary friendships & house lords", "category": "Core chart"},
    "get_nakshatra_profile": {"label": "Nakshatra (birth star) profile + tarabala", "category": "Core chart"},
    "get_divisional_chart": {"label": "Divisional (varga) charts", "category": "Core chart"},
    "get_life_timeline":    {"label": "Life timeline (dasha + transits)", "category": "Timing"},
    "get_saturn_transits":  {"label": "Sade Sati & Saturn transits", "category": "Timing"},
    "get_dasha_chain":      {"label": "Running dasha periods",  "category": "Timing"},
    "get_dasha_children":   {"label": "Dasha sub-periods",      "category": "Timing"},
    "get_transits":         {"label": "Current transits (Gochara)", "category": "Timing"},
    "get_gochara_phala":    {"label": "Gochara-phala with vedha (Moon-referenced)", "category": "Timing"},
    "get_panchanga":        {"label": "Panchanga almanac",      "category": "Timing"},
    "get_varshaphal":       {"label": "Varshaphal (annual chart)", "category": "Timing"},
    "get_fortnightly_digest": {"label": "Fortnightly digest (Paksha Pravesha)", "category": "Timing"},
    "get_monthly_digest":   {"label": "Monthly digest (Maasa Pravesha / lunar month)", "category": "Timing"},
    "get_tithi_pravesha":   {"label": "Tithi Pravesha (annual lunar return)", "category": "Timing"},
    "get_pancha_pakshi":    {"label": "Pancha Pakshi timing",  "category": "Timing"},
    "get_vedic_clock":      {"label": "Vedic clock (ghati/hora)", "category": "Timing"},
    "get_retrograde":       {"label": "Retrograde (Vakra) status", "category": "Timing"},
    "get_muhurta":          {"label": "Muhurta (auspicious times)", "category": "Timing"},
    "get_yogas":            {"label": "Yogas",                  "category": "Strengths & afflictions"},
    "get_raja_yogas":       {"label": "Raja Yogas",             "category": "Strengths & afflictions"},
    "get_doshas":           {"label": "Doshas",                 "category": "Strengths & afflictions"},
    "get_ashtakavarga":     {"label": "Ashtakavarga",          "category": "Strengths & afflictions"},
    "get_shadbala":         {"label": "Shadbala strength",      "category": "Strengths & afflictions"},
    "get_strength":         {"label": "Strength (Shadbala + Bhava + Vimsopaka)", "category": "Strengths & afflictions"},
    "get_longevity":        {"label": "Ayu (longevity)",        "category": "Strengths & afflictions"},
    "get_nadi":             {"label": "Nadi karaka reading (significators + timing)", "category": "Systems"},
    "get_sphuta":           {"label": "Sphutas (sensitive points)", "category": "Sensitive points"},
    "get_special_points":   {"label": "Special lagnas & upagrahas (Hora/Ghati/Varnada, Gulika…)",
                             "category": "Sensitive points"},
    "get_sahams":           {"label": "Sahams (36 points)",     "category": "Sensitive points"},
    "get_argala":           {"label": "Argala (intervention)",  "category": "Sensitive points"},
    "get_dasha_periods":    {"label": "Other dasha systems (Chara, Yogini, Sudarshana Chakra…)", "category": "Timing"},
    "get_sarvatobhadra_chakra": {"label": "Sarvatobhadra Chakra (transits + vedha)", "category": "Chakras"},
    "get_kota_chakra":      {"label": "Kota Chakra (the fort — protection)", "category": "Chakras"},
    "get_kaala_chakra":     {"label": "Kaala Chakra (wheel of directions)", "category": "Chakras"},
    "get_tripataki_chakra": {"label": "Tripataki Chakra (vedha on Moon + Lagna)", "category": "Chakras"},
    "get_kp":               {"label": "KP sub-lords & significators", "category": "Systems"},
    "get_jaimini":          {"label": "Jaimini (Karakamsa)",     "category": "Systems"},
    "get_journal_entries":  {"label": "Astro-journal (your logged life events)", "category": "Your data"},
    "search_classical_texts": {"label": "Classical texts (cited shlokas)", "category": "Sources"},
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
