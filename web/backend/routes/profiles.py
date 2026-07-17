"""Saved birth profiles: CRUD, default, import/export.

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
import digest_recipients
import scheduler
import uuid
from fastapi import APIRouter
from config import settings
from models import *  # noqa: F401,F403
from deps import *  # noqa: F401,F403
import deps as _deps

router = APIRouter()


async def _invite_recipient_if_external(owner_id: str, notify_email: Optional[str]):
    """When a profile's digest email is someone *other* than the account owner,
    make sure that person has been invited to opt in (double opt-in). The owner's
    own account email needs no consent — it's already verified, and the owner
    reads their own combined digest there. No-ops silently if email isn't
    configured or the address already has a standing decision."""
    email = digest_recipients.normalize(notify_email)
    if not email:
        return
    db = get_database()
    owner = await db["users"].find_one({"username": owner_id})
    owner_email = digest_recipients.normalize((owner or {}).get("email"))
    if email == owner_email:
        return  # the owner's own address — no invite needed
    record, created = await digest_recipients.ensure(owner_id, email)
    if created and record:
        base = settings.APP_BASE_URL.rstrip("/")
        token = record["token"]
        owner_name = (owner or {}).get("username") or "Someone"
        try:
            await email_service.send_digest_confirmation(
                email, owner_name,
                confirm_url=f"{base}/digest/confirm?token={token}",
                unsubscribe_url=f"{base}/digest/unsubscribe?token={token}",
            )
        except Exception as e:  # a mail hiccup must not fail the profile save
            print(f"[digest] confirmation email failed for {email}: {e}")


@router.post("/api/profiles/save")
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
            is_default=req.is_default,
            notify_email=(req.notify_email or "").strip() or None,
        )

        result = await profiles_collection.insert_one(profile.model_dump(by_alias=True, exclude={"id"}))

        await _invite_recipient_if_external(current_user, req.notify_email)

        return {
            "success": True,
            "profile_id": str(result.inserted_id),
            "message": f"Profile '{req.profile_name}' saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/api/profiles/{profile_id}")
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
        update = {
            "profile_name": req.profile_name,
            "birth_details": req.birth_details.model_dump(),
        }
        # Only touch notify_email when the client actually sent the field, so a
        # birth-details-only update (e.g. rectification) never erases it.
        if "notify_email" in req.model_fields_set:
            update["notify_email"] = (req.notify_email or "").strip() or None

        result = await profiles_collection.update_one(
            {"_id": ObjectId(profile_id), "user_id": current_user},
            {"$set": update},
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Profile not found")

        if "notify_email" in req.model_fields_set:
            await _invite_recipient_if_external(current_user, req.notify_email)

        return {
            "success": True,
            "message": f"Profile '{req.profile_name}' updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/profiles/{profile_id}/default")
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

@router.get("/api/profiles/list")
async def list_profiles(current_user: str = Depends(get_current_user)):
    """Get all saved profiles for the current user"""
    try:
        from database import database

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        profiles = await profiles_collection.find({"user_id": current_user}).sort("created_at", -1).to_list(100)

        # The owner's own address needs no consent; flag external recipients with
        # their opt-in state so the UI can show pending/confirmed/unsubscribed.
        owner = await database["users"].find_one({"username": current_user})
        owner_email = digest_recipients.normalize((owner or {}).get("email"))

        for profile in profiles:
            profile["_id"] = str(profile["_id"])
            addr = digest_recipients.normalize(profile.get("notify_email"))
            if not addr or addr == owner_email:
                profile["notify_status"] = "owner" if addr else None
            else:
                rec = await digest_recipients.get(current_user, addr)
                profile["notify_status"] = rec.get("status") if rec else "pending"

        return {
            "success": True,
            "profiles": profiles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/profiles/export")
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


@router.post("/api/profiles/import")
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


@router.delete("/api/profiles/{profile_id}")
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
