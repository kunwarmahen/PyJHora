"""Public API v1 — token-authed, read-only tool surface for scripts + MCP (§2.3).

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



# ============= PUBLIC API v1 (token-authed, read-only) — §2.3 =============
# A documented, stable surface for scripts and the MCP server. Every route is
# **read-only compute** (no account/profile mutation), authenticated with a
# per-user API token (or a session JWT), and rate-limited like the AI endpoints.

@router.get("/api/v1")
async def api_v1_index():
    """Discovery root — points at the catalog + how to authenticate. No auth so a
    client can bootstrap; the actual compute routes require a token."""
    return {
        "name": f"{settings.SITE_NAME} Astrology API",
        "version": "1",
        "auth": "Bearer token — create one under Settings → API access (jyd_…).",
        "read_only": True,
        "endpoints": {
            "list_tools": "GET /api/v1/tools",
            "list_profiles": "GET /api/v1/profiles",
            "run_tool": "POST /api/v1/tools/{tool_name}",
        },
    }


@router.get("/api/v1/tools")
async def api_v1_tools(current_user: str = Depends(get_api_user)):
    """The full catalog of astrology tools the API can run — each with a label,
    category, model/agent-facing description, and JSON-schema parameters."""
    return {"tools": tool_registry.tool_catalog()}


@router.get("/api/v1/profiles")
async def api_v1_profiles(current_user: str = Depends(get_api_user)):
    """The caller's saved profiles (id + name + birth summary) for use as
    `profile_id` when running a tool. Read-only projection — no mutation here."""
    from database import database
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    docs = await database["saved_profiles"].find(
        {"user_id": current_user}
    ).sort("created_at", -1).to_list(200)
    out = []
    for d in docs:
        bd = d.get("birth_details") or {}
        out.append({
            "id": str(d["_id"]),
            "profile_name": d.get("profile_name"),
            "name": bd.get("name"),
            "dob": bd.get("dob"),
            "tob": bd.get("tob"),
            "place": bd.get("place"),
        })
    return {"profiles": out}


@router.post("/api/v1/tools/{tool_name}")
async def api_v1_run_tool(tool_name: str, req: ToolRunRequest,
                          current_user: str = Depends(get_api_user)):
    """Run one astrology tool. Body: `profile_id` OR `birth_details`, an optional
    `ayanamsa`, and tool-specific `args`. Returns the tool's JSON result."""
    _enforce_rate_limit(current_user)
    birth_details = await _resolve_birth_details(req, current_user)
    if not birth_details.get("dob") or not birth_details.get("tob"):
        raise HTTPException(status_code=400, detail="birth data missing dob/tob")
    try:
        result = tool_registry.dispatch(
            tool_name, req.args or {}, birth_details,
            ayanamsa=req.ayanamsa or DEFAULT_AYANAMSA,
            current_tz=await viewer_tz(
                current_user, fallback=birth_details.get("timezone")),
            viewer=await viewer_place(current_user),
        )
    except tool_registry.ToolError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"tool": tool_name, "result": result}
