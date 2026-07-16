"""Astro-journal entries.

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


@router.get("/api/journal")
async def list_journal(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """All journal entries for the user (optionally one profile), newest first."""
    return {"entries": await journal.list_entries(current_user, profile_id),
            "categories": journal.CATEGORIES}

@router.post("/api/journal")
async def create_journal(
    request: JournalEntryRequest,
    current_user: str = Depends(get_current_user),
):
    """Add a dated life-event entry; snapshots the running dasha if birth details
    are supplied."""
    if not request.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    dasha = _dasha_snapshot(request.birth_details, request.date, request.ayanamsa)
    entry = await journal.create_entry(
        current_user, request.profile_id, request.date, request.title,
        request.category, request.notes, dasha)
    return entry

@router.put("/api/journal/{entry_id}")
async def update_journal(
    entry_id: str,
    request: JournalUpdateRequest,
    current_user: str = Depends(get_current_user),
):
    """Edit an entry. If the date changes (and birth details are supplied), the
    running-dasha snapshot is recomputed."""
    fields = {k: v for k, v in {
        "date": request.date, "title": request.title,
        "category": request.category, "notes": request.notes,
    }.items() if v is not None}
    if request.date and request.birth_details:
        fields["dasha"] = _dasha_snapshot(request.birth_details, request.date, request.ayanamsa)
    updated = await journal.update_entry(current_user, entry_id, fields)
    if not updated:
        raise HTTPException(status_code=404, detail="Entry not found")
    return updated

@router.delete("/api/journal/{entry_id}")
async def delete_journal(
    entry_id: str,
    current_user: str = Depends(get_current_user),
):
    ok = await journal.delete_entry(current_user, entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Entry not found")
    return {"status": "deleted"}
