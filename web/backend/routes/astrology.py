"""Astrology compute endpoints (charts, dashas, panchanga, muhurta, transits, …).

Part of the §4b main.py split — handlers moved verbatim; only the
decorator changed from @app.* to @router.*.
"""
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse, Response
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any
import json
import re
from pydantic import BaseModel

from config import settings
from database import connect_to_mongo, close_mongo_connection
from auth import create_access_token, decode_token, get_password_hash, verify_password, Token
from database import User, BirthDetails, ChartData
from astrology import AstrologyCompute, SUPPORTED_AYANAMSAS, DEFAULT_AYANAMSA, SUPPORTED_VARGAS, SUPPORTED_DASHAS
from chart_context import build_chart_context
from llm_service import llm_service, LLMProvider
import tools as tool_registry
import conversations as convo
import journal
import ical
import tool_traces
import user_settings
import ratelimit
import shares
import quiz
import refresh_tokens
import api_tokens
import password_reset
import email_service
import notifications
import digest as digest_service
import scheduler
import uuid
from fastapi import APIRouter
from models import *  # noqa: F401,F403
from deps import *  # noqa: F401,F403
import deps as _deps

router = APIRouter()


# ============= ASTROLOGY ROUTES =============

@router.post("/api/astrology/birth-chart")
async def calculate_birth_chart(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Calculate birth chart for given details"""
    try:
        from database import database

        chart = AstrologyCompute.get_birth_chart(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa
        )

        charts_collection = database["charts"]
        chart_doc = {
            "user_id": current_user,
            "birth_details": birth_details.model_dump(),
            "chart_type": "rasi",
            "planets_positions": chart.get("planets", {}),
            "houses": chart.get("houses", {})
        }
        result = await charts_collection.insert_one(chart_doc)
        chart["_id"] = str(result.inserted_id)
        
        return chart
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/ayanamsas")
async def list_ayanamsas():
    """Supported ayanamsa options for chart calculation."""
    return {
        "default": DEFAULT_AYANAMSA,
        "options": [{"value": k, "label": v} for k, v in SUPPORTED_AYANAMSAS.items()],
    }

@router.get("/api/astrology/vargas")
async def list_vargas():
    """Supported divisional (varga) charts for the varga picker."""
    return {
        "options": [
            {"value": factor, "code": code, "name": name, "significance": significance}
            for factor, (code, name, significance) in SUPPORTED_VARGAS.items()
        ]
    }

@router.post("/api/astrology/divisional-chart")
async def calculate_divisional_chart(
    birth_details: BirthDetails,
    varga: int = 9,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Calculate a single divisional (varga) chart, e.g. varga=10 for Dasamsa."""
    try:
        chart = AstrologyCompute.calculate_divisional_chart(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            varga_factor=varga,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa,
        )
        if chart.get("status") != "success":
            raise HTTPException(status_code=400, detail=chart.get("error", "Calculation failed"))
        return chart
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/panchanga")
async def get_panchanga(
    date: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    system: str = "drik",
    current_user: str = Depends(get_current_user),
):
    """Daily almanac (panchanga) for a place and optional date (defaults to
    today at that place). Used by the 'Today' panel. `system` = drik (default)
    or surya_siddhanta (classical ayanamsa engine); response also includes the
    Hijri (Islamic) date."""
    try:
        panchanga = AstrologyCompute.get_panchanga(
            date=date,
            place=place,
            lat=latitude,
            lon=longitude,
            tz=timezone,
            system=system,
        )
        if panchanga.get("status") != "success":
            raise HTTPException(status_code=400, detail=panchanga.get("error", "Calculation failed"))
        return panchanga
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/almanac/hora")
async def get_planetary_hours(
    date: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    current_user: str = Depends(get_current_user),
):
    """Planetary hours (hora) table for a place and optional date (defaults to
    today at that place)."""
    try:
        result = AstrologyCompute.get_planetary_hours(
            date=date, place=place, lat=latitude, lon=longitude, tz=timezone,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/almanac/eclipses")
async def get_eclipses(
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    from_date: Optional[str] = None,
    count: int = 3,
    current_user: str = Depends(get_current_user),
):
    """Upcoming solar + lunar eclipses (global visibility) from a date, in the
    place's local time."""
    try:
        result = AstrologyCompute.get_eclipses(
            place=place, lat=latitude, lon=longitude, tz=timezone,
            from_date=from_date, count=count,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/almanac/festivals")
async def get_festivals(
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    types: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """Tithi-driven festival / vratha dates in a range. `types` is a comma-
    separated list of festival keys (defaults to the common bundle)."""
    try:
        type_list = [t.strip() for t in types.split(",") if t.strip()] if types else None
        result = AstrologyCompute.get_festival_dates(
            place=place, lat=latitude, lon=longitude, tz=timezone,
            start=start, end=end, types=type_list,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/almanac/conjunctions")
async def get_conjunctions(
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    max_sep: float = 3.0,
    current_user: str = Depends(get_current_user),
):
    """Planetary conjunctions (Graha Yuddha) among Mars–Saturn in a date range,
    within `max_sep` degrees; each event carries the closest approach + a war
    flag (<1°)."""
    try:
        result = AstrologyCompute.get_conjunctions(
            place=place, lat=latitude, lon=longitude, tz=timezone,
            start=start, end=end, max_sep=max_sep,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/sensitive-points")
async def get_sensitive_points(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Sensitive points of the natal chart: the classical Sphutas, the 36 natal
    Sahams, and the Argala / Virodhargala per bhava. Aggregated for one page."""
    try:
        args = dict(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        sphuta = AstrologyCompute.get_sphuta(**args)
        sahams = AstrologyCompute.get_sahams(**args)
        argala = AstrologyCompute.get_argala(**args)
        if sphuta.get("status") != "success":
            raise HTTPException(status_code=400, detail=sphuta.get("error", "Calculation failed"))
        return {"status": "success", "sphuta": sphuta, "sahams": sahams, "argala": argala}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/vedic-clock")
async def get_vedic_clock(
    date: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    current_user: str = Depends(get_current_user),
):
    """Vedic day-clock data (sunrise/sunset, ghati/vighati, running hora lord,
    panchanga limbs) for a place + optional date. Drives the live clock face."""
    try:
        result = AstrologyCompute.get_vedic_clock(
            date=date, place=place, lat=latitude, lon=longitude, tz=timezone,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/retrograde")
async def get_retrograde(
    date: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    current_user: str = Depends(get_current_user),
):
    """Retrograde (Vakra) status: which grahas are retrograde now, the next
    station dates, and the Vakra-gathi epicycle loop (x,y) for each planet."""
    try:
        result = AstrologyCompute.get_retrograde(
            date=date, place=place, lat=latitude, lon=longitude, tz=timezone,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/birth-chart/{chart_id}")
async def get_birth_chart(chart_id: str, current_user: str = Depends(get_current_user)):
    """Retrieve stored birth chart"""
    try:
        from database import database
        from bson import ObjectId
        
        charts_collection = database["charts"]
        chart = await charts_collection.find_one({
            "_id": ObjectId(chart_id),
            "user_id": current_user
        })
        
        if not chart:
            raise HTTPException(status_code=404, detail="Chart not found")
        
        chart["_id"] = str(chart["_id"])
        return chart
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/horoscope")
async def get_horoscope(
    birth_details: BirthDetails,
    current_user: str = Depends(get_current_user)
):
    """Get the deterministic horoscope chart data (lagna, moon/sun signs,
    planetary positions). For an AI-written reading use /api/astrology/predict,
    which runs through the unified LLM service (Ollama/OpenAI/Gemini)."""
    try:
        chart_data = AstrologyCompute.get_horoscope_predictions(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone
        )
        return chart_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/doshas")
async def get_doshas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Get doshas"""
    try:
        doshas = AstrologyCompute.get_doshas(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa
        )
        return doshas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/yogas")
async def get_yogas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    lang: str = "en",
    current_user: str = Depends(get_current_user)
):
    """Get yogas. `lang` localizes the yoga names and descriptions (sa -> hi)."""
    try:
        yogas = AstrologyCompute.get_yogas(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa,
            lang=lang
        )
        return yogas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/dhasa")
async def get_dhasa(
    birth_details: BirthDetails,
    dhasa_type: str = "vimsottari",
    current_user: str = Depends(get_current_user)
):
    """Get Dasha periods"""
    try:
        dhasa = AstrologyCompute.get_dashas(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            dhasa_type=dhasa_type
        )
        return dhasa
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/dhasa/children")
async def get_dhasa_children(
    birth_details: BirthDetails,
    lords: str = "",
    current_user: str = Depends(get_current_user)
):
    """Lazily fetch the immediate child periods (Antara/Sookshma) of a Vimsottari
    node. `lords` is a comma-separated lord-path, e.g. `Venus,Saturn`."""
    try:
        lords_path = [p.strip() for p in lords.split(",") if p.strip()]
        result = AstrologyCompute.get_dasha_children(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            lords_path=lords_path,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/dasha-systems")
async def list_dasha_systems(current_user: str = Depends(get_current_user)):
    """List the supported non-Vimsottari dasha systems."""
    return {
        "systems": [
            {"key": k, "name": v["name"], "lord_type": v["lord_type"],
             "description": v["description"]}
            for k, v in SUPPORTED_DASHAS.items()
        ]
    }

@router.post("/api/astrology/applicable-dashas")
async def get_applicable_dashas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Which conditional Vimsottari-family dashas classically apply to this chart
    (BPHS applicability rules) — so the Dhasa page can recommend them."""
    try:
        result = AstrologyCompute.get_applicable_dashas(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/dasha-periods")
async def get_dasha_periods(
    birth_details: BirthDetails,
    dhasa_type: str,
    current_user: str = Depends(get_current_user)
):
    """Maha-level periods for one of the non-Vimsottari dasha systems
    (ashtottari/yogini/narayana/kalachakra)."""
    try:
        result = AstrologyCompute.get_dasha_periods(
            dhasa_type=dhasa_type,
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/ashtakavarga")
async def get_ashtakavarga(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Bhinna + Sarva Ashtakavarga bindu tables."""
    try:
        result = AstrologyCompute.get_ashtakavarga(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/aspects")
async def get_aspects(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Graha drishti (planetary aspects) + rasi drishti + sphuta aspect strength."""
    try:
        result = AstrologyCompute.get_aspects(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/varshaphal")
async def get_varshaphal(
    birth_details: BirthDetails,
    year: int,
    ayanamsa: str = DEFAULT_AYANAMSA,
    dasha_system: str = "mudda",
    current_user: str = Depends(get_current_user)
):
    """Varshaphal / Tajaka annual (solar-return) horoscope for a target year."""
    try:
        result = AstrologyCompute.get_varshaphal(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            year=year,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
            dasha_system=dasha_system,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/raja-yogas")
async def get_raja_yogas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    lang: str = "en",
    current_user: str = Depends(get_current_user)
):
    """Dedicated Raja Yoga analysis (Kendra-Trikona pairs + named special types).

    `lang` localizes the named raja-yoga names and descriptions (sa -> hi).
    """
    try:
        result = AstrologyCompute.get_raja_yogas(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa, lang=lang,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/longevity")
async def get_longevity(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Ayu (longevity) category — Alpa/Madhya/Purna — with contributing factors.
    Returns a conditional category and its factors, never a death date/age."""
    try:
        result = AstrologyCompute.get_longevity(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/sudarsana-chakra")
async def get_sudarsana_chakra(
    birth_details: BirthDetails,
    year_offset: int = 0,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Sudarsana Chakra — three wheels (Lagna/Moon/Sun ascendants) for the
    solar-return year `year_offset` past birth (0 = natal)."""
    try:
        result = AstrologyCompute.get_sudarsana_chakra(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa, year_offset=year_offset,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/pancha-pakshi")
async def get_pancha_pakshi(
    birth_details: BirthDetails,
    date: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """Pancha Pakshi Sastra — birth bird + the day's activity-strength timeline."""
    try:
        result = AstrologyCompute.get_pancha_pakshi(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, date=date,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/rectify-birth-time")
async def rectify_birth_time(
    birth_details: BirthDetails,
    method: str = "nakshatra",
    gender: Optional[int] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """EXPERIMENTAL birth-time rectification (BV Raman suddhi methods). Suggests a
    corrected birth time within +/-30 min and returns before/after chart summaries.
    method: nakshatra | lagna | janma (janma needs gender: 0=male, 1=female)."""
    try:
        result = AstrologyCompute.get_birth_time_rectification(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
            method=method, gender=gender,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/rectify-birth-time/events")
async def rectify_birth_time_by_events(
    request: RectifyEventsRequest,
    current_user: str = Depends(get_current_user)
):
    """EXPERIMENTAL event-based birth-time rectification. Scans candidate times and
    picks the one whose Vimsottari dasha + Jupiter/Saturn transits best match the
    supplied dated life events (deterministic, auditable per-event matches)."""
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_event_rectification(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            events=[e.model_dump() for e in request.events],
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            window_minutes=request.window_minutes,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/chart-details")
async def get_chart_details(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Advanced chart factors: Arudha padas, Chara karakas, Special lagnas, Upagrahas."""
    try:
        result = AstrologyCompute.get_chart_details(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/shadbala")
async def get_shadbala(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Shadbala (six-fold planetary strength) for Sun..Saturn."""
    try:
        result = AstrologyCompute.get_shadbala(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/share")
async def create_share_link(
    request: ShareRequest,
    current_user: str = Depends(get_current_user)
):
    """Create a read-only share token for a chart (birth details + ayanamsa)."""
    try:
        token = await shares.create_share(
            user_id=current_user,
            profile_name=request.profile_name,
            birth_details=request.birth_details.model_dump(),
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
        return {"token": token, "path": f"/share/{token}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/astrology/share/{token}")
async def get_shared_chart(token: str):
    """Public, read-only: recompute and return the shared chart. No auth."""
    try:
        share = await shares.get_share(token)
        if not share:
            raise HTTPException(status_code=404, detail="Shared chart not found")
        bd = share.get("birth_details", {})
        ayanamsa = share.get("ayanamsa", DEFAULT_AYANAMSA)
        chart = AstrologyCompute.calculate_birth_chart(
            dob=bd.get("dob"), tob=bd.get("tob"), place=bd.get("place"),
            lat=bd.get("latitude"), lon=bd.get("longitude"),
            tz=bd.get("timezone"), ayanamsa=ayanamsa,
        )
        if chart.get("error"):
            raise HTTPException(status_code=400, detail=chart.get("error"))
        return {
            "profile_name": share.get("profile_name"),
            "ayanamsa": ayanamsa,
            "birth_details": {
                "name": bd.get("name"),
                "dob": bd.get("dob"),
                "tob": bd.get("tob"),
                "place": bd.get("place"),
            },
            "chart": chart,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/transit")
async def get_transits(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Get current transits (Gochara) over the natal chart"""
    try:
        transits = AstrologyCompute.get_transits(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            current_date=current_date,
            current_time=current_time,
            current_tz=current_tz,
            ayanamsa=ayanamsa
        )
        if transits.get("status") != "success":
            raise HTTPException(status_code=400, detail=transits.get("error", "Calculation failed"))
        return transits
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/bhava-chart")
async def get_bhava_chart(
    birth_details: BirthDetails,
    method: str = "SRIPATI",
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Bhava (house-cusp) chart — Bhava Chalit / cuspal division (Sripati, Placidus,
    KP, Equal). Returns each bhava's start/cusp/end longitudes + occupants, plus a
    `planets` map for the Kundali component (Bhava Chalit rendering)."""
    try:
        result = AstrologyCompute.get_bhava_chart(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            method=method,
            ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/astrology/ephemeris")
async def get_ephemeris(
    start_date: str,
    days: int = 30,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Sidereal ephemeris + ingress calendar over a date window (max 92 days).
    Each day carries every graha's sign/degree/retrograde at local noon; ingresses
    list the sign changes. Powers the transit-calendar / ephemeris view."""
    try:
        result = AstrologyCompute.get_ephemeris(
            start_date=start_date,
            days=days,
            place=place,
            lat=latitude,
            lon=longitude,
            tz=timezone,
            ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/compatibility")
async def get_compatibility(
    request: CompatibilityRequest,
    current_user: str = Depends(get_current_user)
):
    """Calculate compatibility"""
    try:
        compatibility = AstrologyCompute.get_compatibility(
            male_dob=request.male_dob,
            male_tob=request.male_tob,
            male_place=request.male_place,
            male_lat=request.male_latitude,
            male_lon=request.male_longitude,
            female_dob=request.female_dob,
            female_tob=request.female_tob,
            female_place=request.female_place,
            female_lat=request.female_latitude,
            female_lon=request.female_longitude,
            male_tz=request.male_timezone,
            female_tz=request.female_timezone,
            tz=request.male_timezone or request.female_timezone or 5.5
        )
        # AI compatibility analysis lives at /api/astrology/compatibility-analysis
        # (unified LLM service); this endpoint returns the deterministic score only.
        return compatibility
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/marriage-workspace")
async def get_marriage_workspace(
    request: MarriageWorkspaceRequest,
    current_user: str = Depends(get_current_user)
):
    """7th-house marriage deep-dive for both partners (§2.6 workspace)."""
    try:
        m = request.male_details
        f = request.female_details
        return AstrologyCompute.get_marriage_workspace(
            male_dob=m.dob, male_tob=m.tob, male_place=m.place,
            male_lat=m.latitude, male_lon=m.longitude, male_tz=m.timezone,
            female_dob=f.dob, female_tob=f.tob, female_place=f.place,
            female_lat=f.latitude, female_lon=f.longitude, female_tz=f.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/ask")
async def ask_question(
    request: AskQuestionRequest,
    current_user: str = Depends(get_current_user)
):
    """Ask a question about the birth chart using AI"""
    _enforce_rate_limit(current_user)
    try:
        # Build the rich, structured chart context (D1 + running dasha chain +
        # yogas + doshas + transits), token-budgeted and section-toggleable.
        chart_data = build_chart_context(
            birth_details=request.birth_details.model_dump(),
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            sections=request.sections,
            vargas=request.vargas,
        )

        # Resolve the model config (request key → user's stored key → env key)
        cfg = await _resolve_cfg(current_user, request)

        # Multi-turn: load prior turns from the conversation (if any)
        conv = await convo.get_conversation(current_user, request.conversation_id) \
            if request.conversation_id else None
        history = convo.history_for_model(conv)
        mode = _resolve_mode(request, conv)

        # Get AI response
        started = datetime.now(timezone.utc)
        usage: dict = {}
        tool_trace: list = []
        if mode == "tools":
            # Drain the tool loop, collecting the final answer + the call trace.
            seed_block = llm_service._render_context_block(chart_data, tool_mode=True)
            bd = request.birth_details.model_dump()
            parts = []
            async for ev in llm_service.run_tool_loop(
                    seed_block, request.question, history, cfg, bd,
                    request.ayanamsa or DEFAULT_AYANAMSA,
                    tool_names=tool_registry.tool_names_for_sections(request.sections),
                    usage=usage):
                et = ev.get("type")
                if et == "token":
                    parts.append(ev["text"])
                elif et == "tool_call":
                    tool_trace.append({"name": ev["name"], "args": ev.get("args", {})})
                elif et == "tool_result":
                    for tr in reversed(tool_trace):
                        if tr["name"] == ev["name"] and "ok" not in tr:
                            tr["ok"] = ev["ok"]
                            tr["result"] = ev.get("result")
                            break
            answer = "".join(parts)
        else:
            answer = await llm_service.ask_question(
                chart_data=chart_data,
                question=request.question,
                config=cfg,
                history=history,
                usage=usage,
            )
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

        # Persist the turn (create the conversation on first message)
        conv_id = await _save_turn(current_user, request, cfg, chart_data, answer,
                                   elapsed_ms=elapsed_ms, usage=usage or None,
                                   mode=mode, tool_trace=tool_trace or None)

        return {
            "question": request.question,
            "answer": answer,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
            "mode": mode,
            "elapsed_ms": elapsed_ms,
            "usage": usage or None,
            "conversation_id": conv_id,
            "sections": chart_data.get("_sections", {}),
            "vargas": chart_data.get("_vargas", []),
            "tool_trace": tool_trace,
            "context": chart_data,  # full structured context (for the "what was sent" view)
            "chart_summary": {
                "lagna": chart_data.get("lagna", {}),
                "moon_sign": chart_data.get("moon_sign", {}),
                "sun_sign": chart_data.get("sun_sign", {})
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/ask/stream")
async def ask_question_stream(
    request: AskQuestionRequest,
    current_user: str = Depends(get_current_user)
):
    """Stream an answer token-by-token (SSE), with multi-turn context, and persist
    the completed turn. Frontend reads this with a fetch + ReadableStream."""
    _enforce_rate_limit(current_user)
    # Build context + resolve model up front so failures surface as HTTP errors.
    chart_data = build_chart_context(
        birth_details=request.birth_details.model_dump(),
        ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        sections=request.sections,
        vargas=request.vargas,
    )
    cfg = await _resolve_cfg(current_user, request)
    conv = await convo.get_conversation(current_user, request.conversation_id) \
        if request.conversation_id else None
    history = convo.history_for_model(conv)
    mode = _resolve_mode(request, conv)

    async def event_gen():
        # Tell the client which conversation + model + mode up front.
        meta = {
            "type": "meta",
            "conversation_id": request.conversation_id,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
            "mode": mode,
            "sections": chart_data.get("_sections", {}),
            "vargas": chart_data.get("_vargas", []),
            "context": chart_data,  # exact structured context (seed, in tool mode)
        }
        yield f"data: {json.dumps(meta)}\n\n"

        parts = []
        tool_trace: list = []
        usage: dict = {}
        started = datetime.now(timezone.utc)
        try:
            if mode == "tools":
                # Seed = the toggled-on sections; the model fetches the rest via tools.
                seed_block = llm_service._render_context_block(chart_data, tool_mode=True)
                bd = request.birth_details.model_dump()
                # Inject the user's journal so get_journal_entries can serve it
                # synchronously inside the (sync) tool dispatch. Best-effort.
                try:
                    bd["_journal"] = await journal.entries_for_ai(current_user, request.profile_id)
                except Exception:
                    bd["_journal"] = []
                async for ev in llm_service.run_tool_loop(
                        seed_block, request.question, history, cfg, bd,
                        request.ayanamsa or DEFAULT_AYANAMSA,
                        tool_names=tool_registry.tool_names_for_sections(request.sections),
                        usage=usage):
                    et = ev.get("type")
                    if et == "token":
                        parts.append(ev["text"])
                    elif et == "tool_call":
                        tool_trace.append({"name": ev["name"], "args": ev.get("args", {})})
                    elif et == "tool_result":
                        for tr in reversed(tool_trace):
                            if tr["name"] == ev["name"] and "ok" not in tr:
                                tr["ok"] = ev["ok"]
                                tr["result"] = ev.get("result")
                                break
                    yield f"data: {json.dumps(ev)}\n\n"
            else:
                async for chunk in llm_service.stream_answer(chart_data, request.question,
                                                             history, cfg, usage=usage):
                    parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        answer = "".join(parts)
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        usage = usage or None
        try:
            conv_id = await _save_turn(current_user, request, cfg, chart_data, answer,
                                       elapsed_ms=elapsed_ms, usage=usage, mode=mode,
                                       tool_trace=tool_trace or None)
        except Exception as e:
            conv_id = request.conversation_id
            print(f"Failed to persist conversation: {e}")
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv_id, 'elapsed_ms': elapsed_ms, 'usage': usage})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@router.post("/api/astrology/predict")
async def generate_prediction(
    request: PredictionRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate AI-powered predictions"""
    _enforce_rate_limit(current_user)
    try:
        # Build the rich, structured chart context (same path as /ask):
        # D1 + running dasha chain + yogas + doshas + transits + selected vargas.
        chart_data = build_chart_context(
            birth_details=request.birth_details.model_dump(),
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            sections=request.sections,
            vargas=request.vargas,
        )

        # Resolve the model config (request key → user's stored key → env key)
        cfg = await _resolve_cfg(current_user, request)

        # Generate prediction
        prediction = await llm_service.generate_prediction(
            chart_data=chart_data,
            prediction_type=request.prediction_type,
            config=cfg,
        )

        await _save_reading(
            current_user, source="prediction",
            title=f"Prediction ({request.prediction_type}) — {request.birth_details.name or 'chart'}",
            text=prediction, cfg=cfg, profile_id=request.profile_id,
            birth_details=request.birth_details.model_dump(),
            context={"prediction_type": request.prediction_type,
                     "ayanamsa": request.ayanamsa},
        )
        return {
            "prediction_type": request.prediction_type,
            "prediction": prediction,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
            "chart_data": chart_data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= SARVATOBHADRA CHAKRA =============

@router.post("/api/astrology/kaala-chakra")
async def get_kaala_chakra(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Kaala Chakra — the wheel of directions with today's transits on it (§2.7)."""
    try:
        r = AstrologyCompute.get_kaala_chakra(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude, tz=birth_details.timezone,
            current_date=current_date, current_time=current_time,
            current_tz=current_tz, ayanamsa=ayanamsa,
        )
        if r.get("status") != "success":
            raise HTTPException(status_code=400, detail=r.get("error", "Calculation failed"))
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/kota-chakra")
async def get_kota_chakra(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Kota Chakra (the fort) with today's transits marked on its four rings (§2.7)."""
    try:
        r = AstrologyCompute.get_kota_chakra(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude, tz=birth_details.timezone,
            current_date=current_date, current_time=current_time,
            current_tz=current_tz, ayanamsa=ayanamsa,
        )
        if r.get("status") != "success":
            raise HTTPException(status_code=400, detail=r.get("error", "Calculation failed"))
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/tripataki-chakra")
async def get_tripataki_chakra(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    basis: str = "transit",
    year: Optional[int] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Tripataki Chakra with vedha on the Moon + Lagna (§2.7).

    `basis=transit` (default) reads the chosen moment; `basis=annual` reads the
    Varshaphal (solar-return) chart for `year` — Tripataki's classical home."""
    try:
        r = AstrologyCompute.get_tripataki_chakra(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude, tz=birth_details.timezone,
            current_date=current_date, current_time=current_time,
            current_tz=current_tz, basis=basis, year=year, ayanamsa=ayanamsa,
        )
        if r.get("status") != "success":
            raise HTTPException(status_code=400, detail=r.get("error", "Calculation failed"))
        return r
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/sarvatobhadra")
async def get_sarvatobhadra(
    birth_details: BirthDetails,
    name_nakshatra: Optional[int] = None,
    current_date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Sarvatobhadra Chakra with today's transits + vedha on the native's stars."""
    try:
        sbc = AstrologyCompute.get_sarvatobhadra_chakra(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude, tz=birth_details.timezone,
            name_nakshatra=name_nakshatra, current_date=current_date,
            current_time=current_time, current_tz=current_tz, ayanamsa=ayanamsa,
        )
        if sbc.get("status") != "success":
            raise HTTPException(status_code=400, detail=sbc.get("error", "Calculation failed"))
        return sbc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= MUHURTA / PRASHNA / DAILY DIGEST (§16) =============

@router.post("/api/astrology/muhurta")
async def get_muhurta(
    activity: str = "general",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    current_user: str = Depends(get_current_user),
):
    """Auspicious windows for an activity over a date range (electional astrology).
    Location-driven; not tied to a birth chart."""
    try:
        result = AstrologyCompute.get_muhurta(
            activity=activity, start_date=start_date, end_date=end_date,
            place=place, lat=latitude, lon=longitude, tz=timezone)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/muhurta/subtools")
async def get_muhurta_subtools(
    request: MuhurtaSubtoolsRequest,
    current_user: str = Depends(get_current_user),
):
    """Day-level muhurta helpers: Choghadiya + Panchaka (location) and, when
    birth details are supplied, personal Tarabala + Chandrabala."""
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_muhurta_subtools(
            date=request.date, place=request.place,
            lat=request.latitude, lon=request.longitude, tz=request.timezone,
            birth_dob=bd.dob if bd else None,
            birth_tob=bd.tob if bd else None,
            birth_lat=bd.latitude if bd else None,
            birth_lon=bd.longitude if bd else None,
            birth_tz=bd.timezone if bd else None,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/prashna")
async def get_prashna(
    question: Optional[str] = None,
    date: Optional[str] = None,
    time: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    ayanamsa: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """Cast a Prashna (horary) chart for a moment (defaults to now + here)."""
    try:
        result = AstrologyCompute.get_prashna(
            question=question, date=date, time=time, place=place,
            lat=latitude, lon=longitude, tz=timezone,
            ayanamsa=ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/daily-digest")
async def get_daily_digest(
    birth_details: BirthDetails,
    date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    basis: str = "solar",
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Personalized 'Today' digest — panchanga + dasha + headline transits.
    `basis=lunar` additionally casts the day's tithi-pravesha chart."""
    try:
        result = AstrologyCompute.get_daily_digest(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, date=date, current_time=current_time,
            current_tz=current_tz, basis=_basis(basis), ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/fortnightly-digest")
async def get_fortnightly_digest(
    birth_details: BirthDetails,
    date: Optional[str] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Personalized 'This Fortnight' reading — dasha context + the running paksha's
    transit events, anchored to that paksha's Pravesha chart (~14.8 days)."""
    try:
        result = AstrologyCompute.get_fortnightly_digest(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, date=date, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/monthly-digest")
async def get_monthly_digest(
    birth_details: BirthDetails,
    date: Optional[str] = None,
    basis: str = "solar",
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Personalized 'This Month' reading. `basis=solar` anchors to the Maasa
    Pravesha (Tajaka monthly solar return, ~30.4d); `basis=lunar` anchors to the
    birth-tithi return (lunar month, ~29.5d)."""
    try:
        result = AstrologyCompute.get_monthly_digest(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, date=date, basis=_basis(basis), ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/tithi-pravesha")
async def get_tithi_pravesha(
    birth_details: BirthDetails,
    year: Optional[int] = None,
    date: Optional[str] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Tithi Pravesha — the annual *lunar*-return chart (natal tithi + lunar month
    recurring, ~354 days). The lunar counterpart of Varshaphal's solar return."""
    try:
        result = AstrologyCompute.get_tithi_pravesha(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, year=year, date=date, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/lunar-pravesha")
async def get_lunar_pravesha(
    birth_details: BirthDetails,
    rung: str = "annual",
    year: Optional[int] = None,
    date: Optional[str] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """A chart anywhere on the **lunar (tithi) pravesha ladder** — the Tithi Pravesha
    page's one endpoint.

    `rung` picks the window: `tithi` (the running tithi, ~1d), `paksha` (the lunar
    fortnight, ~14.8d), `month` (the birth-tithi return, ~29.5d), or `annual` (the
    natal tithi *and* lunar month recurring — the TP chart proper, ~354/384d).

    Each returns the chart cast at the instant the window opens, plus that window's
    **compressed Tithi Ashtottari**. `year` targets a specific annual window; `date`
    selects whichever window contains it (and is how the ± stepper walks the ladder).
    The year-reckoned panels — Muntha, year-lord, Sahams — are meaningful only on the
    annual rung and are omitted below it."""
    if rung not in _LUNAR_RUNGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown rung '{rung}' — expected one of {', '.join(_LUNAR_RUNGS)}")
    try:
        result = AstrologyCompute.get_lunar_pravesha(
            rung, dob=birth_details.dob, tob=birth_details.tob,
            place=birth_details.place, lat=birth_details.latitude,
            lon=birth_details.longitude, tz=birth_details.timezone,
            year=year, date=date, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/tithi-ashtottari-children")
async def get_tithi_ashtottari_children(
    request: TithiAshtottariChildrenRequest,
    current_user: str = Depends(get_current_user),
):
    """The eight sub-periods of one Tithi Ashtottari period — one level of the
    dasha tree, computed on expand. The full six levels (Maha → … → Deha) would be
    8⁶ ≈ 262k rows, so they are never sent whole."""
    try:
        result = AstrologyCompute.get_tithi_ashtottari_children(
            start_jd=request.start_jd, lord=request.lord, span_deg=request.span_deg,
            level=request.level, lat=request.latitude, lon=request.longitude,
            tz=request.timezone, place=request.place)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= NADI / BHRIGU YEARLY MARKERS + REMEDIES =============

@router.post("/api/astrology/bhrigu-markers")
async def get_bhrigu_markers(
    birth_details: BirthDetails,
    from_age: Optional[int] = None,
    years: int = 12,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Nadi / Bhrigu-style yearly markers: the Moon-based annual progression +
    the Bhrigu Bindu and its Jupiter/Saturn activations."""
    try:
        result = AstrologyCompute.get_bhrigu_markers(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, from_age=from_age, years=years, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/life-timeline")
async def get_life_timeline(
    birth_details: BirthDetails,
    years_before: int = 10,
    years_after: int = 10,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """The composed dasha–transit life timeline: Vimsottari maha/bhukti bands,
    Sade Sati / Shani phases, Jupiter/Saturn/Rahu ingresses and flagged eclipses
    over a window around today."""
    try:
        result = AstrologyCompute.get_life_timeline(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, years_before=years_before,
            years_after=years_after, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/planet-conditions")
async def get_planet_conditions(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Classical planet-condition flags — combustion, vargottama, pushkara,
    mrityu bhaga, marana karaka, gandanta, graha yuddha, retrograde."""
    try:
        result = AstrologyCompute.get_planet_conditions(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/saturn-transits")
async def get_saturn_transits(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Sade Sati cycles (with phase windows + retrograde re-entries), Ashtama and
    Kantaka Shani periods, and the current Saturn status from the natal Moon."""
    try:
        result = AstrologyCompute.get_saturn_transits(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/strength")
async def get_strength(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """The full strength picture: Shadbala (six-fold), Bhava Bala (house strength)
    and Vimsopaka Bala (varga dignity, 0-20)."""
    try:
        result = AstrologyCompute.get_strength(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/nakshatra-profile")
async def get_nakshatra_profile(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Janma-nakshatra deep-dive: the Moon's nakshatra + pada with its classical
    attributes and a 27-day tarabala calendar strip."""
    try:
        result = AstrologyCompute.get_nakshatra_profile(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, current_date=current_date, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/gochara-phala")
async def get_gochara_phala(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Classical Moon-referenced gochara-phala with vedha (obstruction) for the
    current transits."""
    try:
        result = AstrologyCompute.get_gochara_phala(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, current_date=current_date,
            current_tz=current_tz, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── Composed long-form Life Report (§5.11) ──────────────────────────────────
@router.get("/api/astrology/life-report/chapters")
async def life_report_chapters(current_user: str = Depends(get_current_user)):
    """The ordered chapter list the frontend generates one-by-one (with progress)."""
    return {"chapters": [{"key": k, "title": title}
                         for (k, title, _focus) in llm_service.LIFE_REPORT_CHAPTERS]}

@router.post("/api/astrology/life-report/chapter")
async def life_report_chapter(
    request: LifeReportChapterRequest,
    current_user: str = Depends(get_current_user),
):
    """Generate a single Life Report chapter (personality/career/…)."""
    _enforce_rate_limit(current_user)
    chapter = next((c for c in llm_service.LIFE_REPORT_CHAPTERS
                    if c[0] == request.chapter_key), None)
    if not chapter:
        raise HTTPException(status_code=400, detail="Unknown chapter")
    _key, title, focus = chapter
    try:
        chart_data = build_chart_context(
            birth_details=request.birth_details.model_dump(),
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            sections=request.sections, vargas=request.vargas)
        cfg = await _resolve_cfg(current_user, request)
        text = await llm_service.generate_life_report_chapter(
            chart_data=chart_data, title=title, focus=focus,
            name=request.person_name or request.birth_details.name or "this person",
            config=cfg)
        return {"key": _key, "title": title, "text": text,
                "provider": cfg.provider_type.value, "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/life-report/save")
async def life_report_save(
    request: LifeReportSaveRequest,
    current_user: str = Depends(get_current_user),
):
    """Persist a finished Life Report (assembled markdown) to the unified history."""
    try:
        cfg = await _resolve_cfg(current_user, request)
        await _save_reading(
            current_user, source="life_report",
            title=f"Life Report — {request.person_name or request.birth_details.name or 'chart'}",
            text=request.markdown, cfg=cfg, profile_id=request.profile_id,
            birth_details=request.birth_details.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa})
        return {"status": "saved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/friendships")
async def get_friendships(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Compound planetary friendships, house-lord placements and Parivartana
    (mutual sign exchange) for this chart."""
    try:
        result = AstrologyCompute.get_friendships(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/avasthas")
async def get_avasthas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Planetary avasthas (states) for the seven grahas — Baladi, Jagradadi and
    Deeptadi, computed from longitude + dignity."""
    try:
        result = AstrologyCompute.get_avasthas(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/remedies")
async def get_remedies(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Traditional remedial suggestions per weak / afflicted planet (dignity +
    shadbala driven). Clearly labelled traditional guidance, not advice."""
    try:
        result = AstrologyCompute.get_remedies(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= KP (KRISHNAMURTI PADDHATI) · JAIMINI · NOW-CHART (§16) =============

@router.post("/api/astrology/kp")
async def get_kp(
    birth_details: BirthDetails,
    current_user: str = Depends(get_current_user),
):
    """KP natal: sub-lords, cuspal sub-lords, significators, ruling planets."""
    try:
        result = AstrologyCompute.get_kp_details(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/kp-horary")
async def get_kp_horary(
    number: int,
    date: Optional[str] = None,
    time: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    current_user: str = Depends(get_current_user),
):
    """KP horary (Prasna) chart for a number 1-249 (cast for now + here)."""
    try:
        result = AstrologyCompute.get_kp_horary(
            number=number, date=date, time=time, place=place,
            lat=latitude, lon=longitude, tz=timezone)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/jaimini")
async def get_jaimini(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Jaimini toolkit: Chara Karakas, Karakamsa/Swamsa, argala."""
    try:
        result = AstrologyCompute.get_jaimini(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/now-chart")
async def get_now_chart(
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Chart of the moment — the current sky at now + here."""
    try:
        result = AstrologyCompute.get_now_chart(
            place=place, lat=latitude, lon=longitude, tz=timezone,
            current_time=current_time, current_tz=current_tz, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
