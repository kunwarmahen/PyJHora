"""Learn-the-chart quiz: generate, grade, history, stats.

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



@router.post("/api/astrology/quiz/generate")
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


@router.post("/api/astrology/quiz/grade")
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


@router.get("/api/astrology/quiz/history")
async def quiz_history(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """List the user's past quiz sessions (optionally for one profile)."""
    sessions = await quiz.list_sessions(current_user, profile_id)
    return {"sessions": sessions}


@router.get("/api/astrology/quiz/stats")
async def quiz_stats(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """Per-topic mastery, overall average, streak and weak areas for the user."""
    return await quiz.get_stats(current_user, profile_id)


@router.delete("/api/astrology/quiz/{session_id}")
async def quiz_delete(
    session_id: str,
    current_user: str = Depends(get_current_user),
):
    ok = await quiz.delete_session(current_user, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Quiz session not found.")
    return {"status": "deleted"}
