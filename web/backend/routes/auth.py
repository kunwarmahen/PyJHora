"""Authentication: register/login/Google, token refresh, account management, API tokens.

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



@router.post("/api/auth/register", response_model=Token)
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

@router.post("/api/auth/login", response_model=Token)
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


@router.post("/api/auth/google", response_model=Token)
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


@router.post("/api/auth/refresh", response_model=Token)
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


@router.post("/api/auth/logout")
async def logout(req: LogoutRequest):
    """Revoke the presented refresh token so it can't mint new access tokens."""
    if req.refresh_token:
        await refresh_tokens.revoke(req.refresh_token)
    return {"status": "ok"}


# ============= API TOKEN MANAGEMENT (Settings → API access) =============
@router.get("/api/auth/api-tokens")
async def list_api_tokens(current_user: str = Depends(get_current_user)):
    """List the caller's live API tokens (metadata only — never the raw token)."""
    return {"tokens": await api_tokens.list_tokens(current_user)}


@router.post("/api/auth/api-tokens")
async def create_api_token(req: ApiTokenCreateRequest, current_user: str = Depends(get_current_user)):
    """Create a new API token. The raw token is returned **once** here and never
    again — the caller must copy it now."""
    token = await api_tokens.issue(current_user, label=req.label or "")
    if token is None:
        raise HTTPException(
            status_code=400,
            detail=f"Token limit reached ({api_tokens.MAX_TOKENS_PER_USER}). Revoke an old one first.",
        )
    return {"token": token, "label": (req.label or "API token").strip()[:80] or "API token"}


@router.delete("/api/auth/api-tokens/{token_id}")
async def revoke_api_token(token_id: str, current_user: str = Depends(get_current_user)):
    """Revoke one of the caller's API tokens by id."""
    if not await api_tokens.revoke(current_user, token_id):
        raise HTTPException(status_code=404, detail="Token not found")
    return {"status": "revoked"}


@router.post("/api/auth/change-password", response_model=Token)
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


@router.put("/api/auth/email")
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


@router.put("/api/auth/name")
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


@router.post("/api/auth/logout-all", response_model=Token)
async def logout_all(current_user: str = Depends(get_current_user)):
    """Revoke every refresh token for this user (signing out all other devices),
    then hand the current session a fresh pair so it stays signed in."""
    await refresh_tokens.revoke_all(current_user)
    return await _issue_token_pair(current_user, remember_me=True)


@router.delete("/api/auth/account")
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


@router.post("/api/auth/forgot-password")
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


@router.post("/api/auth/reset-password", response_model=Token)
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
