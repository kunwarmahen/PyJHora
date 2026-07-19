"""Jyotir AI Web API — FastAPI app wiring (§4b split).

This file used to be 5,272 lines of handlers. It now only builds the app: the
lifespan (Mongo + digest scheduler), CORS, and mounting the route modules. Every
handler lives under routes/, the request models in models.py, and the shared
auth/rate-limit/persistence helpers in deps.py.

`get_current_user` / `get_api_user` are re-exported below so that
`app.dependency_overrides[main.get_current_user]` (used by the tests) still
targets the very same function object the routers depend on.
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

# Shared dependencies — re-exported so `main.get_current_user` stays a valid
# dependency_overrides key for callers/tests that referenced it before the split.
from deps import get_current_user, get_api_user, get_admin_user, security  # noqa: F401
import admin as admin_service


# Lifecycle events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    # Mirror ADMIN_USERNAMES (env, deployer-controlled) onto the is_admin flag so
    # admin grants/revokes take effect on deploy without touching Mongo (§44).
    try:
        result = await admin_service.reconcile_admins()
        if result["granted"] or result["revoked"]:
            print(f"[admin] reconciled admins: {result}")
    except Exception as e:
        print(f"[admin] reconcile skipped: {e}")
    scheduler.start()  # daily-digest scheduler (no-op unless DIGEST_SCHEDULER_ENABLED)
    yield
    # Shutdown
    await scheduler.stop()
    await close_mongo_connection()

app = FastAPI(
    title=f"{settings.SITE_NAME} Web API",
    description="Vedic Astrology Web Application",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────
from routes import auth as auth_routes
from routes import v1 as v1_routes
from routes import ai as ai_routes
from routes import astrology as astrology_routes
from routes import astrology_ai as astrology_ai_routes
from routes import quiz as quiz_routes
from routes import user as user_routes
from routes import profiles as profiles_routes
from routes import journal as journal_routes
from routes import notifications as notifications_routes
from routes import misc as misc_routes
from routes import admin as admin_routes

app.include_router(auth_routes.router)
app.include_router(v1_routes.router)
app.include_router(ai_routes.router)
app.include_router(astrology_routes.router)
app.include_router(astrology_ai_routes.router)
app.include_router(quiz_routes.router)
app.include_router(user_routes.router)
app.include_router(profiles_routes.router)
app.include_router(journal_routes.router)
app.include_router(notifications_routes.router)
app.include_router(misc_routes.router)
app.include_router(admin_routes.router)

if __name__ == "__main__":
    import os
    import uvicorn
    # Overridable so this can run alongside another service already holding the
    # default port (dev.sh passes BACKEND_PORT through).
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("BACKEND_PORT", "8000")))
