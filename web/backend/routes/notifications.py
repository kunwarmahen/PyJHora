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
from astrology import AstrologyCompute, SUPPORTED_AYANAMSAS, DEFAULT_AYANAMSA, SUPPORTED_VARGAS, SUPPORTED_DASHAS, EVENT_KINDS
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
import digest_recipients
import events
import scheduler
import timezones
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
            # Served rather than hard-coded in the UI: the kinds a user may pick
            # from and the kinds the compute emits have to be the same list, and
            # two lists that must agree are a bug waiting to happen (§52).
            "event_kinds": list(EVENT_KINDS),
            "vapid_public_key": notifications.vapid_public_key()}

@router.put("/api/notifications/prefs")
async def set_notification_prefs(
    req: NotificationPrefsRequest,
    current_user: str = Depends(get_current_user),
):
    prefs = await notifications.set_prefs(
        current_user, {k: v for k, v in req.model_dump().items() if v is not None})
    return {"prefs": prefs}

@router.get("/api/notifications/events")
async def get_upcoming_events(
    profile_id: str = "",
    kinds: str = "",
    months: int = 12,
    refresh: bool = False,
    limit: int = 200,
    current_user: str = Depends(get_current_user),
):
    """The stored forward calendar for this user (§70).

    `refresh=true` recomputes first; otherwise a calendar older than the refresh
    horizon is rebuilt anyway, so a user who never enables alerts still sees a
    current list when they open the tab. "Today" is the reader's own date — a
    calendar that begins yesterday is a bug for a third of the globe."""
    prefs = await notifications.get_prefs(current_user)
    tz_now = await viewer_tz(current_user)
    today = timezones.today_at_offset(tz_now)
    try:
        await events.refresh_user(current_user, prefs, today=today, force=refresh)
    except Exception as e:  # a stale calendar still beats an error page
        print(f"[events] refresh failed for {current_user}: {e}")
    wanted = [k.strip() for k in kinds.split(",") if k.strip()] or None
    rows = await events.upcoming(current_user, profile_id=profile_id or None,
                                 kinds=wanted, limit=limit, today=today)
    return {"events": rows, "today": today, "kinds": list(EVENT_KINDS),
            "months": months, "alerts_enabled": bool(prefs.get("event_alerts"))}


@router.post("/api/notifications/events/send")
async def send_event_alerts_now(current_user: str = Depends(get_current_user)):
    """Deliver any due alerts immediately — the "send test now" of this feature.

    It claims and sends real events rather than a fake one, so what arrives is
    exactly what the scheduler would have sent."""
    prefs = await notifications.get_prefs(current_user)
    today = timezones.today_at_offset(await viewer_tz(current_user))
    await events.refresh_user(current_user, prefs, today=today)
    return await events.send_alerts_for_user(current_user, prefs, today=today)


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


# ---- Public digest opt-in / opt-out (no auth — reached from an emailed link) ----

@router.get("/api/digest/confirm")
async def digest_confirm(token: str = ""):
    """Confirm a recipient's opt-in from a confirmation-email link. Public and
    idempotent; a bad token just reports failure without leaking anything."""
    email = await digest_recipients.confirm(token)
    if not email:
        return {"status": "invalid"}
    return {"status": "confirmed", "email": email}


@router.get("/api/digest/unsubscribe")
async def digest_unsubscribe(token: str = ""):
    """Opt a recipient out from an unsubscribe link carried in every digest.
    Public and idempotent."""
    email = await digest_recipients.unsubscribe(token)
    if not email:
        return {"status": "invalid"}
    return {"status": "unsubscribed", "email": email}
