"""'Learn the Chart' quiz persistence + scoring helpers.

Stored in the `quiz_sessions` Mongo collection, scoped to the owning user_id on
every query. A session is created at generation time holding the questions WITH
their hidden answer keys (correct_index / expected_points / rationale); the keys
are stripped before items are sent to the browser, and revealed only in the
graded results. Grading records the user's answers, per-item grades, the overall
score and a per-topic breakdown — which powers the History view and the Adaptive
difficulty selector.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from bson import ObjectId

from database import get_database

COLLECTION = "quiz_sessions"

# Public (client-safe) question fields — everything else is the answer key.
_PUBLIC_FIELDS = ("id", "topic", "difficulty", "format", "question", "options")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_items(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Strip answer-key fields so the browser can't reveal correct answers early."""
    return [{k: it[k] for k in _PUBLIC_FIELDS if k in it} for it in items]


async def create_session(user_id: str, profile_id: Optional[str],
                         birth_details: Dict[str, Any], topics: List[str],
                         level: str, adaptive: bool,
                         items: List[Dict[str, Any]],
                         provider: Optional[str] = None,
                         model: Optional[str] = None) -> str:
    """Persist a freshly generated quiz (with hidden keys); return its id."""
    db = get_database()
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "birth_details": birth_details,
        "topics": topics,
        "level": level,
        "adaptive": bool(adaptive),
        "items": items,            # full items incl. answer keys
        "provider": provider,
        "model": model,
        "status": "open",          # open -> graded
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    res = await db[COLLECTION].insert_one(doc)
    return str(res.inserted_id)


async def get_session(user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    try:
        oid = ObjectId(session_id)
    except Exception:
        return None
    return await db[COLLECTION].find_one({"_id": oid, "user_id": user_id})


async def save_grading(user_id: str, session_id: str, answers: Dict[str, str],
                       graded_items: List[Dict[str, Any]], score: float,
                       topic_scores: Dict[str, Any]) -> None:
    db = get_database()
    try:
        oid = ObjectId(session_id)
    except Exception:
        return
    await db[COLLECTION].update_one(
        {"_id": oid, "user_id": user_id},
        {"$set": {
            "status": "graded",
            "answers": answers,
            "graded_items": graded_items,
            "score": score,
            "topic_scores": topic_scores,
            "completed_at": _now_iso(),
            "updated_at": _now_iso(),
        }},
    )


async def list_sessions(user_id: str,
                        profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
    db = get_database()
    query: Dict[str, Any] = {"user_id": user_id}
    if profile_id:
        query["profile_id"] = profile_id
    cursor = db[COLLECTION].find(query).sort("created_at", -1).limit(100)
    out = []
    async for s in cursor:
        out.append({
            "id": str(s["_id"]),
            "profile_id": s.get("profile_id"),
            "topics": s.get("topics", []),
            "level": s.get("level"),
            "adaptive": s.get("adaptive", False),
            "status": s.get("status", "open"),
            "question_count": len(s.get("items", [])),
            "score": s.get("score"),
            "topic_scores": s.get("topic_scores", {}),
            "model": s.get("model"),
            "created_at": s.get("created_at"),
            "completed_at": s.get("completed_at"),
        })
    return out


async def delete_session(user_id: str, session_id: str) -> bool:
    db = get_database()
    try:
        oid = ObjectId(session_id)
    except Exception:
        return False
    res = await db[COLLECTION].delete_one({"_id": oid, "user_id": user_id})
    return res.deleted_count > 0


def compute_topic_scores(graded_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate per-topic {correct-fraction, count} from a session's graded items."""
    agg: Dict[str, Dict[str, float]] = {}
    for it in graded_items:
        topic = it.get("topic", "planets")
        a = agg.setdefault(topic, {"sum": 0.0, "count": 0})
        a["sum"] += float(it.get("score", 0))
        a["count"] += 1
    return {
        topic: {"avg": round(a["sum"] / a["count"], 3) if a["count"] else 0.0,
                "count": a["count"]}
        for topic, a in agg.items()
    }


async def get_stats(user_id: str,
                    profile_id: Optional[str] = None) -> Dict[str, Any]:
    """Roll up mastery across the user's graded sessions: per-topic average score +
    question count, overall average, sessions taken, and a current streak (count of
    most-recent consecutive sessions scoring >= 0.6). Powers Adaptive difficulty
    and the 'review your weak spots' view."""
    db = get_database()
    query: Dict[str, Any] = {"user_id": user_id, "status": "graded"}
    if profile_id:
        query["profile_id"] = profile_id
    cursor = db[COLLECTION].find(query).sort("completed_at", -1).limit(200)

    topic_agg: Dict[str, Dict[str, float]] = {}
    overall_sum = 0.0
    sessions = 0
    recent_scores: List[float] = []
    async for s in cursor:
        sessions += 1
        overall_sum += float(s.get("score") or 0)
        recent_scores.append(float(s.get("score") or 0))
        for topic, ts in (s.get("topic_scores") or {}).items():
            a = topic_agg.setdefault(topic, {"sum": 0.0, "count": 0})
            # weight each session's topic avg by its question count
            cnt = ts.get("count", 1) if isinstance(ts, dict) else 1
            avg = ts.get("avg", 0) if isinstance(ts, dict) else 0
            a["sum"] += float(avg) * cnt
            a["count"] += cnt

    topics = {
        topic: {"avg": round(a["sum"] / a["count"], 3) if a["count"] else 0.0,
                "count": int(a["count"])}
        for topic, a in topic_agg.items()
    }
    # Streak: consecutive recent sessions (newest first) scoring >= 0.6.
    streak = 0
    for sc in recent_scores:
        if sc >= 0.6:
            streak += 1
        else:
            break
    weak = sorted(topics.items(), key=lambda kv: kv[1]["avg"])
    return {
        "sessions": sessions,
        "overall_avg": round(overall_sum / sessions, 3) if sessions else None,
        "topics": topics,
        "streak": streak,
        "weak_topics": [t for t, _ in weak[:2]],
    }


def suggest_level(overall_avg: Optional[float]) -> str:
    """Map a rolling overall average onto a difficulty level (Adaptive mode)."""
    if overall_avg is None:
        return "beginner"
    if overall_avg >= 0.8:
        return "advanced"
    if overall_avg >= 0.55:
        return "intermediate"
    return "beginner"
