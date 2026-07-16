"""User profile + saved charts.

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


# ============= USER ROUTES =============

@router.get("/api/user/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    """Get user profile"""
    try:
        from database import database
        
        users_collection = database["users"]
        user = await users_collection.find_one({"username": current_user})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user["_id"] = str(user.get("_id", ""))
        # Tell the client whether a password is set (Google-only accounts have
        # none yet) so Settings can offer "Set a password" vs "Change password".
        user["has_password"] = bool(user.get("hashed_password"))
        # Google-only accounts have no password field — pop defensively.
        user.pop("hashed_password", None)
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/user/charts")
async def get_user_charts(current_user: str = Depends(get_current_user)):
    """Get user charts"""
    try:
        from database import database
        
        charts_collection = database["charts"]
        charts = await charts_collection.find({"user_id": current_user}).to_list(length=100)
        
        for chart in charts:
            chart["_id"] = str(chart.get("_id", ""))
        
        return {"charts": charts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/user/api-keys")
async def get_api_keys(current_user: str = Depends(get_current_user)):
    """Per-provider key status for the current user (masked — never the raw key)."""
    return {"keys": await user_settings.get_key_status(current_user)}


@router.put("/api/user/api-keys/{provider}")
async def put_api_key(
    provider: str,
    request: ApiKeyRequest,
    current_user: str = Depends(get_current_user)
):
    """Store (encrypted) the user's API key for one provider."""
    if provider not in user_settings.KEYED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider}'. Expected one of {user_settings.KEYED_PROVIDERS}.",
        )
    if not request.api_key.strip():
        raise HTTPException(status_code=400, detail="api_key cannot be empty")
    await user_settings.set_api_key(current_user, provider, request.api_key)
    return {"success": True, "provider": provider}


@router.delete("/api/user/api-keys/{provider}")
async def remove_api_key(
    provider: str,
    current_user: str = Depends(get_current_user)
):
    """Remove the user's stored API key for one provider."""
    if provider not in user_settings.KEYED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'.")
    await user_settings.delete_api_key(current_user, provider)
    return {"success": True, "provider": provider}


@router.get("/api/user/preferences")
async def get_preferences(current_user: str = Depends(get_current_user)):
    """The user's cross-device UI preferences (currently the LLM provider/model)."""
    return {"preferences": await user_settings.get_preferences(current_user)}


@router.put("/api/user/preferences")
async def put_preferences(
    request: PreferencesRequest,
    current_user: str = Depends(get_current_user),
):
    """Store a partial set of the user's synced UI preferences."""
    prefs = await user_settings.set_preferences(current_user, request.preferences or {})
    return {"preferences": prefs}
