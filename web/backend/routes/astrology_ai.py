"""AI readings over the astrology computes (the *-analysis endpoints).

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


@router.post("/api/astrology/compatibility-analysis")
async def analyze_compatibility(
    request: CompatibilityAnalysisRequest,
    current_user: str = Depends(get_current_user)
):
    """Get detailed compatibility analysis with AI"""
    _enforce_rate_limit(current_user)
    try:
        male_details = request.male_details
        female_details = request.female_details

        # Calculate compatibility score
        compatibility = AstrologyCompute.get_compatibility(
            male_dob=male_details.dob,
            male_tob=male_details.tob,
            male_place=male_details.place,
            female_dob=female_details.dob,
            female_tob=female_details.tob,
            female_place=female_details.place,
            male_lat=male_details.latitude,
            male_lon=male_details.longitude,
            female_lat=female_details.latitude,
            female_lon=female_details.longitude,
            male_tz=male_details.timezone,
            female_tz=female_details.timezone,
            tz=male_details.timezone or female_details.timezone
        )

        # Build the natal summary for both partners (lagna/moon/sun/planets).
        ayanamsa = request.ayanamsa or DEFAULT_AYANAMSA
        male_chart = AstrologyCompute.get_horoscope_predictions(
            dob=male_details.dob, tob=male_details.tob, place=male_details.place,
            lat=male_details.latitude, lon=male_details.longitude,
            tz=male_details.timezone, ayanamsa=ayanamsa,
        )
        female_chart = AstrologyCompute.get_horoscope_predictions(
            dob=female_details.dob, tob=female_details.tob, place=female_details.place,
            lat=female_details.latitude, lon=female_details.longitude,
            tz=female_details.timezone, ayanamsa=ayanamsa,
        )

        # 7th-house marriage workspace (§2.6) — sharpens the couple reading with
        # the marriage houses/karakas. Best-effort: a failure just omits it.
        marriage = None
        try:
            mw = AstrologyCompute.get_marriage_workspace(
                male_dob=male_details.dob, male_tob=male_details.tob,
                male_place=male_details.place, male_lat=male_details.latitude,
                male_lon=male_details.longitude, male_tz=male_details.timezone,
                female_dob=female_details.dob, female_tob=female_details.tob,
                female_place=female_details.place, female_lat=female_details.latitude,
                female_lon=female_details.longitude, female_tz=female_details.timezone,
                ayanamsa=ayanamsa,
            )
            if mw.get("status") == "success":
                marriage = mw
        except Exception as _mw_e:
            print(f"[compat-analysis] marriage workspace skipped: {_mw_e}")

        # Resolve the model config (request key → user's stored key → env key)
        cfg = await _resolve_cfg(current_user, request)

        # Get AI analysis
        ai_analysis = await llm_service.analyze_compatibility(
            male_chart=male_chart,
            female_chart=female_chart,
            koota_score=compatibility.get("total_score", 0),
            marriage=marriage,
            config=cfg,
        )

        await _save_reading(
            current_user, source="compatibility",
            title=f"Compatibility: {male_details.name or 'Partner A'} & {female_details.name or 'Partner B'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=male_details.model_dump(),
            context={"male_details": male_details.model_dump(),
                     "female_details": female_details.model_dump(),
                     "ayanamsa": request.ayanamsa},
        )
        return {
            "compatibility_score": compatibility,
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/compare-analysis")
async def analyze_comparison(
    request: CompareAnalysisRequest,
    current_user: str = Depends(get_current_user)
):
    """Neutral AI comparison of two charts (not marriage compatibility)."""
    _enforce_rate_limit(current_user)
    try:
        p1 = request.person1_details
        p2 = request.person2_details
        ayanamsa = request.ayanamsa or DEFAULT_AYANAMSA

        chart_a = AstrologyCompute.get_horoscope_predictions(
            dob=p1.dob, tob=p1.tob, place=p1.place,
            lat=p1.latitude, lon=p1.longitude, tz=p1.timezone, ayanamsa=ayanamsa,
        )
        chart_b = AstrologyCompute.get_horoscope_predictions(
            dob=p2.dob, tob=p2.tob, place=p2.place,
            lat=p2.latitude, lon=p2.longitude, tz=p2.timezone, ayanamsa=ayanamsa,
        )

        cfg = await _resolve_cfg(current_user, request)

        ai_analysis = await llm_service.compare_charts(
            chart_a=chart_a,
            chart_b=chart_b,
            name_a=request.person1_name or "Person 1",
            name_b=request.person2_name or "Person 2",
            config=cfg,
        )

        await _save_reading(
            current_user, source="compare",
            title=f"Compare: {request.person1_name or 'Person 1'} vs {request.person2_name or 'Person 2'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=p1.model_dump(),
            context={"person1_details": p1.model_dump(),
                     "person2_details": p2.model_dump(),
                     "person1_name": request.person1_name,
                     "person2_name": request.person2_name,
                     "ayanamsa": request.ayanamsa},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/kaala-chakra-analysis")
async def analyze_kaala_chakra(
    request: ChakraAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of the Kaala Chakra (directions) — §2.7."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        kaala = AstrologyCompute.get_kaala_chakra(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            current_date=request.current_date, current_time=request.current_time,
            current_tz=request.current_tz, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
        if kaala.get("status") != "success":
            raise HTTPException(status_code=400, detail=kaala.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_kaala_chakra(
            kaala_data=kaala, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="kaala_chakra",
            title=f"Kaala Chakra — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name,
                     "current_date": request.current_date,
                     "current_time": request.current_time,
                     "current_tz": request.current_tz,
                     "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value, "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/kota-chakra-analysis")
async def analyze_kota_chakra(
    request: ChakraAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of the Kota Chakra (the fort) — §2.7."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        kota = AstrologyCompute.get_kota_chakra(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            current_date=request.current_date, current_time=request.current_time,
            current_tz=request.current_tz, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
        if kota.get("status") != "success":
            raise HTTPException(status_code=400, detail=kota.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_kota_chakra(
            kota_data=kota, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="kota_chakra",
            title=f"Kota Chakra — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name,
                     "current_date": request.current_date,
                     "current_time": request.current_time,
                     "current_tz": request.current_tz,
                     "ayanamsa": request.ayanamsa},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/tripataki-chakra-analysis")
async def analyze_tripataki_chakra(
    request: ChakraAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of the Tripataki Chakra vedha — §2.7."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        trip = AstrologyCompute.get_tripataki_chakra(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            current_date=request.current_date, current_time=request.current_time,
            current_tz=request.current_tz,
            basis=request.basis or "transit", year=request.year,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
        if trip.get("status") != "success":
            raise HTTPException(status_code=400, detail=trip.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_tripataki(
            trip_data=trip, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="tripataki_chakra",
            title=f"Tripataki Chakra — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name,
                     "current_date": request.current_date,
                     "current_time": request.current_time,
                     "current_tz": request.current_tz,
                     "ayanamsa": request.ayanamsa},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/astrology/sarvatobhadra-analysis")
async def analyze_sarvatobhadra(
    request: SarvatobhadraAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of the Sarvatobhadra Chakra transit picture."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        sbc = AstrologyCompute.get_sarvatobhadra_chakra(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            name_nakshatra=request.name_nakshatra, current_date=request.current_date,
            current_time=request.current_time, current_tz=request.current_tz,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
        if sbc.get("status") != "success":
            raise HTTPException(status_code=400, detail=sbc.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_sarvatobhadra(
            sbc_data=sbc, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="sarvatobhadra",
            title=f"Sarvatobhadra — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name,
                     "name_nakshatra": request.name_nakshatra,
                     "current_date": request.current_date,
                     "current_time": request.current_time,
                     "current_tz": request.current_tz,
                     "ayanamsa": request.ayanamsa},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/sensitive-points-analysis")
async def analyze_sensitive_points(
    request: SensitivePointsAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of the sensitive points (Sphuta/Saham/Argala)."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        args = dict(dob=bd.dob, tob=bd.tob, place=bd.place,
                    lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
                    ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        data = {
            "sphuta": AstrologyCompute.get_sphuta(**args),
            "sahams": AstrologyCompute.get_sahams(**args),
            "argala": AstrologyCompute.get_argala(**args),
        }
        if data["sphuta"].get("status") != "success":
            raise HTTPException(status_code=400,
                                detail=data["sphuta"].get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_sensitive_points(
            data=data, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="sensitive_points",
            title=f"Sensitive points — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name,
                     "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/celestial-analysis")
async def analyze_celestial(
    request: CelestialAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of the Vedic clock + retrograde snapshot."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        loc = dict(place=bd.place, lat=bd.latitude, lon=bd.longitude, tz=bd.timezone)
        data = {
            "clock": AstrologyCompute.get_vedic_clock(date=request.date, **loc),
            "retrograde": AstrologyCompute.get_retrograde(date=request.date, **loc),
        }
        if data["clock"].get("status") != "success":
            raise HTTPException(status_code=400,
                                detail=data["clock"].get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_celestial(
            data=data, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="celestial",
            title=f"Vedic clock — {request.date or 'now'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "date": request.date},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/almanac-analysis")
async def analyze_almanac(
    request: AlmanacAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI day-guide from the almanac (panchanga + hora) for a
    place/date. Location-driven, not tied to a birth chart."""
    _enforce_rate_limit(current_user)
    try:
        loc = dict(place=request.place, lat=request.latitude,
                   lon=request.longitude, tz=request.timezone)
        data = {
            "panchanga": AstrologyCompute.get_panchanga(
                date=request.date, system=request.system, **loc),
            "hours": AstrologyCompute.get_planetary_hours(date=request.date, **loc),
        }
        if data["panchanga"].get("status") != "success":
            raise HTTPException(status_code=400,
                                detail=data["panchanga"].get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_almanac(data=data, config=cfg)
        await _save_reading(
            current_user, source="almanac",
            title=f"Almanac — {request.place or 'location'} · {request.date or 'today'}",
            text=ai_analysis, cfg=cfg,
            context={"place": request.place, "latitude": request.latitude,
                     "longitude": request.longitude, "timezone": request.timezone,
                     "date": request.date, "system": request.system},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/muhurta-analysis")
async def analyze_muhurta(
    request: MuhurtaAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language rationale for the recommended auspicious windows."""
    _enforce_rate_limit(current_user)
    try:
        result = AstrologyCompute.get_muhurta(
            activity=request.activity, start_date=request.start_date,
            end_date=request.end_date, place=request.place,
            lat=request.latitude, lon=request.longitude, tz=request.timezone)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_muhurta(muhurta_data=result, config=cfg)
        await _save_reading(
            current_user, source="muhurta",
            title=f"Muhurta — {request.activity} · {request.start_date or ''}".strip(" ·"),
            text=ai_analysis, cfg=cfg,
            context={"activity": request.activity, "start_date": request.start_date,
                     "end_date": request.end_date, "place": request.place,
                     "latitude": request.latitude, "longitude": request.longitude,
                     "timezone": request.timezone},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/prashna-analysis")
async def analyze_prashna(
    request: PrashnaAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Prashna (horary) reading of the moment-chart for the asked question."""
    _enforce_rate_limit(current_user)
    try:
        result = AstrologyCompute.get_prashna(
            question=request.question, date=request.date, time=request.time,
            place=request.place, lat=request.latitude, lon=request.longitude,
            tz=request.timezone, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_prashna(prashna_data=result, config=cfg)
        await _save_reading(
            current_user, source="prashna",
            title=f"Prashna — {(request.question or 'question')[:48]}",
            text=ai_analysis, cfg=cfg, request_label=request.question or "Prashna",
            context={"question": request.question, "date": request.date,
                     "time": request.time, "place": request.place,
                     "latitude": request.latitude, "longitude": request.longitude,
                     "timezone": request.timezone, "ayanamsa": request.ayanamsa},
        )
        return {"reading": ai_analysis, "chart": result,
                "provider": cfg.provider_type.value, "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/daily-digest-analysis")
async def analyze_daily_digest(
    request: DailyDigestAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, personalized AI reading of today's digest."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        basis = _basis(request.basis)
        result = AstrologyCompute.get_daily_digest(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, date=request.date,
            current_time=request.current_time, current_tz=request.current_tz,
            basis=basis, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_daily_digest(
            digest_data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="daily_digest",
            title=f"Daily digest — {request.date or 'today'} · {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "date": request.date,
                     "current_time": request.current_time, "current_tz": request.current_tz,
                     "basis": basis, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/fortnightly-digest-analysis")
async def analyze_fortnightly_digest(
    request: DailyDigestAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, personalized AI reading of the fortnight (Paksha Pravesha) digest."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_fortnightly_digest(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, date=request.date,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_fortnightly_digest(
            digest_data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="fortnightly_digest",
            title=f"Fortnightly digest — {result.get('start_date')} · {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "date": request.date,
                     "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/monthly-digest-analysis")
async def analyze_monthly_digest(
    request: DailyDigestAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, personalized AI reading of the monthly digest (solar Maasa Pravesha
    or lunar birth-tithi return, per `basis`)."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        basis = _basis(request.basis)
        result = AstrologyCompute.get_monthly_digest(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, date=request.date, basis=basis,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_monthly_digest(
            digest_data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="monthly_digest",
            title=f"Monthly digest ({basis}) — {result.get('start_date')} · {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "date": request.date,
                     "basis": basis, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/tithi-pravesha-analysis")
async def analyze_tithi_pravesha(
    request: DailyDigestAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm AI reading of a chart on the lunar pravesha ladder.

    `rung` defaults to `annual` — the Tithi Pravesha chart proper — so older clients
    that never sent one keep the reading they always got. Every rung is saved under
    the same `tithi_pravesha` history source, so a saved reading reopens on the TP
    page whichever window it was cast for."""
    _enforce_rate_limit(current_user)
    rung = request.rung or "annual"
    if rung not in _LUNAR_RUNGS:
        raise HTTPException(status_code=400, detail=f"Unknown rung '{rung}'")
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_lunar_pravesha(
            rung, dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, year=request.year, date=request.date,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_tithi_pravesha(
            tp_data=result, name=request.person_name or bd.name or "this person", config=cfg)
        label = {"tithi": "Tithi", "paksha": "Paksha", "month": "Lunar month",
                 "annual": "Tithi Pravesha"}[rung]
        await _save_reading(
            current_user, source="tithi_pravesha",
            title=f"{label} — {result.get('window', {}).get('start')} · {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "year": request.year,
                     "date": request.date, "rung": rung, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/bhrigu-markers-analysis")
async def analyze_bhrigu_markers(
    request: BhriguMarkersAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language reading of the Bhrigu / Nadi yearly markers."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_bhrigu_markers(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, from_age=request.from_age,
            years=request.years or 12, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_bhrigu_markers(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="bhrigu",
            title=f"Bhrigu markers — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "from_age": request.from_age,
                     "years": request.years or 12, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/nadi-analysis")
async def analyze_nadi_reading(
    request: NadiAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language reading of the Nadi karaka significators + transit triggers."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_nadi_reading(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, gender=request.gender,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_nadi_reading(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="nadi",
            title=f"Nadi karaka reading — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "gender": request.gender,
                     "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/life-timeline-analysis")
async def analyze_life_timeline(
    request: TimelineAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language reading of "what's running" at a chosen point on the
    timeline — the active Maha/Bhukti, Saturn phase and nearby transits."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        ctx = AstrologyCompute.get_timeline_window_context(
            dob=bd.dob, tob=bd.tob, place=bd.place, target_date=request.target_date,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if ctx.get("status") != "success":
            raise HTTPException(status_code=400, detail=ctx.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_timeline_window(
            data=ctx, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="timeline",
            title=f"Timeline — {request.target_date} — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name,
                     "target_date": request.target_date, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model, "window": ctx}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/planet-conditions-analysis")
async def analyze_planet_conditions(
    request: PlanetConditionsAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language reading of the planet-condition flags."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_planet_conditions(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_planet_conditions(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="planet_conditions",
            title=f"Planet conditions — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/saturn-transits-analysis")
async def analyze_saturn_transits(
    request: SaturnTransitsAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Calm, plain-language reading of the Sade Sati / Saturn transits."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_saturn_transits(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_saturn_transits(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="saturn_transits",
            title=f"Sade Sati — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/strength-analysis")
async def analyze_strength(
    request: StrengthAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language reading of the strength picture."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_strength(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_strength(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="strength",
            title=f"Strength — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/nakshatra-profile-analysis")
async def analyze_nakshatra_profile(
    request: NakshatraProfileAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, layman reading of the janma-nakshatra profile."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_nakshatra_profile(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, current_date=request.current_date,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_nakshatra_profile(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="nakshatra_profile",
            title=f"Nakshatra — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/planetary-nakshatras-analysis")
async def analyze_planetary_nakshatras(
    request: NakshatraProfileAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Reading of the nakshatra each graha occupies — the star layer beyond the
    janma star, which `nakshatra-profile-analysis` covers on its own."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_nakshatra_profile(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, current_date=request.current_date,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_planetary_nakshatras(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="planetary_nakshatras",
            title=f"Planetary nakshatras — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/gochara-phala-analysis")
async def analyze_gochara_phala(
    request: GocharaPhalaAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, layman reading of the gochara-phala (with vedha) results."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_gochara_phala(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, current_date=request.current_date,
            current_tz=request.current_tz,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_gochara_phala(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="gochara_phala",
            title=f"Gochara-phala — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/friendships-analysis")
async def analyze_friendships(
    request: FriendshipsAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language reading of the planetary friendships + house-lord placements."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_friendships(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_friendships(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="friendships",
            title=f"Friendships — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/avasthas-analysis")
async def analyze_avasthas(
    request: AvasthasAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language reading of the planetary avasthas."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_avasthas(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_avasthas(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="avasthas",
            title=f"Avasthas — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/remedies-analysis")
async def analyze_remedies(
    request: RemediesAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, plain-language explanation of the suggested remedies."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_remedies(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_remedies(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="remedies",
            title=f"Remedies — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/kp-analysis")
async def analyze_kp(
    request: KPAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """AI KP reading of the natal chart."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_kp_details(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_kp(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="kp",
            title=f"KP reading — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/kp-horary-analysis")
async def analyze_kp_horary(
    request: KPHoraryAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """AI KP horary judgement for the number + question."""
    _enforce_rate_limit(current_user)
    try:
        result = AstrologyCompute.get_kp_horary(
            number=request.number, date=request.date, time=request.time,
            place=request.place, lat=request.latitude, lon=request.longitude,
            tz=request.timezone)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_kp_horary(
            data=result, question=request.question or "", config=cfg)
        await _save_reading(
            current_user, source="kp_horary",
            title=f"KP horary #{request.number} — {(request.question or 'question')[:40]}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            request_label=request.question or f"KP horary #{request.number}",
            context={"number": request.number, "question": request.question,
                     "date": request.date, "time": request.time, "place": request.place,
                     "latitude": request.latitude, "longitude": request.longitude,
                     "timezone": request.timezone},
        )
        return {"reading": ai_analysis, "chart": result,
                "provider": cfg.provider_type.value, "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/jaimini-analysis")
async def analyze_jaimini(
    request: JaiminiAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """AI Jaimini reading of the natal chart."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_jaimini(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_jaimini(
            data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="jaimini",
            title=f"Jaimini reading — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/arudha-analysis")
async def analyze_arudhas(
    request: ArudhaAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """AI reading of the bhava arudhas — the *projected* chart (image vs reality)."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_arudha_analysis(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_arudhas(
            data=result, name=request.person_name or bd.name or "this person",
            selected=request.selected, config=cfg)
        picks = ", ".join(request.selected) if request.selected else "AL, UL, A10, A11"
        await _save_reading(
            current_user, source="arudha",
            title=f"Arudha reading ({picks}) — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "ayanamsa": request.ayanamsa,
                     "selected": request.selected},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/now-chart-analysis")
async def analyze_now_chart(
    request: NowChartAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """AI reading of the chart of the moment."""
    _enforce_rate_limit(current_user)
    try:
        result = AstrologyCompute.get_now_chart(
            place=request.place, lat=request.latitude, lon=request.longitude,
            tz=request.timezone, current_time=request.current_time,
            current_tz=request.current_tz, ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_now_chart(data=result, config=cfg)
        await _save_reading(
            current_user, source="now_chart",
            title=f"Chart of the moment — {result.get('moment', {}).get('date', 'now')}",
            text=ai_analysis, cfg=cfg,
            context={"place": request.place, "latitude": request.latitude,
                     "longitude": request.longitude, "timezone": request.timezone,
                     "current_time": request.current_time, "current_tz": request.current_tz},
        )
        return {"reading": ai_analysis, "chart": result,
                "provider": cfg.provider_type.value, "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/varshaphal-analysis")
async def analyze_varshaphal(
    request: VarshaphalAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI year-ahead reading of the Varshaphal (annual) chart."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        varsha = AstrologyCompute.get_varshaphal(
            dob=bd.dob, tob=bd.tob, place=bd.place, year=request.year,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            current_tz=await viewer_tz(current_user, request.current_tz, bd.timezone),
        )
        if varsha.get("status") != "success":
            raise HTTPException(status_code=400, detail=varsha.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_varshaphal(
            varsha_data=varsha, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="varshaphal",
            title=f"Annual {request.year} — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"year": request.year, "person_name": request.person_name,
                     "ayanamsa": request.ayanamsa},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/pancha-pakshi-analysis")
async def analyze_pancha_pakshi(
    request: PanchaPakshiAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of today's Pancha Pakshi timing — what to do/avoid."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        here = await viewer_place(current_user) or {}
        pp = AstrologyCompute.get_pancha_pakshi(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            date=request.date,
            current_place=here.get("place"), current_lat=here.get("latitude"),
            current_lon=here.get("longitude"), current_tz=here.get("timezone"),
        )
        if pp.get("status") != "success":
            raise HTTPException(status_code=400, detail=pp.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_pancha_pakshi(
            pp_data=pp, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="panchapakshi",
            title=f"Pancha Pakshi — {request.date or 'today'} · {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"person_name": request.person_name, "date": request.date},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/rectify-birth-time/explain")
async def explain_rectification(
    request: RectifyExplainRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI note on why the suggested (rectified) birth time fits better."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        rect = AstrologyCompute.get_birth_time_rectification(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            method=request.method, gender=request.gender,
        )
        if rect.get("status") != "success":
            raise HTTPException(status_code=400, detail=rect.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.explain_rectification(
            rectification_data=rect, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="rectification",
            title=f"Rectification ({request.method}) — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"method": request.method, "gender": request.gender,
                     "person_name": request.person_name, "ayanamsa": request.ayanamsa},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/rectify-birth-time/events/explain")
async def explain_event_rectification(
    request: RectifyEventsExplainRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI note on why the event-matched time fits the supplied events."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        rect = AstrologyCompute.get_event_rectification(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            events=[e.model_dump() for e in request.events],
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            window_minutes=request.window_minutes,
        )
        if rect.get("status") != "success":
            raise HTTPException(status_code=400, detail=rect.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.explain_event_rectification(
            rectification_data=rect, name=request.person_name or "this person", config=cfg,
        )
        await _save_reading(
            current_user, source="rectification",
            title=f"Event rectification — {request.person_name or bd.name or 'chart'}",
            text=ai_analysis, cfg=cfg, profile_id=request.profile_id,
            birth_details=bd.model_dump(),
            context={"events": [e.model_dump() for e in request.events],
                     "window_minutes": request.window_minutes,
                     "person_name": request.person_name, "ayanamsa": request.ayanamsa,
                     "mode": "events"},
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/astrology/rectify-birth-time/chat")
async def rectify_birth_time_chat(
    request: RectifyChatRequest,
    current_user: str = Depends(get_current_user),
):
    """Conversational rectification: the AI interviews the user for dated life
    events (one question per turn) and returns the running event list + a `ready`
    flag. The deterministic /events endpoint then does the actual rectification."""
    _enforce_rate_limit(current_user)
    try:
        cfg = await _resolve_cfg(current_user, request)
        turn = await llm_service.rectification_chat(
            messages=[m.model_dump() for m in request.messages],
            collected_events=[e.model_dump() for e in request.collected_events],
            name=request.person_name or "this person",
            config=cfg,
        )
        return {
            "reply": turn.get("reply", ""),
            "events": turn.get("events", []),
            "ready": turn.get("ready", False),
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
