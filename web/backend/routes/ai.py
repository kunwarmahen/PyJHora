"""AI endpoints: ask/stream, conversations, traces, tool catalog, keys, preferences.

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
import digest_history
import journal
import outcomes as outcome_store
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


# ============= LLM Q&A ROUTES =============

@router.get("/api/llm/providers")
async def list_llm_providers(current_user: str = Depends(get_current_user)):
    """List available AI providers, their reachability, and installed/known models.

    Availability also reflects the calling user's own stored API keys."""
    try:
        user_keys = await user_settings.get_user_keys(current_user)
        providers = await llm_service.list_providers(user_keys)
        return {"providers": providers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ai/tools")
async def list_ai_tools():
    """The catalog of tools the AI astrologer can call while answering. Static,
    user-independent capability disclosure for the 'What the AI can do' page."""
    return {"tools": tool_registry.tool_catalog()}

@router.get("/api/ai/sources")
async def ai_sources_status():
    """Whether the classical-text corpus (§5.12 RAG) is indexed, so the UI can show
    if AI readings can cite the shastra. Best-effort; never raises."""
    import rag
    try:
        count = rag.build_index()
        return {"available": count > 0, "passages": count,
                "embed_model": rag.EMBED_MODEL}
    except Exception as e:
        return {"available": False, "passages": 0, "error": str(e)}


@router.get("/api/ai/personal-context")
async def ai_personal_context(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """What the AI can read about this person that is **not** in their chart: the
    astro-journal (§5.9) and the outcomes recorded on past readings (§68.7).

    Counts only. It exists so the capability is visible in the Ask UI rather than
    something the model silently knows: neither is a section of the chart, so
    neither has a row in the context picker, and a reader who has never opened
    /journal has no way to learn that either is being read. Same reasoning as the
    classical-citations line beside it. Best-effort — a failure hides the note."""
    try:
        entries = await journal.entries_for_ai(current_user, profile_id)
    except Exception:
        entries = []
    try:
        settled = await outcome_store.for_ai(current_user, profile_id)
    except Exception:
        settled = []
    return {"journal_entries": len(entries), "settled_outcomes": len(settled)}


@router.get("/api/ai/conversations")
async def list_ai_conversations(
    profile_id: Optional[str] = None,
    digests: bool = False,
    current_user: str = Depends(get_current_user)
):
    """List the current user's saved AI conversations (optionally for one profile).

    With `digests=true` the delivered digests are merged in — they live in their
    own collection under their own retention (see digest_history), so they are
    opt-in here rather than always present: every existing caller (the dashboard's
    recent-readings strip, the per-profile lists) keeps exactly the list it had,
    and only the History page asks for the full picture."""
    try:
        items = await convo.list_conversations(current_user, profile_id)
        if digests:
            items += await digest_history.list_for_user(current_user, profile_id)
            items.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
        # "Did this land?" verdicts (§68.7), attached in one query so the list can
        # show its chips without a round trip per row. Best-effort: a history that
        # loses its verdict chips is still a history.
        try:
            marks = await outcome_store.by_reading_id(current_user,
                                                      [i["id"] for i in items])
            for i in items:
                if i["id"] in marks:
                    i["outcome"] = marks[i["id"]]
        except Exception as e:  # pragma: no cover - defensive
            print(f"Failed to attach reading outcomes: {e}")
        return {"conversations": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/ai/conversations/{conversation_id}")
async def get_ai_conversation(
    conversation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Fetch a full conversation thread — or a delivered digest, which serialises
    to the same one-turn shape so the reading-restore path needs no special case."""
    if digest_history.is_digest_id(conversation_id):
        d = await digest_history.get(current_user, conversation_id)
        if not d:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return digest_history.serialize(d)
    c = await convo.get_conversation(current_user, conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo.serialize_conversation(c)


@router.get("/api/ai/conversations/{conversation_id}/traces/{trace_id}")
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


@router.delete("/api/ai/conversations/{conversation_id}")
async def delete_ai_conversation(
    conversation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a conversation (and any stored tool traces), or a delivered digest."""
    if digest_history.is_digest_id(conversation_id):
        if not await digest_history.delete(current_user, conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        await outcome_store.delete_for_reading(current_user, conversation_id)
        return {"success": True}
    ok = await convo.delete_conversation(current_user, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await tool_traces.delete_for_conversation(current_user, conversation_id)
    # Deleting a reading by hand takes its verdict too. Automatic retention
    # pruning does NOT — see outcomes.py for why the two differ.
    await outcome_store.delete_for_reading(current_user, conversation_id)
    return {"success": True}


@router.post("/api/ai/conversations/{conversation_id}/feedback")
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


# ============= DID THIS LAND? — OUTCOMES ON SAVED READINGS (§68.7) =============
# The join between a reading and what actually happened. Thumbs up/down (above)
# rates the *answer*; this rates the *prediction*, months later, against a life.


async def _reading_for_outcome(user_id: str, reading_id: str) -> Dict[str, Any]:
    """The serialized reading an outcome is being recorded against — conversation
    or delivered digest, both already in one shape. 404 if it isn't theirs."""
    if digest_history.is_digest_id(reading_id):
        item = digest_history.serialize(
            await digest_history.get(user_id, reading_id))
    else:
        item = convo.serialize_conversation(
            await convo.get_conversation(user_id, reading_id))
    if not item:
        raise HTTPException(status_code=404, detail="Reading not found")
    return item


@router.put("/api/ai/conversations/{conversation_id}/outcome")
async def set_reading_outcome(
    conversation_id: str,
    request: ReadingOutcomeRequest,
    current_user: str = Depends(get_current_user)
):
    """Record (or re-record) "did this land?" on one saved reading, optionally
    logging what happened to the astro-journal in the same call."""
    verdict = outcome_store.normalize_verdict(request.verdict)
    if not verdict:
        raise HTTPException(
            status_code=400,
            detail="verdict must be one of: " + ", ".join(outcome_store.VERDICTS))
    item = await _reading_for_outcome(current_user, conversation_id)
    profile_id = request.profile_id or item.get("profile_id")

    # The chart to date the outcome against: whatever the caller sent, else the
    # one the reading itself was made for (readings carry their birth details).
    bd = request.birth_details
    if bd is None and item.get("birth_details"):
        try:
            bd = BirthDetails(**item["birth_details"])
        except Exception:
            bd = None

    # "And log what happened" — one call, so the entry and the verdict cannot be
    # half-written against each other.
    journal_entry_id = None
    j = request.journal
    if j and j.title.strip():
        entry = await journal.create_entry(
            current_user, profile_id or j.profile_id, j.date, j.title,
            j.category, j.notes,
            _dasha_snapshot(j.birth_details or bd, j.date,
                            j.ayanamsa or request.ayanamsa))
        journal_entry_id = entry["id"]

    # Which period was running when it landed — the whole point of feeding this
    # back ("in the previous Jupiter/Saturn period the user reported …").
    on = request.outcome_date or (j.date if j else None) \
        or (item.get("created_at") or "")[:10]
    dasha = _dasha_snapshot(bd, on, request.ayanamsa) if on else None

    saved = await outcome_store.record(
        current_user, conversation_id, verdict=verdict, note=request.note,
        outcome_date=request.outcome_date or (j.date if j else None),
        profile_id=profile_id, journal_entry_id=journal_entry_id, dasha=dasha,
        snapshot=outcome_store.snapshot_of(item))
    return saved


@router.delete("/api/ai/conversations/{conversation_id}/outcome")
async def clear_reading_outcome(
    conversation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Un-judge a reading. A linked journal entry is left alone — it is a record
    of the user's life, not of their opinion of a reading."""
    await outcome_store.clear(current_user, conversation_id)
    return {"success": True}


@router.get("/api/ai/outcomes")
async def list_reading_outcomes(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """Every verdict this user has recorded, plus the track-record summary.

    Rows whose reading has since been pruned by `AI_HISTORY_MAX` are still here —
    each carries its own snapshot of what it judged."""
    rows = await outcome_store.list_for_user(current_user, profile_id)
    return {"outcomes": rows, "summary": outcome_store.summarize(rows),
            "verdicts": list(outcome_store.VERDICTS)}
