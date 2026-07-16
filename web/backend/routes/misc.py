"""Location lookup, iCal calendar feed, health check.

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


# ── iCal feed (§5.10) ────────────────────────────────────────────────────────
@router.get("/api/calendar/token")
async def get_calendar_token(
    profile_id: str,
    current_user: str = Depends(get_current_user),
):
    """Stable, signed subscribe token + relative .ics path for a profile."""
    from database import database
    from bson import ObjectId
    prof = await database["saved_profiles"].find_one(
        {"_id": ObjectId(profile_id), "user_id": current_user})
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    token = ical.make_token(current_user, profile_id)
    return {"token": token, "path": f"/api/calendar/{token}.ics"}

@router.get("/api/calendar/{token}.ics")
async def calendar_feed(token: str):
    """Public, token-authed iCal feed. No bearer auth (calendar apps can't send
    one) — the signed token in the path is the credential."""
    resolved = ical.verify_token(token)
    if not resolved:
        raise HTTPException(status_code=403, detail="Invalid calendar token")
    user_id, profile_id = resolved
    from database import database
    from bson import ObjectId
    try:
        prof = await database["saved_profiles"].find_one(
            {"_id": ObjectId(profile_id), "user_id": user_id})
    except Exception:
        prof = None
    if not prof:
        raise HTTPException(status_code=404, detail="Profile not found")
    bd = prof.get("birth_details", {})
    name = prof.get("profile_name") or bd.get("name") or "Chart"
    events = ical.gather_events(bd)
    body = ical.build_ics(f"Jyotir AI — {name}", events)
    return Response(content=body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'inline; filename="jyotir-{profile_id}.ics"'})

@router.post("/api/location/search")
async def search_location(req: LocationSearchRequest):
    """
    Search for a location and return its coordinates and timezone.
    This makes it easy for users to get lat/long without manually looking it up.

    Example queries:
    - "Chennai, India"
    - "New York, USA"
    - "London, UK"
    """
    try:
        result = AstrologyCompute.search_location(req.query)
        if result:
            return {
                "success": True,
                "place": result[0],
                "latitude": result[1],
                "longitude": result[2],
                "timezone": result[3]
            }
        else:
            return {
                "success": False,
                "message": f"Location '{req.query}' not found. Try format: 'City, Country' (e.g., 'Mumbai, India')"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Location search error: {str(e)}")

@router.post("/api/location/reverse")
async def reverse_geocode(req: ReverseGeocodeRequest):
    """Resolve a map-picked lat/long to a place name + timezone offset.

    Backs the interactive map picker. Gated by MAP_PICKER_ENABLED so the whole
    feature can be switched off for production deployments (the frontend hides
    the UI via REACT_APP_ENABLE_MAP_PICKER; this guard is defense in depth).
    """
    if not settings.MAP_PICKER_ENABLED:
        raise HTTPException(status_code=403, detail="Map location picker is disabled.")
    if not (-90 <= req.latitude <= 90) or not (-180 <= req.longitude <= 180):
        raise HTTPException(status_code=400, detail="Coordinates out of range.")
    try:
        result = AstrologyCompute.reverse_geocode(req.latitude, req.longitude)
        if result:
            return {
                "success": True,
                "place": result[0],
                "latitude": result[1],
                "longitude": result[2],
                "timezone": result[3],
            }
        return {"success": False, "message": "Could not resolve that location."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reverse geocode error: {str(e)}")

# ============= HEALTH CHECK =============

@router.get("/health")
async def health_check():
    """Health check.

    Probes the local Ollama endpoint (OLLAMA_URL / OLLAMA_DEFAULT_MODEL) so the
    Settings › System tab reflects the actual local-AI status and configured
    model."""
    local = await llm_service._ollama_status()
    return {
        "status": "healthy",
        "engine_available": AstrologyCompute.ENGINE_AVAILABLE,
        "local_ai": {
            "available": bool(local.get("available")),
            "base_url": local.get("base_url"),
            "model": local.get("default_model"),
            "reason": local.get("reason"),
        },
        "map_picker_enabled": settings.MAP_PICKER_ENABLED
    }
