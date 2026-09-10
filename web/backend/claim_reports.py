"""Where claim-check results go, and the report an admin triages them from (§68.1).

Two collections, for two different questions:

  • `claim_check_stats` — one small counter document per UTC day. Every checked
    reading updates it, including the clean ones, because a contradiction *count*
    without the number of readings behind it says nothing. This is what the
    console's rate is computed from, and it is cheap enough to write on every
    reading forever.

  • `claim_checks` — the work queue: one document per reading that still
    contradicted its chart after the retry. This is the part an admin acts on,
    so it carries a triage state (`open` → `fixed` / `false_positive` /
    `wont_fix`) and a verdict naming *what* was wrong: the prompt, the code, the
    model, or the checker itself. Pruned on a retention horizon like the audit
    log, so it cannot grow without bound.

Marking a row `false_positive` is not paperwork — the checker trades coverage for
precision on purpose, and the false positives are how its rules get tuned. The
verdict field is the whole point of the queue: a run of `prompt` verdicts on one
claim kind says fix the wording, a run of `code` verdicts says the payload is
lying to the model again, which is what §63/§64/§65 each turned out to be.
"""
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId

import runtime_config
from config import settings
from database import get_database

QUEUE_COLLECTION = "claim_checks"
STATS_COLLECTION = "claim_check_stats"

STATUSES = ("open", "fixed", "false_positive", "wont_fix")
# What the admin decided was actually at fault. `checker` closes the loop back
# onto this module: it means the reading was right and the rule was wrong.
VERDICTS = ("prompt", "code", "model", "checker")

_last_prune_at = 0.0
_PRUNE_EVERY_SECONDS = 3600


def _db():
    return get_database()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _retention_days() -> int:
    try:
        return max(1, int(settings.CLAIM_CHECK_RETENTION_DAYS))
    except (TypeError, ValueError):
        return 90


async def _prune() -> None:
    """Drop triaged rows past the horizon. Open ones are kept regardless — an
    unread work item ageing out is how a bug gets forgotten."""
    global _last_prune_at
    now = time.monotonic()
    if now - _last_prune_at < _PRUNE_EVERY_SECONDS:
        return
    _last_prune_at = now
    cutoff = (_now() - timedelta(days=_retention_days())).isoformat()
    try:
        await _db()[QUEUE_COLLECTION].delete_many(
            {"at": {"$lt": cutoff}, "status": {"$ne": "open"}})
    except Exception as e:
        print(f"[claim_reports] prune failed: {e}")


async def record(report: Dict[str, Any], *, username: Optional[str], source: str,
                 provider: Optional[str] = None, model: Optional[str] = None,
                 mode: str = "verify", profile_id: Optional[str] = None,
                 question: Optional[str] = None) -> Optional[str]:
    """File one reading's check. Returns the queue id when a row was written.

    Never raises: this runs on the path that is about to return a real answer to
    a real reader, and a logging failure must not cost them the answer.
    """
    try:
        day = _now().strftime("%Y-%m-%d")
        contradictions = report.get("contradictions") or []      # survived the retry
        initial = report.get("initial") or contradictions          # what was said first
        retried = bool(report.get("regenerated"))
        inc = {
            "readings": 1,
            "claims": int(report.get("claims") or 0),
            "checked": int(report.get("checked") or 0),
            # Counted on the FIRST answer: a reading the retry rescued is still a
            # reading the model got wrong, and that is the number that says
            # whether the prompt work is landing.
            "flagged_readings": 1 if initial else 0,
            # …and this is the number that says what the reader actually saw.
            "unresolved_readings": 1 if contradictions else 0,
            "contradictions": len(initial),
            "surviving": len(contradictions),
            "regenerated": 1 if retried else 0,
            "fixed_by_retry": int(report.get("fixed_by_retry") or 0),
        }
        for c in initial:
            key = f"by_kind.{c.get('kind', 'unknown')}"
            inc[key] = inc.get(key, 0) + 1
        if model and initial:
            inc[f"by_model.{_key(model)}"] = len(initial)
        await _db()[STATS_COLLECTION].update_one(
            {"_id": day}, {"$inc": inc, "$set": {"day": day}}, upsert=True)

        if not contradictions:
            return None
        doc = {
            "at": _now().isoformat(),
            "username": username,
            "source": source,
            "provider": provider,
            "model": model,
            "mode": mode,
            "profile_id": profile_id,
            "question": (question or "")[:400] or None,
            "claims": int(report.get("claims") or 0),
            "checked": int(report.get("checked") or 0),
            "regenerated": retried,
            "fixed_by_retry": int(report.get("fixed_by_retry") or 0),
            "contradictions": contradictions,
            "status": "open",
            "verdict": None,
            "note": None,
        }
        res = await _db()[QUEUE_COLLECTION].insert_one(doc)
        await _prune()
        return str(res.inserted_id)
    except Exception as e:
        print(f"[claim_reports] record failed: {e}")
        return None


def _key(value: str) -> str:
    """Mongo forbids dots in field names, and every model id has one."""
    return str(value).replace(".", "_").replace("$", "_")


async def summary(days: int = 30) -> Dict[str, Any]:
    """Headline numbers for the console: how many readings were checked, how many
    disagreed with their own chart, and which kinds of claim go wrong."""
    since = (_now() - timedelta(days=max(1, days))).strftime("%Y-%m-%d")
    totals = {"readings": 0, "claims": 0, "checked": 0, "flagged_readings": 0,
              "unresolved_readings": 0, "contradictions": 0, "surviving": 0,
              "regenerated": 0, "fixed_by_retry": 0}
    by_kind: Dict[str, int] = {}
    by_model: Dict[str, int] = {}
    daily: List[Dict[str, Any]] = []
    try:
        cursor = _db()[STATS_COLLECTION].find({"_id": {"$gte": since}}).sort("_id", 1)
        async for doc in cursor:
            for k in totals:
                totals[k] += int(doc.get(k) or 0)
            for k, v in (doc.get("by_kind") or {}).items():
                by_kind[k] = by_kind.get(k, 0) + int(v or 0)
            for k, v in (doc.get("by_model") or {}).items():
                by_model[k] = by_model.get(k, 0) + int(v or 0)
            daily.append({"day": doc.get("_id"),
                          "readings": int(doc.get("readings") or 0),
                          "flagged": int(doc.get("flagged_readings") or 0),
                          "unresolved": int(doc.get("unresolved_readings") or 0)})
    except Exception as e:
        print(f"[claim_reports] summary failed: {e}")
    open_count = 0
    try:
        open_count = await _db()[QUEUE_COLLECTION].count_documents({"status": "open"})
    except Exception:
        pass
    readings = totals["readings"]
    return {
        "days": days,
        "totals": totals,
        # Two rates, because they answer different questions. `flagged_rate` is
        # how often the model contradicted its own chart — the quality signal,
        # measured before the retry. `unresolved_rate` is how often that reached
        # a reader — the one that says whether the guard is doing its job. Both
        # are per *reading*: one wrong sentence makes one wrong reading.
        "flagged_rate": round(totals["flagged_readings"] / readings, 4) if readings else 0.0,
        "unresolved_rate": (round(totals["unresolved_readings"] / readings, 4)
                            if readings else 0.0),
        "by_kind": dict(sorted(by_kind.items(), key=lambda kv: -kv[1])),
        "by_model": dict(sorted(by_model.items(), key=lambda kv: -kv[1])),
        "daily": daily,
        "open": open_count,
        "statuses": list(STATUSES),
        "verdicts": list(VERDICTS),
    }


async def listing(limit: int = 100, status: str = "", kind: str = "",
                  source: str = "", redact: bool = False) -> List[Dict[str, Any]]:
    """The work queue, newest first.

    `redact` drops everything a contradiction quotes — the model's own sentence
    and the chart facts behind it are about one identifiable person's chart, so
    without ADMIN_CONTENT_ACCESS the console gets the shape of the problem (kind,
    count, model, when) and not its content. The rate and the triage still work.
    """
    query: Dict[str, Any] = {}
    if status:
        query["status"] = status
    if kind:
        query["contradictions.kind"] = kind
    if source:
        query["source"] = source
    rows: List[Dict[str, Any]] = []
    try:
        cursor = _db()[QUEUE_COLLECTION].find(query).sort("at", -1).limit(min(limit, 500))
        async for doc in cursor:
            doc["id"] = str(doc.pop("_id"))
            if redact:
                doc["question"] = None
                doc["contradictions"] = [{"kind": c.get("kind")}
                                         for c in doc.get("contradictions") or []]
            rows.append(doc)
    except Exception as e:
        print(f"[claim_reports] listing failed: {e}")
    return rows


async def triage(entry_id: str, *, status: Optional[str] = None,
                 verdict: Optional[str] = None, note: Optional[str] = None,
                 admin: Optional[str] = None) -> bool:
    """Move one row through the queue. Unknown values are ignored rather than
    stored, so a stale console cannot write a state nothing renders."""
    updates: Dict[str, Any] = {}
    if status in STATUSES:
        updates["status"] = status
    if verdict in VERDICTS:
        updates["verdict"] = verdict
    elif verdict == "":
        updates["verdict"] = None
    if note is not None:
        updates["note"] = str(note)[:1000] or None
    if not updates:
        return False
    updates["triaged_at"] = _now().isoformat()
    updates["triaged_by"] = admin
    try:
        res = await _db()[QUEUE_COLLECTION].update_one(
            {"_id": ObjectId(entry_id)}, {"$set": updates})
        return res.matched_count > 0
    except Exception as e:
        print(f"[claim_reports] triage failed: {e}")
        return False


async def mode() -> str:
    """The effective claim-check mode: the deployed `CLAIM_CHECK_MODE` unless an
    admin has overridden it in the console. Falls back to the env default if the
    settings document cannot be read, so a database hiccup does not silently turn
    the checker off."""
    try:
        cfg = await runtime_config.get()
        return cfg.get("claim_check_mode") or runtime_config.DEFAULT_CLAIM_CHECK_MODE
    except Exception:
        return runtime_config._default_claim_check_mode()
