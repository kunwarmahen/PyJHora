"""Pydantic request models for the API (§4b split).

Moved verbatim out of main.py; the old file defined these in two clusters
(a big block up top and a dozen more interleaved with the routes).
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

class ApiTokenCreateRequest(BaseModel):
    """Create a public-API / MCP token (§2.3). `label` helps the user tell tokens
    apart (e.g. 'Claude Desktop', 'my script')."""
    label: Optional[str] = None

class ToolRunRequest(BaseModel):
    """Run one astrology tool over the public API (§2.3). Provide EITHER a
    `profile_id` (one of the caller's saved profiles) OR inline `birth_details`.
    `args` are the tool-specific parameters (see GET /api/v1/tools for schemas)."""
    profile_id: Optional[str] = None
    birth_details: Optional[BirthDetails] = None
    ayanamsa: Optional[str] = None
    args: Optional[Dict[str, Any]] = None

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

class MarriageWorkspaceRequest(BaseModel):
    """7th-house marriage workspace for a couple (§2.6). BirthDetails for both
    partners — the dasha overlap + Saturn outlook + D1/D9 charts are composed on
    the frontend from the existing per-person endpoints."""
    male_details: BirthDetails
    female_details: BirthDetails
    ayanamsa: Optional[str] = None

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

class ChakraAnalysisRequest(BaseModel):
    """AI reading for the Kota / Tripataki chakras (§2.7). Same shape as the
    Sarvatobhadra request minus its name-nakshatra anchor, which those two
    chakras don't use."""
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    person_name: Optional[str] = None
    current_date: Optional[str] = None
    current_time: Optional[str] = None
    current_tz: Optional[float] = None
    # Tripataki only: "transit" (default) or "annual" (Varshaphal) + target year.
    basis: Optional[str] = None
    year: Optional[int] = None
    llm_provider: str = "qwen"  # legacy fallback
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
    # Pravesha basis: "solar" (Tajaka ladder) or "lunar" (tithi ladder).
    basis: Optional[str] = None
    # Which rung of the LUNAR ladder: tithi | paksha | month | annual (default).
    rung: Optional[str] = None
    year: Optional[int] = None  # Tithi Pravesha: target lunar-return year
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

class TimelineAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    target_date: str                  # the point on the timeline to read
    person_name: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class PlanetConditionsAnalysisRequest(BaseModel):
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

class AvasthasAnalysisRequest(BaseModel):
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

class StrengthAnalysisRequest(BaseModel):
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

class SaturnTransitsAnalysisRequest(BaseModel):
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

class NakshatraProfileAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    person_name: Optional[str] = None
    current_date: Optional[str] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class GocharaPhalaAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None  # for grouping the saved reading in history
    person_name: Optional[str] = None
    current_date: Optional[str] = None
    current_tz: Optional[float] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class LifeReportChapterRequest(BaseModel):
    birth_details: BirthDetails
    chapter_key: str
    profile_id: Optional[str] = None
    person_name: Optional[str] = None
    sections: Optional[dict] = None
    vargas: Optional[list] = None
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    ayanamsa: Optional[str] = None

class LifeReportSaveRequest(BaseModel):
    birth_details: BirthDetails
    markdown: str
    profile_id: Optional[str] = None
    person_name: Optional[str] = None
    ayanamsa: Optional[str] = None

class JournalEntryRequest(BaseModel):
    profile_id: Optional[str] = None
    birth_details: Optional[BirthDetails] = None  # to snapshot the running dasha
    date: str  # YYYY-MM-DD of the life event
    title: str
    category: str = "other"
    notes: str = ""
    ayanamsa: Optional[str] = None

class JournalUpdateRequest(BaseModel):
    birth_details: Optional[BirthDetails] = None
    date: Optional[str] = None
    title: Optional[str] = None
    category: Optional[str] = None
    notes: Optional[str] = None
    ayanamsa: Optional[str] = None

class FriendshipsAnalysisRequest(BaseModel):
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
    # Per-cadence fortnightly / monthly readings. The fortnight fires on the paksha
    # boundary, so it takes only an hour (no day picker).
    fortnightly: Optional[bool] = None
    fortnightly_hour: Optional[int] = None
    monthly: Optional[bool] = None
    monthly_dom: Optional[int] = None      # 1-28
    monthly_hour: Optional[int] = None
    # Pravesha ladder for the delivered readings: "solar" (Tajaka) or "lunar" (tithi).
    basis: Optional[str] = None

class PushSubscribeRequest(BaseModel):
    # A browser PushSubscription JSON (endpoint + keys).
    subscription: dict

class PushUnsubscribeRequest(BaseModel):
    endpoint: str


class FeedbackRequest(BaseModel):
    message_index: int
    rating: Optional[str] = None  # "up" | "down" | null to clear


# ============= PER-USER API KEYS =============

class ApiKeyRequest(BaseModel):
    api_key: str


class PreferencesRequest(BaseModel):
    preferences: Dict[str, Any] = {}


class ZoneLocationRequest(BaseModel):
    """Set the current location from a browser-reported IANA zone alone, by
    geocoding the zone's representative city. One click instead of typing a city
    the app already effectively knows."""
    timezone: str


class CurrentLocationRequest(BaseModel):
    """Where the user is now — NOT birth data. `timezone` is an IANA zone name
    ("America/Chicago"), not an offset: an offset can't carry DST. It's optional
    because the coordinates alone determine it."""
    place: str = ""
    latitude: float
    longitude: float
    timezone: Optional[str] = None


class TithiAshtottariChildrenRequest(BaseModel):
    """One period of the compressed Tithi Ashtottari, to be subdivided.

    A period is fully described by its start instant, lord and **degree** span, so
    the drill-down is stateless — no need to re-derive the tree from the pravesha
    moment on every expand. `start_jd` and `span_deg` come straight back from the
    parent row."""
    start_jd: float
    lord: int
    span_deg: float
    level: int
    latitude: float
    longitude: float
    timezone: float
    place: str = ""


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

# ============= LOCATION SEARCH =============

class LocationSearchRequest(BaseModel):
    query: str  # e.g., "Chennai, India" or "New York, USA"


class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float

# ============= SAVED PROFILES =============

class SaveProfileRequest(BaseModel):
    profile_name: str
    birth_details: BirthDetails
    is_default: bool = False
    notify_email: Optional[str] = None
    digest_frequency: Optional[str] = None
    # {place, latitude, longitude} of where this subject lives now; the zone is
    # derived server-side. Send null to clear it.
    current_location: Optional[Dict[str, Any]] = None


class SetDefaultRequest(BaseModel):
    is_default: bool = True

class ImportProfileItem(BaseModel):
    profile_name: str
    birth_details: BirthDetails
    is_default: bool = False


class ImportProfilesRequest(BaseModel):
    profiles: List[ImportProfileItem]
