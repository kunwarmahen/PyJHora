"""Astro-journal + dasha diary (§5.9).

Per-profile dated life-event entries ("changed jobs", "moved city", free text),
stored in the `journal_entries` Mongo collection, scoped to the owning user_id.
Each entry can optionally be enriched with the Vimsottari maha/bhukti that was
running on its date (via AstrologyCompute.get_timeline_window_context), so the
user — and the AI — can see "what was running when this happened". The entries
also feed the event-based rectification mode and the `get_journal_entries` tool.
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from bson import ObjectId

from database import get_database

COLLECTION = "journal_entries"

# Free-text is always allowed; these are quick-pick categories for the UI/filters.
CATEGORIES = [
    "career", "relationship", "family", "health", "finance",
    "move", "education", "spiritual", "loss", "milestone", "other",
]


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc["_id"]),
        "profile_id": doc.get("profile_id"),
        "date": doc.get("date"),
        "title": doc.get("title", ""),
        "category": doc.get("category", "other"),
        "notes": doc.get("notes", ""),
        "dasha": doc.get("dasha"),  # {maha, bhukti} snapshot, if enriched
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }


async def list_entries(user_id: str, profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """All journal entries for a user (optionally one profile), newest event first."""
    db = get_database()
    query: Dict[str, Any] = {"user_id": user_id}
    if profile_id:
        query["profile_id"] = profile_id
    cursor = db[COLLECTION].find(query).sort("date", -1)
    return [_serialize(d) async for d in cursor]


async def create_entry(user_id: str, profile_id: Optional[str], date: str,
                       title: str, category: str, notes: str,
                       dasha: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    db = get_database()
    now = datetime.now(timezone.utc)
    doc = {
        "user_id": user_id,
        "profile_id": profile_id,
        "date": date,
        "title": title.strip(),
        "category": category if category in CATEGORIES else "other",
        "notes": notes.strip(),
        "dasha": dasha,
        "created_at": now,
        "updated_at": now,
    }
    res = await db[COLLECTION].insert_one(doc)
    doc["_id"] = res.inserted_id
    return _serialize(doc)


async def update_entry(user_id: str, entry_id: str,
                       fields: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    db = get_database()
    if not ObjectId.is_valid(entry_id):
        return None
    allowed = {k: v for k, v in fields.items()
               if k in ("date", "title", "category", "notes", "dasha")}
    if "category" in allowed and allowed["category"] not in CATEGORIES:
        allowed["category"] = "other"
    allowed["updated_at"] = datetime.now(timezone.utc)
    res = await db[COLLECTION].find_one_and_update(
        {"_id": ObjectId(entry_id), "user_id": user_id},
        {"$set": allowed},
        return_document=True,
    )
    return _serialize(res) if res else None


async def delete_entry(user_id: str, entry_id: str) -> bool:
    db = get_database()
    if not ObjectId.is_valid(entry_id):
        return False
    res = await db[COLLECTION].delete_one({"_id": ObjectId(entry_id), "user_id": user_id})
    return res.deleted_count > 0


async def entries_for_ai(user_id: str, profile_id: Optional[str],
                         limit: int = 40) -> List[Dict[str, Any]]:
    """Compact journal view for the AI tool: date, title, category, a trimmed note
    and the running dasha snapshot (if any). Newest first, capped."""
    entries = await list_entries(user_id, profile_id)
    out = []
    for e in entries[:limit]:
        row = {"date": e["date"], "title": e["title"], "category": e["category"]}
        if e.get("notes"):
            row["notes"] = e["notes"][:280]
        d = e.get("dasha") or {}
        if d.get("maha"):
            row["running"] = f"{d.get('maha')}" + (f"/{d.get('bhukti')}" if d.get("bhukti") else "")
        out.append(row)
    return out
