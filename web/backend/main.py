from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
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
import tool_traces
import user_settings
import ratelimit
import shares
import quiz
import refresh_tokens
import password_reset
import email_service
import notifications
import digest as digest_service
import scheduler
import uuid

# Request models
class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    name: str
    remember_me: bool = False

class GoogleAuthRequest(BaseModel):
    # The ID token (a JWT) returned by Google Identity Services in the browser.
    credential: str
    remember_me: bool = False

class RefreshRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class UpdateEmailRequest(BaseModel):
    email: str

class UpdateNameRequest(BaseModel):
    name: str

class DeleteAccountRequest(BaseModel):
    # Current password, required to confirm an irreversible account deletion.
    password: str

class ForgotPasswordRequest(BaseModel):
    # Accept either a username or an email address in one field.
    identifier: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str

class AskQuestionRequest(BaseModel):
    birth_details: BirthDetails
    question: str
    llm_provider: str = "qwen"  # legacy: qwen, gemini, or chatgpt
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None   # ollama | openai-compatible | gemini | openai
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Max response length (output tokens). Optional; when set it overrides the
    # provider default so users can raise the cap if answers get cut off.
    max_tokens: Optional[int] = None
    # Context controls (optional)
    ayanamsa: Optional[str] = None
    sections: Optional[dict] = None  # toggle dasha_tree/yogas/doshas/transits
    vargas: Optional[list] = None    # divisional-chart factors, e.g. [1, 9, 10]
    # Answer mode: "pass_all" (default) pre-sends the full context; "tools" lets the
    # model fetch chart data on demand. Set per conversation (first turn wins).
    mode: Optional[str] = None
    # Conversation (save + multi-turn)
    conversation_id: Optional[str] = None
    profile_id: Optional[str] = None
    # Where the thread originated, so the Ask page can label/filter it:
    # "astrologer" (default) or "transit" (the Transits-page chat). Only honoured
    # when the conversation is first created.
    source: Optional[str] = None
    # When true, replace the last assistant answer instead of appending a new turn
    regenerate: bool = False

class PredictionRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    prediction_type: str = "general"  # general, health, career, relationships
    llm_provider: str = "qwen"  # legacy fallback
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None   # ollama | openai-compatible | gemini | openai
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Max response length (output tokens). Optional; when set it overrides the
    # provider default so users can raise the cap if answers get cut off.
    max_tokens: Optional[int] = None
    # Context controls (optional)
    ayanamsa: Optional[str] = None
    sections: Optional[dict] = None  # toggle dasha_tree/yogas/doshas/transits
    vargas: Optional[list] = None    # divisional-chart factors, e.g. [1, 9, 10]


class ShareRequest(BaseModel):
    birth_details: BirthDetails
    ayanamsa: Optional[str] = None
    profile_name: Optional[str] = None


class CompatibilityRequest(BaseModel):
    """Ashtakoot compatibility scoring. Flat birth fields for both partners —
    sent as a JSON body by the frontend (these were previously declared as bare
    function args, which FastAPI treated as query params)."""
    male_dob: str
    male_tob: str
    male_place: str
    female_dob: str
    female_tob: str
    female_place: str
    male_latitude: Optional[float] = None
    male_longitude: Optional[float] = None
    male_timezone: Optional[float] = None
    female_latitude: Optional[float] = None
    female_longitude: Optional[float] = None
    female_timezone: Optional[float] = None

class CompatibilityAnalysisRequest(BaseModel):
    male_details: BirthDetails
    female_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    llm_provider: str = "qwen"  # legacy fallback
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class CompareAnalysisRequest(BaseModel):
    person1_details: BirthDetails
    person2_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    person1_name: Optional[str] = None
    person2_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class SarvatobhadraAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    person_name: Optional[str] = None
    name_nakshatra: Optional[int] = None  # 1..27 naama-nakshatra (optional anchor)
    current_date: Optional[str] = None
    current_time: Optional[str] = None
    current_tz: Optional[float] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class VarshaphalAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    year: int
    person_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class PanchaPakshiAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    date: Optional[str] = None
    person_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class SensitivePointsAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    person_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class CelestialAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    date: Optional[str] = None
    person_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class AlmanacAnalysisRequest(BaseModel):
    # Location-driven (not birth-chart bound), so no BirthDetails.
    place: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None
    date: Optional[str] = None
    system: str = "drik"
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None

class RectifyExplainRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    method: str = "nakshatra"        # nakshatra | lagna | janma
    gender: Optional[int] = None     # 0=male, 1=female (janma suddhi only)
    person_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class RectifyEventItem(BaseModel):
    type: str                        # an EVENT_SIGNIFICATORS key
    date: str                        # YYYY-MM-DD

class RectifyEventsRequest(BaseModel):
    birth_details: BirthDetails
    events: List[RectifyEventItem] = []
    window_minutes: int = 120
    ayanamsa: Optional[str] = None

class RectifyEventsExplainRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    events: List[RectifyEventItem] = []
    window_minutes: int = 120
    person_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class RectifyChatMessage(BaseModel):
    role: str                        # "user" | "assistant"
    content: str

class RectifyChatRequest(BaseModel):
    birth_details: BirthDetails
    messages: List[RectifyChatMessage] = []
    collected_events: List[RectifyEventItem] = []
    person_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class MuhurtaAnalysisRequest(BaseModel):
    # Location-driven (not birth-chart bound).
    activity: str = "general"
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    place: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None

class PrashnaAnalysisRequest(BaseModel):
    # Horary — cast for the moment (no birth data). All optional → "now + here".
    question: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    place: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class DailyDigestAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    date: Optional[str] = None
    current_time: Optional[str] = None
    current_tz: Optional[float] = None
    person_name: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class MuhurtaSubtoolsRequest(BaseModel):
    # Day-level muhurta helpers. Location-driven; birth_details optional and only
    # used to personalize Tarabala / Chandrabala.
    date: Optional[str] = None
    place: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None
    birth_details: Optional[BirthDetails] = None

class BhriguMarkersAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    from_age: Optional[int] = None
    years: Optional[int] = 12
    person_name: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class RemediesAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    person_name: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class KPAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None
    person_name: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None  # KP forces its own ayanamsa; kept for parity

class KPHoraryAnalysisRequest(BaseModel):
    number: int
    question: Optional[str] = None
    date: Optional[str] = None
    time: Optional[str] = None
    place: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None
    profile_id: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None

class JaiminiAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None
    person_name: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class NowChartAnalysisRequest(BaseModel):
    # Location-driven "chart of the moment" (not birth-chart bound).
    place: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None
    current_time: Optional[str] = None
    current_tz: Optional[float] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class NotificationPrefsRequest(BaseModel):
    daily_digest: Optional[bool] = None
    email: Optional[bool] = None
    push: Optional[bool] = None
    profile_id: Optional[str] = None
    profile_ids: Optional[List[str]] = None
    all_profiles: Optional[bool] = None
    include_ai: Optional[bool] = None
    hour: Optional[int] = None
    # Per-cadence weekly / monthly readings (each with its own day + hour).
    weekly: Optional[bool] = None
    weekly_dow: Optional[int] = None       # 0=Mon..6=Sun
    weekly_hour: Optional[int] = None
    monthly: Optional[bool] = None
    monthly_dom: Optional[int] = None      # 1-28
    monthly_hour: Optional[int] = None

class PushSubscribeRequest(BaseModel):
    # A browser PushSubscription JSON (endpoint + keys).
    subscription: dict

class PushUnsubscribeRequest(BaseModel):
    endpoint: str

# Lifecycle events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
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

security = HTTPBearer()

# ============= AUTH ROUTES =============

async def _issue_token_pair(username: str, remember_me: bool = False) -> dict:
    """Mint a short-lived access token + a long-lived refresh token for a user."""
    access_token = create_access_token(
        data={"sub": username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    days = settings.REFRESH_TOKEN_EXPIRE_DAYS if remember_me else settings.REFRESH_TOKEN_SHORT_DAYS
    refresh_token = await refresh_tokens.issue(username, days)
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": refresh_token}


@app.post("/api/auth/register", response_model=Token)
async def register(req: RegisterRequest):
    """Register a new user"""
    try:
        from database import database
        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        name = (req.name or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="Please enter your name")

        users_collection = database["users"]

        # Check if user exists
        existing = await users_collection.find_one({"username": req.username})
        if existing:
            raise HTTPException(status_code=400, detail="Username already registered")

        # Create new user
        hashed_password = get_password_hash(req.password)
        user_doc = {
            "username": req.username,
            "email": req.email,
            "name": name,
            "hashed_password": hashed_password,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await users_collection.insert_one(user_doc)

        return await _issue_token_pair(req.username, req.remember_me)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login", response_model=Token)
async def login(req: LoginRequest, request: Request):
    """Login user and return token"""
    try:
        from database import database
        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        # Brute-force guard: throttle by client IP after repeated failures.
        client_ip = request.client.host if request.client else "unknown"
        allowed, retry_after = ratelimit.login_allowed(client_ip)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Too many failed login attempts. Try again in {retry_after}s.",
                headers={"Retry-After": str(retry_after)},
            )

        users_collection = database["users"]
        user = await users_collection.find_one({"username": req.username})

        if not user or not verify_password(req.password, user.get("hashed_password") or ""):
            ratelimit.login_failed(client_ip)
            raise HTTPException(status_code=401, detail="Invalid credentials")

        ratelimit.login_succeeded(client_ip)
        return await _issue_token_pair(req.username, req.remember_me)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/google", response_model=Token)
async def google_auth(req: GoogleAuthRequest):
    """Sign in (or register) with Google. The frontend obtains a Google Identity
    Services ID token; here we verify it against our OAuth client, then find-or-
    create the user keyed on their verified email and issue our normal JWT pair.

    Account model (per product decision):
      • username == the Google email.
      • If a user with that email already exists (e.g. a prior password signup),
        we LINK Google to it and sign them straight in — same verified email is
        treated as the same account.
      • A Google-only user has no `hashed_password`; password login/change/delete
        paths tolerate that (they can set one later via forgot-password).
    """
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")

    from database import database
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    # Verify the ID token: checks Google's signature, expiry, and that the token's
    # audience is our client ID. Raises ValueError on any mismatch.
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests
        idinfo = google_id_token.verify_oauth2_token(
            req.credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid Google token")
    except Exception as e:
        print(f"Google auth error: {e}")
        raise HTTPException(status_code=502, detail="Could not verify Google sign-in")

    email = (idinfo.get("email") or "").strip().lower()
    google_sub = idinfo.get("sub")
    if not email or not idinfo.get("email_verified") or not google_sub:
        raise HTTPException(status_code=401, detail="Google account has no verified email")

    users_collection = database["users"]
    # Prefer matching a previously linked Google account; fall back to email so an
    # existing password account with the same email gets linked rather than duping.
    user = await users_collection.find_one(
        {"$or": [{"google_sub": google_sub}, {"email": email}, {"username": email}]}
    )

    if user:
        username = user["username"]
        # Backfill link fields on first Google sign-in for a pre-existing account.
        updates = {}
        if user.get("google_sub") != google_sub:
            updates["google_sub"] = google_sub
        if not user.get("auth_provider"):
            updates["auth_provider"] = "google"
        # Fill in a display name from Google only if the account doesn't have one
        # yet — never clobber a name the user set themselves.
        if not user.get("name") and idinfo.get("name"):
            updates["name"] = idinfo.get("name")
        if updates:
            await users_collection.update_one({"username": username}, {"$set": updates})
    else:
        username = email
        await users_collection.insert_one({
            "username": username,
            "email": email,
            "google_sub": google_sub,
            "auth_provider": "google",
            "name": idinfo.get("name"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return await _issue_token_pair(username, req.remember_me)


@app.post("/api/auth/refresh", response_model=Token)
async def refresh(req: RefreshRequest):
    """Exchange a valid refresh token for a fresh access token. The refresh token
    is rotated (the old one is revoked, a new one returned) so a leaked token is
    single-use."""
    username, new_refresh = await refresh_tokens.rotate(req.refresh_token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token = create_access_token(
        data={"sub": username},
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer", "refresh_token": new_refresh}


@app.post("/api/auth/logout")
async def logout(req: LogoutRequest):
    """Revoke the presented refresh token so it can't mint new access tokens."""
    if req.refresh_token:
        await refresh_tokens.revoke(req.refresh_token)
    return {"status": "ok"}

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify token and return username"""
    username = decode_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return username


@app.post("/api/auth/change-password", response_model=Token)
async def change_password(req: ChangePasswordRequest, current_user: str = Depends(get_current_user)):
    """Change the logged-in user's password. Verifies the current password
    (unless the account is Google-only and has none yet — then this sets the
    first password), revokes all existing refresh tokens (logging out other
    devices), and returns a fresh token pair so the current session stays in."""
    from database import database
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    if len(req.new_password or "") < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    users_collection = database["users"]
    user = await users_collection.find_one({"username": current_user})
    if not user:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    existing_hash = user.get("hashed_password")
    # A Google-only account has no password yet — let it set a first one without
    # a current password. An account that already has a password must verify it.
    if existing_hash and not verify_password(req.current_password, existing_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    await users_collection.update_one(
        {"username": current_user},
        {"$set": {"hashed_password": get_password_hash(req.new_password)}},
    )
    # Invalidate every existing session, then hand this one a fresh pair.
    await refresh_tokens.revoke_all(current_user)
    return await _issue_token_pair(current_user, remember_me=True)


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@app.put("/api/auth/email")
async def update_email(req: UpdateEmailRequest, current_user: str = Depends(get_current_user)):
    """Update the logged-in user's email address."""
    from database import database
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    email = (req.email or "").strip()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address")

    users_collection = database["users"]
    # Reject if another account already uses this email.
    clash = await users_collection.find_one(
        {"email": email, "username": {"$ne": current_user}}
    )
    if clash:
        raise HTTPException(status_code=400, detail="That email is already in use")

    result = await users_collection.update_one(
        {"username": current_user}, {"$set": {"email": email}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "email": email}


@app.put("/api/auth/name")
async def update_name(req: UpdateNameRequest, current_user: str = Depends(get_current_user)):
    """Update the logged-in user's display name."""
    from database import database
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Please enter your name")
    if len(name) > 100:
        raise HTTPException(status_code=400, detail="Name is too long")

    result = await database["users"].update_one(
        {"username": current_user}, {"$set": {"name": name}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
    return {"success": True, "name": name}


@app.post("/api/auth/logout-all", response_model=Token)
async def logout_all(current_user: str = Depends(get_current_user)):
    """Revoke every refresh token for this user (signing out all other devices),
    then hand the current session a fresh pair so it stays signed in."""
    await refresh_tokens.revoke_all(current_user)
    return await _issue_token_pair(current_user, remember_me=True)


# Every Mongo collection that stores rows scoped to a user, and the field its
# owner is keyed on. Used to fully purge an account on deletion.
_USER_SCOPED_COLLECTIONS = [
    ("saved_profiles", "user_id"),
    ("charts", "user_id"),
    ("user_settings", "user_id"),
    ("ai_conversations", "user_id"),
    ("ai_tool_traces", "user_id"),
    ("shared_charts", "user_id"),
    ("quiz_sessions", "user_id"),
    ("push_subscriptions", "user_id"),
    ("refresh_tokens", "username"),
    ("password_reset_tokens", "username"),
]


@app.delete("/api/auth/account")
async def delete_account(req: DeleteAccountRequest, current_user: str = Depends(get_current_user)):
    """Permanently delete the logged-in user's account and cascade-delete all of
    their data (birth profiles, saved charts, AI conversations + tool traces,
    shared-chart links, quiz sessions, settings and refresh tokens). Requires the
    current password as a confirmation. Irreversible."""
    from database import database
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")

    users_collection = database["users"]
    user = await users_collection.find_one({"username": current_user})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Password accounts must re-enter their password to confirm. Google-only
    # accounts have none, so the (already-required) valid access token is the
    # confirmation — they can set a password first via forgot-password if desired.
    if user.get("hashed_password"):
        if not verify_password(req.password, user["hashed_password"]):
            raise HTTPException(status_code=400, detail="Password is incorrect")

    # Cascade: wipe every user-scoped collection, then the user row itself.
    for name, field in _USER_SCOPED_COLLECTIONS:
        try:
            await database[name].delete_many({field: current_user})
        except Exception as e:
            # Don't abort the whole deletion if one collection is missing/errors.
            print(f"delete_account: failed clearing {name}: {e}")
    await users_collection.delete_one({"username": current_user})
    return {"success": True, "message": "Account deleted"}


@app.post("/api/auth/forgot-password")
async def forgot_password(req: ForgotPasswordRequest, request: Request):
    """Begin a password reset. Looks the user up by username OR email, issues a
    single-use reset token and emails the reset link. To avoid leaking which
    accounts exist, the response is ALWAYS the same generic success — regardless
    of whether the identifier matched or whether email is even configured."""
    generic = {
        "status": "ok",
        "message": "If an account matches, a reset link has been sent.",
        "email_configured": email_service.is_configured(),
    }
    try:
        from database import database
        if database is None:
            return generic
        ident = (req.identifier or "").strip()
        if not ident:
            return generic
        # Throttle by IP to blunt enumeration/spam (reuse the login limiter).
        client_ip = request.client.host if request.client else "unknown"
        allowed, _ = ratelimit.login_allowed(client_ip)
        if not allowed:
            return generic

        user = await database["users"].find_one(
            {"$or": [{"username": ident}, {"email": ident}]}
        )
        if user and user.get("email"):
            token = await password_reset.issue(user["username"])
            reset_url = f"{settings.APP_BASE_URL.rstrip('/')}/reset-password?token={token}"
            await email_service.send_password_reset(
                user["email"], reset_url, settings.PASSWORD_RESET_TTL_MINUTES)
    except Exception as e:
        print(f"forgot_password error: {e}")
    return generic


@app.post("/api/auth/reset-password", response_model=Token)
async def reset_password(req: ResetPasswordRequest):
    """Complete a password reset with the emailed token. Consumes the token
    (single-use), sets the new password, revokes all existing sessions, and
    returns a fresh token pair so the user is signed straight in."""
    from database import database
    if database is None:
        raise HTTPException(status_code=500, detail="Database not connected")
    if len((req.new_password or "")) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    username = await password_reset.consume(req.token)
    if not username:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has expired")

    await database["users"].update_one(
        {"username": username},
        {"$set": {"hashed_password": get_password_hash(req.new_password)}},
    )
    await refresh_tokens.revoke_all(username)
    return await _issue_token_pair(username, remember_me=True)

# ============= ASTROLOGY ROUTES =============

@app.post("/api/astrology/birth-chart")
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

@app.get("/api/astrology/ayanamsas")
async def list_ayanamsas():
    """Supported ayanamsa options for chart calculation."""
    return {
        "default": DEFAULT_AYANAMSA,
        "options": [{"value": k, "label": v} for k, v in SUPPORTED_AYANAMSAS.items()],
    }

@app.get("/api/astrology/vargas")
async def list_vargas():
    """Supported divisional (varga) charts for the varga picker."""
    return {
        "options": [
            {"value": factor, "code": code, "name": name, "significance": significance}
            for factor, (code, name, significance) in SUPPORTED_VARGAS.items()
        ]
    }

@app.post("/api/astrology/divisional-chart")
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

@app.get("/api/astrology/panchanga")
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

@app.get("/api/astrology/almanac/hora")
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

@app.get("/api/astrology/almanac/eclipses")
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

@app.get("/api/astrology/almanac/festivals")
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

@app.get("/api/astrology/almanac/conjunctions")
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

@app.post("/api/astrology/sensitive-points")
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

@app.post("/api/astrology/vedic-clock")
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

@app.post("/api/astrology/retrograde")
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

@app.get("/api/astrology/birth-chart/{chart_id}")
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

@app.post("/api/astrology/horoscope")
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

@app.post("/api/astrology/doshas")
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

@app.post("/api/astrology/yogas")
async def get_yogas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Get yogas"""
    try:
        yogas = AstrologyCompute.get_yogas(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa
        )
        return yogas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/dhasa")
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

@app.post("/api/astrology/dhasa/children")
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

@app.get("/api/astrology/dasha-systems")
async def list_dasha_systems(current_user: str = Depends(get_current_user)):
    """List the supported non-Vimsottari dasha systems."""
    return {
        "systems": [
            {"key": k, "name": v["name"], "lord_type": v["lord_type"],
             "description": v["description"]}
            for k, v in SUPPORTED_DASHAS.items()
        ]
    }

@app.post("/api/astrology/dasha-periods")
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

@app.post("/api/astrology/ashtakavarga")
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

@app.post("/api/astrology/aspects")
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

@app.post("/api/astrology/varshaphal")
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

@app.post("/api/astrology/raja-yogas")
async def get_raja_yogas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Dedicated Raja Yoga analysis (Kendra-Trikona pairs + named special types)."""
    try:
        result = AstrologyCompute.get_raja_yogas(
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

@app.post("/api/astrology/longevity")
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

@app.post("/api/astrology/sudarsana-chakra")
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

@app.post("/api/astrology/pancha-pakshi")
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

@app.post("/api/astrology/rectify-birth-time")
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

@app.post("/api/astrology/rectify-birth-time/events")
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

@app.post("/api/astrology/chart-details")
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

@app.post("/api/astrology/shadbala")
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

@app.post("/api/astrology/share")
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


@app.get("/api/astrology/share/{token}")
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


@app.post("/api/astrology/transit")
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

@app.post("/api/astrology/bhava-chart")
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

@app.get("/api/astrology/ephemeris")
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

@app.post("/api/astrology/compatibility")
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

# ============= USER ROUTES =============

@app.get("/api/user/profile")
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

@app.get("/api/user/charts")
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

# ============= LLM Q&A ROUTES =============

@app.get("/api/llm/providers")
async def list_llm_providers(current_user: str = Depends(get_current_user)):
    """List available AI providers, their reachability, and installed/known models.

    Availability also reflects the calling user's own stored API keys."""
    try:
        user_keys = await user_settings.get_user_keys(current_user)
        providers = await llm_service.list_providers(user_keys)
        return {"providers": providers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/tools")
async def list_ai_tools():
    """The catalog of tools the AI astrologer can call while answering. Static,
    user-independent capability disclosure for the 'What the AI can do' page."""
    return {"tools": tool_registry.tool_catalog()}


async def _resolve_cfg(current_user: str, request: "AskQuestionRequest"):
    """Resolve the model config, falling back to the user's stored API key when
    the request didn't carry an explicit key and no env key is configured."""
    cfg = llm_service.resolve_config(
        provider_type=request.provider_type,
        model=request.model,
        base_url=request.base_url,
        api_key=request.api_key,
        legacy_provider=request.llm_provider,
    )
    if not cfg.api_key and cfg.provider_type.value in user_settings.KEYED_PROVIDERS:
        stored = await user_settings.get_api_key(current_user, cfg.provider_type.value)
        if stored:
            cfg.api_key = stored
    # Optional per-user output cap from Settings (lets a user raise the limit if
    # answers get cut off). Clamped to a sane range; None → provider defaults.
    mt = getattr(request, "max_tokens", None)
    if mt:
        cfg.max_tokens = max(256, min(int(mt), 32768))
    return cfg


def _enforce_rate_limit(current_user: str):
    allowed, retry_after, reason = ratelimit.check(current_user)
    if not allowed:
        raise HTTPException(
            status_code=429, detail=reason,
            headers={"Retry-After": str(retry_after)},
        )

@app.post("/api/astrology/ask")
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

def _resolve_mode(request: "AskQuestionRequest", conv: Optional[dict]) -> str:
    """The effective answer mode. A conversation's mode is fixed on its first turn,
    so follow-ups inherit it; a brand-new conversation takes the request's mode."""
    if conv and conv.get("mode"):
        return conv["mode"]
    m = request.mode or "pass_all"
    return m if m in ("pass_all", "tools") else "pass_all"


async def _save_turn(user_id: str, request: "AskQuestionRequest", cfg, chart_data: dict,
                     answer: str, elapsed_ms: Optional[int] = None,
                     usage: Optional[dict] = None, mode: str = "pass_all",
                     tool_trace: Optional[list] = None) -> str:
    """Persist a user question + assistant answer, creating the conversation if new.

    When `request.regenerate` is set and a conversation exists, the previous
    assistant answer is replaced in place (no duplicate question/answer turn)."""
    conv_id = request.conversation_id
    if not conv_id:
        conv_id = await convo.create_conversation(
            user_id, request.profile_id, request.question,
            request.birth_details.model_dump(), mode=mode,
            source=request.source or "astrologer",
        )
    now = datetime.now(timezone.utc).isoformat()
    ai_msg = {
        "role": "assistant", "content": answer, "ts": now,
        "provider": cfg.provider_type.value, "model": cfg.model,
        "vargas": chart_data.get("_vargas", []),
        "sections": chart_data.get("_sections", {}),
        "elapsed_ms": elapsed_ms,
    }
    if usage:
        ai_msg["usage"] = usage
    if tool_trace:
        # Keep only the light trace (name/args/ok) on the message so listing/loading
        # stays fast; stash the full per-call results in the side collection keyed by
        # an opaque trace_id, fetched lazily when the user opens "Behind the scenes".
        trace_id = uuid.uuid4().hex
        ai_msg["trace_id"] = trace_id
        ai_msg["tool_trace"] = [
            {"name": e.get("name"), "args": e.get("args", {}), "ok": e.get("ok")}
            for e in tool_trace
        ]
        full = [e for e in tool_trace if e.get("result") is not None]
        if full:
            await tool_traces.save_trace(user_id, conv_id, trace_id, full)
    if request.regenerate and request.conversation_id:
        await convo.replace_last_assistant(user_id, conv_id, ai_msg)
    else:
        user_msg = {"role": "user", "content": request.question, "ts": now}
        await convo.append_messages(user_id, conv_id, [user_msg, ai_msg])
    return conv_id


async def _save_reading(user_id: str, *, source: str, title: str, text: str,
                        context: Optional[dict] = None,
                        profile_id: Optional[str] = None,
                        birth_details: Optional[dict] = None,
                        cfg=None, request_label: Optional[str] = None) -> None:
    """Best-effort persist of a single-shot AI reading into the unified history so
    it appears alongside chats and can be reopened on its source page. Failures are
    swallowed — persistence must never break the actual reading response."""
    if not text:
        return
    try:
        await convo.save_reading(
            user_id, source=source, title=title, text=text,
            context=context, profile_id=profile_id, birth_details=birth_details,
            model=(cfg.model if cfg else None),
            provider=(cfg.provider_type.value if cfg else None),
            request_label=request_label,
        )
    except Exception as e:  # pragma: no cover - defensive
        print(f"Failed to persist reading ({source}): {e}")


@app.post("/api/astrology/ask/stream")
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


@app.get("/api/ai/conversations")
async def list_ai_conversations(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """List the current user's saved AI conversations (optionally for one profile)."""
    try:
        return {"conversations": await convo.list_conversations(current_user, profile_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/conversations/{conversation_id}")
async def get_ai_conversation(
    conversation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Fetch a full conversation thread."""
    c = await convo.get_conversation(current_user, conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo.serialize_conversation(c)


@app.get("/api/ai/conversations/{conversation_id}/traces/{trace_id}")
async def get_ai_trace(
    conversation_id: str,
    trace_id: str,
    current_user: str = Depends(get_current_user)
):
    """Fetch the full per-call tool results for one smart-lookup answer (the
    "Behind the scenes" data), loaded lazily so threads stay light."""
    doc = await tool_traces.get_trace(current_user, trace_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Trace not found")
    return doc


@app.delete("/api/ai/conversations/{conversation_id}")
async def delete_ai_conversation(
    conversation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a conversation (and any stored tool traces)."""
    ok = await convo.delete_conversation(current_user, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await tool_traces.delete_for_conversation(current_user, conversation_id)
    return {"success": True}


class FeedbackRequest(BaseModel):
    message_index: int
    rating: Optional[str] = None  # "up" | "down" | null to clear


@app.post("/api/ai/conversations/{conversation_id}/feedback")
async def submit_feedback(
    conversation_id: str,
    request: FeedbackRequest,
    current_user: str = Depends(get_current_user)
):
    """Store thumbs up/down on a specific assistant message in a conversation."""
    if request.rating not in (None, "", "up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up', 'down', or null")
    ok = await convo.set_feedback(current_user, conversation_id,
                                  request.message_index, request.rating)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True}


# ============= PER-USER API KEYS =============

class ApiKeyRequest(BaseModel):
    api_key: str


@app.get("/api/user/api-keys")
async def get_api_keys(current_user: str = Depends(get_current_user)):
    """Per-provider key status for the current user (masked — never the raw key)."""
    return {"keys": await user_settings.get_key_status(current_user)}


@app.put("/api/user/api-keys/{provider}")
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


@app.delete("/api/user/api-keys/{provider}")
async def remove_api_key(
    provider: str,
    current_user: str = Depends(get_current_user)
):
    """Remove the user's stored API key for one provider."""
    if provider not in user_settings.KEYED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'.")
    await user_settings.delete_api_key(current_user, provider)
    return {"success": True, "provider": provider}


class PreferencesRequest(BaseModel):
    preferences: Dict[str, Any] = {}


@app.get("/api/user/preferences")
async def get_preferences(current_user: str = Depends(get_current_user)):
    """The user's cross-device UI preferences (currently the LLM provider/model)."""
    return {"preferences": await user_settings.get_preferences(current_user)}


@app.put("/api/user/preferences")
async def put_preferences(
    request: PreferencesRequest,
    current_user: str = Depends(get_current_user),
):
    """Store a partial set of the user's synced UI preferences."""
    prefs = await user_settings.set_preferences(current_user, request.preferences or {})
    return {"preferences": prefs}


@app.post("/api/astrology/predict")
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

@app.post("/api/astrology/compatibility-analysis")
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

        # Resolve the model config (request key → user's stored key → env key)
        cfg = await _resolve_cfg(current_user, request)

        # Get AI analysis
        ai_analysis = await llm_service.analyze_compatibility(
            male_chart=male_chart,
            female_chart=female_chart,
            koota_score=compatibility.get("total_score", 0),
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

@app.post("/api/astrology/compare-analysis")
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

# ============= SARVATOBHADRA CHAKRA =============

@app.post("/api/astrology/sarvatobhadra")
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


@app.post("/api/astrology/sarvatobhadra-analysis")
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

@app.post("/api/astrology/sensitive-points-analysis")
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

@app.post("/api/astrology/celestial-analysis")
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

@app.post("/api/astrology/almanac-analysis")
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

# ============= MUHURTA / PRASHNA / DAILY DIGEST (§16) =============

@app.post("/api/astrology/muhurta")
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

@app.post("/api/astrology/muhurta-analysis")
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

@app.post("/api/astrology/muhurta/subtools")
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

@app.post("/api/astrology/prashna")
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

@app.post("/api/astrology/prashna-analysis")
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

@app.post("/api/astrology/daily-digest")
async def get_daily_digest(
    birth_details: BirthDetails,
    date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Personalized 'Today' digest — panchanga + dasha + headline transits."""
    try:
        result = AstrologyCompute.get_daily_digest(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, date=date, current_time=current_time,
            current_tz=current_tz, ayanamsa=ayanamsa)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/daily-digest-analysis")
async def analyze_daily_digest(
    request: DailyDigestAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, personalized AI reading of today's digest."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_daily_digest(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, date=request.date,
            current_time=request.current_time, current_tz=request.current_tz,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
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
                     "ayanamsa": request.ayanamsa},
        )
        return {"ai_analysis": ai_analysis, "provider": cfg.provider_type.value,
                "model": cfg.model}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/weekly-digest")
async def get_weekly_digest(
    birth_details: BirthDetails,
    date: Optional[str] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Personalized 'This Week' reading — dasha context + the next 7 days' transits."""
    try:
        result = AstrologyCompute.get_weekly_digest(
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

@app.post("/api/astrology/monthly-digest")
async def get_monthly_digest(
    birth_details: BirthDetails,
    date: Optional[str] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Personalized 'This Month' reading — dasha context + the Maasa Pravesha
    (Tajaka monthly) chart and the solar month's transit events."""
    try:
        result = AstrologyCompute.get_monthly_digest(
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

@app.post("/api/astrology/weekly-digest-analysis")
async def analyze_weekly_digest(
    request: DailyDigestAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, personalized AI reading of the week-ahead digest."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_weekly_digest(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, date=request.date,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_weekly_digest(
            digest_data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="weekly_digest",
            title=f"Weekly digest — {result.get('start_date')} · {request.person_name or bd.name or 'chart'}",
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

@app.post("/api/astrology/monthly-digest-analysis")
async def analyze_monthly_digest(
    request: DailyDigestAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Warm, personalized AI reading of the month-ahead (Maasa Pravesha) digest."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        result = AstrologyCompute.get_monthly_digest(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, date=request.date,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA)
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_monthly_digest(
            digest_data=result, name=request.person_name or bd.name or "this person", config=cfg)
        await _save_reading(
            current_user, source="monthly_digest",
            title=f"Monthly digest — {result.get('start_date')} · {request.person_name or bd.name or 'chart'}",
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

# ============= NADI / BHRIGU YEARLY MARKERS + REMEDIES =============

@app.post("/api/astrology/bhrigu-markers")
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

@app.post("/api/astrology/bhrigu-markers-analysis")
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

@app.post("/api/astrology/remedies")
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

@app.post("/api/astrology/remedies-analysis")
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

# ============= KP (KRISHNAMURTI PADDHATI) · JAIMINI · NOW-CHART (§16) =============

@app.post("/api/astrology/kp")
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

@app.post("/api/astrology/kp-analysis")
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

@app.post("/api/astrology/kp-horary")
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

@app.post("/api/astrology/kp-horary-analysis")
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

@app.post("/api/astrology/jaimini")
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

@app.post("/api/astrology/jaimini-analysis")
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

@app.post("/api/astrology/now-chart")
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

@app.post("/api/astrology/now-chart-analysis")
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

# ============= NOTIFICATIONS (digest prefs + web push) =============

@app.get("/api/notifications/prefs")
async def get_notification_prefs(current_user: str = Depends(get_current_user)):
    prefs = await notifications.get_prefs(current_user)
    return {"prefs": prefs, "push_available": notifications.push_enabled(),
            "email_available": email_service.is_configured(),
            "vapid_public_key": notifications.vapid_public_key()}

@app.put("/api/notifications/prefs")
async def set_notification_prefs(
    req: NotificationPrefsRequest,
    current_user: str = Depends(get_current_user),
):
    prefs = await notifications.set_prefs(
        current_user, {k: v for k, v in req.model_dump().items() if v is not None})
    return {"prefs": prefs}

@app.post("/api/notifications/push/subscribe")
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

@app.post("/api/notifications/push/unsubscribe")
async def push_unsubscribe(
    req: PushUnsubscribeRequest,
    current_user: str = Depends(get_current_user),
):
    removed = await notifications.delete_subscription(current_user, req.endpoint)
    return {"status": "ok", "removed": removed}

@app.post("/api/notifications/digest/send")
async def send_digest_now(cadence: str = "daily",
                          current_user: str = Depends(get_current_user)):
    """Compute the current user's digest for `cadence` (daily/weekly/monthly) and
    deliver it on their enabled channels (email / push). Returns what was sent.
    Shares its delivery logic with the background scheduler
    (`digest.send_digest_for_user`); a user triggers this as a test from Settings,
    or a deployer's cron can hit it per user + cadence."""
    cadence = (cadence or "daily").lower()
    if cadence not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="cadence must be daily, weekly or monthly")
    prefs = await notifications.get_prefs(current_user)
    # The daily switch is `daily_digest`; weekly/monthly are named for the cadence.
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

@app.post("/api/astrology/varshaphal-analysis")
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

@app.post("/api/astrology/pancha-pakshi-analysis")
async def analyze_pancha_pakshi(
    request: PanchaPakshiAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of today's Pancha Pakshi timing — what to do/avoid."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        pp = AstrologyCompute.get_pancha_pakshi(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            date=request.date,
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

@app.post("/api/astrology/rectify-birth-time/explain")
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

@app.post("/api/astrology/rectify-birth-time/events/explain")
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

@app.post("/api/astrology/rectify-birth-time/chat")
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

# ============= LEARN THE CHART (AI QUIZ) =============

QUIZ_TOPICS = ("planets", "yogas", "dashas", "vargas")
QUIZ_LEVELS = ("beginner", "intermediate", "advanced")


def _quiz_context(birth_details: dict, topics: list, ayanamsa: str) -> dict:
    """Build a chart context tailored to the quiz topics. The full /ask context
    (ashtakavarga + shadbala + every varga) is ~3.5k tokens — too big for small
    local models, which then exhaust their output budget and return nothing. Only
    pull the sections a topic actually needs."""
    sections = {"dasha_tree": False, "yogas": False, "doshas": False,
                "transits": False, "ashtakavarga": False, "shadbala": False}
    vargas = [1]
    if "yogas" in topics:
        sections["yogas"] = True
        sections["doshas"] = True
    if "dashas" in topics:
        sections["dasha_tree"] = True
        sections["transits"] = True
    if "vargas" in topics:
        vargas = [1, 9, 10]
    return build_chart_context(
        birth_details=birth_details, ayanamsa=ayanamsa,
        sections=sections, vargas=vargas,
    )


class QuizGenerateRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None
    topics: Optional[list] = None        # subset of planets/yogas/dashas/vargas
    level: str = "beginner"              # beginner|intermediate|advanced
    adaptive: bool = False               # when true, level is chosen from the user's stats
    num_mcq: int = 5
    num_free: int = 3
    # Model selection (same shape as the other AI endpoints; used by _resolve_cfg)
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None


class QuizGradeRequest(BaseModel):
    session_id: str
    answers: dict                        # {question_id: answer}  (str for free, int index for mcq)
    # Model selection (free-text grading uses the AI; MCQ is graded deterministically)
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Optional per-user output cap (output tokens); honored via _resolve_cfg.
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None


@app.post("/api/astrology/quiz/generate")
async def quiz_generate(
    request: QuizGenerateRequest,
    current_user: str = Depends(get_current_user),
):
    """Generate an AI quiz grounded in this chart's computed facts. Returns the
    questions WITHOUT their answer keys (kept server-side until grading)."""
    _enforce_rate_limit(current_user)
    try:
        topics = [t for t in (request.topics or []) if t in QUIZ_TOPICS] or list(QUIZ_TOPICS)
        level = request.level if request.level in QUIZ_LEVELS else "beginner"
        num_mcq = max(0, min(10, int(request.num_mcq)))
        num_free = max(0, min(10, int(request.num_free)))
        if num_mcq + num_free == 0:
            raise HTTPException(status_code=422, detail="Ask for at least one question.")

        # Adaptive: pick the level (and emphasise weak topics) from the user's history.
        focus_note = ""
        if request.adaptive:
            stats = await quiz.get_stats(current_user, request.profile_id)
            level = quiz.suggest_level(stats.get("overall_avg"))
            weak = [t for t in stats.get("weak_topics", []) if t in topics]
            if weak:
                focus_note = ("Weight more questions toward these weaker topics: "
                              + ", ".join(weak))

        chart_data = _quiz_context(
            request.birth_details.model_dump(), topics,
            request.ayanamsa or DEFAULT_AYANAMSA,
        )
        cfg = await _resolve_cfg(current_user, request)
        items = await llm_service.generate_quiz(
            chart_data=chart_data, topics=topics, level=level,
            num_mcq=num_mcq, num_free=num_free, focus_note=focus_note, config=cfg,
        )
        session_id = await quiz.create_session(
            user_id=current_user, profile_id=request.profile_id,
            birth_details=request.birth_details.model_dump(), topics=topics,
            level=level, adaptive=request.adaptive, items=items,
            provider=cfg.provider_type.value, model=cfg.model,
        )
        return {
            "session_id": session_id,
            "topics": topics,
            "level": level,
            "adaptive": request.adaptive,
            "questions": quiz.public_items(items),
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/astrology/quiz/grade")
async def quiz_grade(
    request: QuizGradeRequest,
    current_user: str = Depends(get_current_user),
):
    """Grade a quiz: MCQ deterministically, free-text via the AI. Persists the
    result and returns per-question feedback + reasoning, score, and topic scores."""
    _enforce_rate_limit(current_user)
    try:
        session = await quiz.get_session(current_user, request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Quiz session not found.")
        if session.get("status") == "graded":
            raise HTTPException(status_code=409, detail="This quiz was already graded.")

        items = session.get("items", [])
        answers = request.answers or {}

        # MCQ — graded deterministically against the stored key.
        graded: dict = {}
        for it in items:
            if it.get("format") != "mcq":
                continue
            raw = answers.get(it["id"])
            try:
                chosen = int(raw)
            except (TypeError, ValueError):
                chosen = None
            correct = it.get("correct_index")
            is_correct = chosen is not None and chosen == correct
            graded[it["id"]] = {
                "score": 1.0 if is_correct else 0.0,
                "verdict": "correct" if is_correct else "incorrect",
                "chosen_index": chosen,
                "correct_index": correct,
                "reasoning": it.get("rationale", ""),
            }

        # Free-text — graded by the AI against expected points + chart facts.
        free_items = [it for it in items if it.get("format") == "free"]
        cfg = await _resolve_cfg(current_user, request)
        if free_items:
            chart_data = _quiz_context(
                session.get("birth_details", {}), session.get("topics", []),
                request.ayanamsa or DEFAULT_AYANAMSA,
            )
            free_grades = await llm_service.grade_quiz_answers(
                chart_data=chart_data, free_items=free_items, answers=answers, config=cfg,
            )
            for it in free_items:
                g = free_grades.get(it["id"], {
                    "score": 0.0, "verdict": "incorrect",
                    "what_was_right": "", "what_was_wrong": "Answer could not be graded.",
                    "reasoning": it.get("rationale", ""),
                })
                graded[it["id"]] = g

        # Assemble per-question result rows (reveal the answer key now).
        results = []
        for it in items:
            g = graded.get(it["id"], {})
            row = {
                "id": it["id"],
                "topic": it.get("topic"),
                "format": it.get("format"),
                "difficulty": it.get("difficulty"),
                "question": it.get("question"),
                "your_answer": answers.get(it["id"]),
                "score": g.get("score", 0.0),
                "verdict": g.get("verdict", "incorrect"),
                "reasoning": g.get("reasoning", it.get("rationale", "")),
            }
            if it.get("format") == "mcq":
                row["options"] = it.get("options", [])
                row["correct_index"] = it.get("correct_index")
                row["chosen_index"] = g.get("chosen_index")
            else:
                row["expected_points"] = it.get("expected_points", [])
                row["what_was_right"] = g.get("what_was_right", "")
                row["what_was_wrong"] = g.get("what_was_wrong", "")
            results.append(row)

        overall = round(sum(r["score"] for r in results) / len(results), 3) if results else 0.0
        topic_scores = quiz.compute_topic_scores(results)
        await quiz.save_grading(current_user, request.session_id, answers,
                                results, overall, topic_scores)
        return {
            "session_id": request.session_id,
            "score": overall,
            "topic_scores": topic_scores,
            "results": results,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/astrology/quiz/history")
async def quiz_history(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """List the user's past quiz sessions (optionally for one profile)."""
    sessions = await quiz.list_sessions(current_user, profile_id)
    return {"sessions": sessions}


@app.get("/api/astrology/quiz/stats")
async def quiz_stats(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """Per-topic mastery, overall average, streak and weak areas for the user."""
    return await quiz.get_stats(current_user, profile_id)


@app.delete("/api/astrology/quiz/{session_id}")
async def quiz_delete(
    session_id: str,
    current_user: str = Depends(get_current_user),
):
    ok = await quiz.delete_session(current_user, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Quiz session not found.")
    return {"status": "deleted"}

# ============= LOCATION SEARCH =============

class LocationSearchRequest(BaseModel):
    query: str  # e.g., "Chennai, India" or "New York, USA"

@app.post("/api/location/search")
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


class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float

@app.post("/api/location/reverse")
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

# ============= SAVED PROFILES =============

class SaveProfileRequest(BaseModel):
    profile_name: str
    birth_details: BirthDetails
    is_default: bool = False

@app.post("/api/profiles/save")
async def save_profile(req: SaveProfileRequest, current_user: str = Depends(get_current_user)):
    """Save a birth profile for quick access"""
    try:
        from database import database, SavedProfile

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        # If this is set as default, unset all other defaults
        if req.is_default:
            await profiles_collection.update_many(
                {"user_id": current_user},
                {"$set": {"is_default": False}}
            )

        # Create profile
        profile = SavedProfile(
            user_id=current_user,
            profile_name=req.profile_name,
            birth_details=req.birth_details,
            is_default=req.is_default
        )

        result = await profiles_collection.insert_one(profile.model_dump(by_alias=True, exclude={"id"}))

        return {
            "success": True,
            "profile_id": str(result.inserted_id),
            "message": f"Profile '{req.profile_name}' saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/profiles/{profile_id}")
async def update_profile(profile_id: str, req: SaveProfileRequest, current_user: str = Depends(get_current_user)):
    """Update an existing birth profile"""
    try:
        from database import database
        from bson import ObjectId

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        # Note: default status is managed only via /api/profiles/{id}/default,
        # so editing a profile never changes which profile is the default.
        result = await profiles_collection.update_one(
            {"_id": ObjectId(profile_id), "user_id": current_user},
            {"$set": {
                "profile_name": req.profile_name,
                "birth_details": req.birth_details.model_dump(),
            }}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "success": True,
            "message": f"Profile '{req.profile_name}' updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SetDefaultRequest(BaseModel):
    is_default: bool = True


@app.put("/api/profiles/{profile_id}/default")
async def set_default_profile(
    profile_id: str,
    req: SetDefaultRequest,
    current_user: str = Depends(get_current_user),
):
    """Mark a profile as the user's default (or clear it).

    Setting a profile default first clears every other profile's default, so at
    most one profile is ever the default. Passing ``is_default=false`` just clears
    this profile's flag, leaving the account with no default.
    """
    try:
        from database import database
        from bson import ObjectId

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        # Confirm the profile belongs to this user before mutating anything.
        target = await profiles_collection.find_one(
            {"_id": ObjectId(profile_id), "user_id": current_user}
        )
        if not target:
            raise HTTPException(status_code=404, detail="Profile not found")

        if req.is_default:
            await profiles_collection.update_many(
                {"user_id": current_user},
                {"$set": {"is_default": False}},
            )

        await profiles_collection.update_one(
            {"_id": ObjectId(profile_id), "user_id": current_user},
            {"$set": {"is_default": req.is_default}},
        )

        return {"success": True, "is_default": req.is_default}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/profiles/list")
async def list_profiles(current_user: str = Depends(get_current_user)):
    """Get all saved profiles for the current user"""
    try:
        from database import database

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        profiles = await profiles_collection.find({"user_id": current_user}).sort("created_at", -1).to_list(100)

        # Convert ObjectId to string
        for profile in profiles:
            profile["_id"] = str(profile["_id"])

        return {
            "success": True,
            "profiles": profiles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ImportProfileItem(BaseModel):
    profile_name: str
    birth_details: BirthDetails
    is_default: bool = False


class ImportProfilesRequest(BaseModel):
    profiles: List[ImportProfileItem]


@app.get("/api/profiles/export")
async def export_profiles(current_user: str = Depends(get_current_user)):
    """Export all of the current user's saved profiles as a portable JSON envelope.

    Only the birth data (profile name + birth details) is exported — no user ids or
    database ids — so the file can be re-imported into any account.
    """
    try:
        from database import database

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]
        profiles = await profiles_collection.find({"user_id": current_user}).sort("created_at", -1).to_list(1000)

        items = [
            {
                "profile_name": p.get("profile_name"),
                "birth_details": p.get("birth_details"),
                "is_default": p.get("is_default", False),
            }
            for p in profiles
        ]

        return {
            "app": "Jyotir AI",
            "type": "profiles",
            "version": 1,
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "count": len(items),
            "profiles": items,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/profiles/import")
async def import_profiles(req: ImportProfilesRequest, current_user: str = Depends(get_current_user)):
    """Import profiles from an exported JSON envelope.

    Duplicates (same profile name + date + time of birth) are skipped so re-importing
    the same file is safe. Imported profiles never override the account's default.
    """
    try:
        from database import database, SavedProfile

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        existing = await profiles_collection.find({"user_id": current_user}).to_list(1000)
        seen = {
            (p.get("profile_name"), (p.get("birth_details") or {}).get("dob"), (p.get("birth_details") or {}).get("tob"))
            for p in existing
        }

        docs = []
        skipped = 0
        for item in req.profiles:
            key = (item.profile_name, item.birth_details.dob, item.birth_details.tob)
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            profile = SavedProfile(
                user_id=current_user,
                profile_name=item.profile_name,
                birth_details=item.birth_details,
                is_default=False,  # never clobber the current default on import
            )
            docs.append(profile.model_dump(by_alias=True, exclude={"id"}))

        if docs:
            await profiles_collection.insert_many(docs)

        return {
            "success": True,
            "imported": len(docs),
            "skipped": skipped,
            "message": f"Imported {len(docs)} profile(s), skipped {skipped} duplicate(s)",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str, current_user: str = Depends(get_current_user)):
    """Delete a saved profile"""
    try:
        from database import database
        from bson import ObjectId

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        result = await profiles_collection.delete_one({
            "_id": ObjectId(profile_id),
            "user_id": current_user
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"success": True, "message": "Profile deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= HEALTH CHECK =============

@app.get("/health")
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)