"""Did this land? — outcomes recorded against saved AI readings (§68.7).

The app has always been able to *produce* readings (§17 unified history) and to
record what actually happened (§5.9 astro-journal), with **nothing joining the
two**. This module is that join: one verdict per saved reading, in the reader's
own words, optionally attached to a journal entry — and fed back into later
prompts so a reading can say "in the last Jupiter/Saturn period you reported …"
instead of guessing.

Two design decisions worth keeping straight:

**An outcome is not stored on the reading.** It lives in its own collection with
a *snapshot* of what it is judging (source, title, an excerpt of the text, the
date it was written). `AI_HISTORY_MAX` prunes readings continuously — an outcome
stored inside the conversation document would evaporate on the user's 101st
reading, taking the only evaluation signal this project has with it. Deleting a
reading *by hand* does take its outcome (see `delete_for_reading`): that is a
deliberate act, and a verdict outliving the thing it judged would be a surprise.
Automatic pruning is not, and does not.

**"Not yet" is not a verdict.** It is the honest state of most predictions most
of the time, so it is recordable — but it is excluded from the hit rate and from
what the model is shown, because a prediction whose window hasn't closed says
nothing about whether the reading was any good.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Iterable

from database import get_database

COLLECTION = "reading_outcomes"

# The verdict vocabulary. Ordered best → worst for display; `NOT_YET` sits apart
# because it is a "come back later", not a judgement.
VERDICTS = ("happened", "partly", "not_yet", "didnt")

# What the model — and the hit rate — are allowed to count. See the module note.
SETTLED = ("happened", "partly", "didnt")

# How the verdict reads in a prompt. Written as the *user's* report, not as a
# score, so the model treats it as testimony about a life rather than a grade.
_VERDICT_PHRASE = {
    "happened": "confirmed this happened",
    "partly": "says this partly happened",
    "didnt": "says this did NOT happen",
    "not_yet": "says it is too early to tell",
}

# Reading text kept alongside the verdict: enough to know what was judged when
# the reading itself has been pruned away, not the whole essay.
EXCERPT_CHARS = 600


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_verdict(verdict: Optional[str]) -> Optional[str]:
    v = (verdict or "").strip().lower()
    return v if v in VERDICTS else None


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "reading_id": doc.get("reading_id"),
        "profile_id": doc.get("profile_id"),
        "source": doc.get("source"),
        "label": doc.get("label"),
        "kind": doc.get("kind"),
        "title": doc.get("title"),
        "excerpt": doc.get("excerpt"),
        "reading_date": doc.get("reading_date"),
        "verdict": doc.get("verdict"),
        "note": doc.get("note", ""),
        "outcome_date": doc.get("outcome_date"),
        "journal_entry_id": doc.get("journal_entry_id"),
        "dasha": doc.get("dasha"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


def snapshot_of(item: Dict[str, Any]) -> Dict[str, Any]:
    """The identifying fields to copy off a serialized reading (a conversation or
    a delivered digest — both already share one shape) so the outcome survives it.

    `messages` is the conversation form; digests serialize to the same one-turn
    shape, so the last assistant message is the reading either way."""
    msgs = item.get("messages") or []
    text = next((m.get("content") for m in reversed(msgs)
                 if m.get("role") == "assistant" and m.get("content")), "")
    return {
        "source": item.get("source"),
        "label": item.get("label"),
        "kind": item.get("kind"),
        "title": item.get("title"),
        "excerpt": (text or "").strip()[:EXCERPT_CHARS],
        "reading_date": item.get("created_at"),
    }


async def record(user_id: str, reading_id: str, *, verdict: str,
                 note: str = "", outcome_date: Optional[str] = None,
                 profile_id: Optional[str] = None,
                 journal_entry_id: Optional[str] = None,
                 dasha: Optional[Dict[str, Any]] = None,
                 snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Upsert the one outcome for this reading. Re-judging replaces the verdict
    rather than piling up a second row — a reading has one answer at a time."""
    db = get_database()
    now = _now_iso()
    fields: Dict[str, Any] = {
        "user_id": user_id,
        "reading_id": reading_id,
        "profile_id": profile_id,
        "verdict": verdict,
        "note": (note or "").strip()[:2000],
        "outcome_date": outcome_date,
        "journal_entry_id": journal_entry_id,
        "dasha": dasha,
        "updated_at": now,
    }
    fields.update(snapshot or {})
    doc = await db[COLLECTION].find_one_and_update(
        {"user_id": user_id, "reading_id": reading_id},
        {"$set": fields, "$setOnInsert": {"created_at": now}},
        upsert=True, return_document=True,
    )
    return _serialize(doc or fields)


async def clear(user_id: str, reading_id: str) -> bool:
    db = get_database()
    res = await db[COLLECTION].delete_one(
        {"user_id": user_id, "reading_id": reading_id})
    return res.deleted_count > 0


async def delete_for_reading(user_id: str, reading_id: str) -> None:
    """Called when the reading itself is deleted by hand. Best-effort: losing the
    reading is the user's intent, and a failure here must not fail that."""
    try:
        await clear(user_id, reading_id)
    except Exception as e:  # pragma: no cover - defensive
        print(f"Failed to clear outcome for {reading_id}: {e}")


async def get(user_id: str, reading_id: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    doc = await db[COLLECTION].find_one(
        {"user_id": user_id, "reading_id": reading_id})
    return _serialize(doc) if doc else None


async def by_reading_id(user_id: str,
                        reading_ids: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    """Outcomes for a batch of readings, keyed by reading id — one query, so the
    history list can show its verdict chips without N round trips."""
    ids = [i for i in reading_ids if i]
    if not ids:
        return {}
    db = get_database()
    cursor = db[COLLECTION].find({"user_id": user_id, "reading_id": {"$in": ids}})
    return {d["reading_id"]: _serialize(d) async for d in cursor}


async def list_for_user(user_id: str, profile_id: Optional[str] = None,
                        verdict: Optional[str] = None) -> List[Dict[str, Any]]:
    """Every recorded outcome, newest judgement first — including those whose
    reading has since been pruned (which is the point of the snapshot)."""
    db = get_database()
    q: Dict[str, Any] = {"user_id": user_id}
    if profile_id:
        q["profile_id"] = profile_id
    if verdict:
        q["verdict"] = verdict
    cursor = db[COLLECTION].find(q).sort("updated_at", -1)
    return [_serialize(d) async for d in cursor]


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Counts by verdict, plus the hit rate over *settled* outcomes only.

    `partly` counts as half. A three-way verdict collapsed to a percentage is a
    blunt instrument either way, and calling a partial hit a full one is the
    flattering direction — half is the one that can't be accused of it."""
    counts = {v: 0 for v in VERDICTS}
    for r in rows:
        v = r.get("verdict")
        if v in counts:
            counts[v] += 1
    settled = sum(counts[v] for v in SETTLED)
    rate = None
    if settled:
        rate = round((counts["happened"] + 0.5 * counts["partly"]) / settled * 100)
    by_source: Dict[str, Dict[str, int]] = {}
    for r in rows:
        src = r.get("label") or r.get("source") or "AI"
        bucket = by_source.setdefault(src, {v: 0 for v in VERDICTS})
        if r.get("verdict") in bucket:
            bucket[r["verdict"]] += 1
    return {"total": len(rows), "settled": settled, "counts": counts,
            "hit_rate": rate, "by_source": by_source}


async def summary(user_id: str,
                  profile_id: Optional[str] = None) -> Dict[str, Any]:
    return summarize(await list_for_user(user_id, profile_id))


def _row_for_ai(r: Dict[str, Any]) -> Dict[str, Any]:
    # Most readings are titled by the tool that saved them, so prefixing the
    # label again yields "Annual (Varshaphal): Annual (Varshaphal) 1976-77".
    label = r.get("label") or r.get("source") or "AI"
    title = (r.get("title") or "").strip()
    name = title if title.lower().startswith(label.lower()) else f"{label}: {title}".strip(": ")
    row: Dict[str, Any] = {
        "reading": name,
        "read_on": (r.get("reading_date") or "")[:10] or None,
        "user_reported": _VERDICT_PHRASE.get(r.get("verdict"), r.get("verdict")),
    }
    if r.get("outcome_date"):
        row["happened_on"] = r["outcome_date"]
    if r.get("note"):
        row["in_their_words"] = r["note"][:400]
    d = r.get("dasha") or {}
    if d.get("maha"):
        row["running_then"] = d["maha"] + (f"/{d['bhukti']}" if d.get("bhukti") else "")
    return row


async def for_ai(user_id: str, profile_id: Optional[str] = None,
                 limit: int = 12) -> List[Dict[str, Any]]:
    """The settled outcomes, compact, newest first — what a later reading is told
    about how earlier ones actually turned out for this person.

    Unsettled ("not yet") rows are withheld: see the module note."""
    rows = [r for r in await list_for_user(user_id, profile_id)
            if r.get("verdict") in SETTLED]
    return [_row_for_ai(r) for r in rows[:limit]]
