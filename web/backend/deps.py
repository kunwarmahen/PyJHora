"""Shared dependencies + helpers for the route modules (§4b split).

Auth dependencies (get_current_user / get_api_user), the model-config and
rate-limit resolvers, reading/turn persistence, and the small shared
constants — moved verbatim out of main.py so routers can import them
without importing the app (which would be circular).

main.py re-exports get_current_user/get_api_user, so existing
`app.dependency_overrides[main.get_current_user]` keeps working.
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
from models import *  # noqa: F401,F403  (request models the helpers type against)


def _basis(value: Optional[str]) -> str:
    """Normalize the pravesha basis: 'solar' (Tajaka) or 'lunar' (tithi).
    Anything unrecognized falls back to solar, the historical behaviour."""
    return "lunar" if (value or "").strip().lower() == "lunar" else "solar"

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

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify token and return username"""
    username = decode_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return username


async def get_api_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Auth for the public API (`/api/v1/*`) + MCP (§2.3).

    Accepts a user-managed API token (opaque `jyd_…`, verified against
    `api_tokens`). For convenience it also accepts a normal access JWT, so the
    same routes work from a logged-in browser session — but the intended
    credential is the long-lived API token pasted into a script or MCP client."""
    token = credentials.credentials
    if token and token.startswith(api_tokens.TOKEN_PREFIX):
        username = await api_tokens.verify(token)
        if not username:
            raise HTTPException(status_code=401, detail="Invalid or revoked API token")
        return username
    # Fall back to a session access token.
    username = decode_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return username


async def get_admin_user(current_user: str = Depends(get_current_user)) -> str:
    """Admin-console gate (§44). Requires a valid session AND that the caller is on
    the ADMIN_USERNAMES allowlist (or has the reconciled `is_admin` flag). Returns
    404 — not 403 — for non-admins so the console's existence isn't confirmed to a
    logged-in non-admin probing the URL."""
    import admin as admin_service
    if admin_service.is_admin_user(current_user):
        return current_user
    from database import database
    if database is not None:
        doc = await database["users"].find_one(
            {"username": current_user}, {"is_admin": 1, "email": 1})
        if doc and admin_service.is_admin_user(current_user, doc):
            return current_user
    raise HTTPException(status_code=404, detail="Not found")


def require_content_access() -> None:
    """Second gate for content drill-down: ADMIN_CONTENT_ACCESS must be on. Off by
    default so private content is 'break glass' only, even for admins."""
    import admin as admin_service
    if not admin_service.content_access_enabled():
        raise HTTPException(
            status_code=403,
            detail="Content access is disabled. Set ADMIN_CONTENT_ACCESS=true and redeploy to enable.")


async def _resolve_birth_details(req: ToolRunRequest, user: str) -> Dict[str, Any]:
    """Resolve the birth data for a v1 tool call: a saved `profile_id` (scoped to
    the caller) takes precedence, else inline `birth_details`. Returns the dict the
    tool layer expects (dob/tob/place/latitude/longitude/timezone)."""
    if req.profile_id:
        from database import database
        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")
        try:
            oid = ObjectId(req.profile_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid profile_id")
        doc = await database["saved_profiles"].find_one(
            {"_id": oid, "user_id": user})
        if not doc:
            raise HTTPException(status_code=404, detail="Profile not found")
        return doc.get("birth_details") or {}
    if req.birth_details:
        return req.birth_details.model_dump()
    raise HTTPException(status_code=400,
                        detail="Provide either profile_id or birth_details")


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
    ("journal_entries", "user_id"),
    ("push_subscriptions", "user_id"),
    ("refresh_tokens", "username"),
    ("password_reset_tokens", "username"),
    ("api_tokens", "username"),
]


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

_LUNAR_RUNGS = ("tithi", "paksha", "month", "annual")

# ── Astro-journal + dasha diary (§5.9) ──────────────────────────────────────
def _dasha_snapshot(bd: Optional[BirthDetails], date: str,
                    ayanamsa: Optional[str]) -> Optional[dict]:
    """The Vimsottari maha/bhukti running on `date` for this chart, or None."""
    if not bd:
        return None
    try:
        c = AstrologyCompute.get_timeline_window_context(
            dob=bd.dob, tob=bd.tob, place=bd.place, lat=bd.latitude,
            lon=bd.longitude, tz=bd.timezone, target_date=date,
            ayanamsa=ayanamsa or DEFAULT_AYANAMSA)
        if c.get("status") != "success":
            return None
        return {"maha": (c.get("maha") or {}).get("lord"),
                "bhukti": (c.get("bhukti") or {}).get("lord")}
    except Exception:
        return None

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


# Export everything (including the _single_underscore helpers the moved route
# bodies call by bare name) to `from deps import *` in the route modules.
__all__ = [_n for _n in dir() if not _n.startswith('__')]
