"""Digest preferences and web-push subscriptions.

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


# ============= NOTIFICATIONS (digest prefs + web push) =============

@router.get("/api/notifications/prefs")
async def get_notification_prefs(current_user: str = Depends(get_current_user)):
    prefs = await notifications.get_prefs(current_user)
    return {"prefs": prefs, "push_available": notifications.push_enabled(),
            "email_available": email_service.is_configured(),
            "vapid_public_key": notifications.vapid_public_key()}

@router.put("/api/notifications/prefs")
async def set_notification_prefs(
    req: NotificationPrefsRequest,
    current_user: str = Depends(get_current_user),
):
    prefs = await notifications.set_prefs(
        current_user, {k: v for k, v in req.model_dump().items() if v is not None})
    return {"prefs": prefs}

@router.post("/api/notifications/push/subscribe")
async def push_subscribe(
    req: PushSubscribeRequest,
    current_user: str = Depends(get_current_user),
):
    if not notifications.push_enabled():
        raise HTTPException(status_code=503, detail="Push notifications are not configured on this server")
    try:
        await notifications.save_subscription(current_user, req.subscription)
        return {"status": "ok"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/api/notifications/push/unsubscribe")
async def push_unsubscribe(
    req: PushUnsubscribeRequest,
    current_user: str = Depends(get_current_user),
):
    removed = await notifications.delete_subscription(current_user, req.endpoint)
    return {"status": "ok", "removed": removed}

@router.post("/api/notifications/digest/send")
async def send_digest_now(cadence: str = "daily",
                          current_user: str = Depends(get_current_user)):
    """Compute the current user's digest for `cadence` (daily/weekly/monthly) and
    deliver it on their enabled channels (email / push). Returns what was sent.
    Shares its delivery logic with the background scheduler
    (`digest.send_digest_for_user`); a user triggers this as a test from Settings,
    or a deployer's cron can hit it per user + cadence."""
    cadence = (cadence or "daily").lower()
    if cadence not in ("daily", "fortnightly", "monthly"):
        raise HTTPException(status_code=400,
                            detail="cadence must be daily, fortnightly or monthly")
    prefs = await notifications.get_prefs(current_user)
    # The daily switch is `daily_digest`; fortnightly/monthly are named for the cadence.
    switch = "daily_digest" if cadence == "daily" else cadence
    if not prefs.get(switch):
        raise HTTPException(status_code=400,
                            detail=f"The {cadence} digest is not enabled in your settings")

    result = await digest_service.send_digest_for_user(current_user, prefs, cadence)
    if result.get("status") != "ok":
        if result.get("reason") == "no_profile":
            raise HTTPException(status_code=400, detail="No birth profile found to build the digest from")
        raise HTTPException(status_code=400, detail="Digest calculation failed")
    return result
