"""Shareable read-only chart links.

Stored in the `shared_charts` Mongo collection. A share holds just enough to
recompute a chart on demand (birth details + ayanamsa) plus a random token used
in the public URL. The GET-by-token endpoint is unauthenticated and read-only.
"""
import secrets
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from database import get_database

COLLECTION = "shared_charts"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def create_share(user_id: str, profile_name: Optional[str],
                       birth_details: Dict[str, Any], ayanamsa: str) -> str:
    """Create a share and return its token. Reuses an existing token if this user
    already shared the exact same birth details + ayanamsa (idempotent-ish)."""
    db = get_database()
    existing = await db[COLLECTION].find_one({
        "user_id": user_id,
        "birth_details": birth_details,
        "ayanamsa": ayanamsa,
    })
    if existing:
        return existing["token"]

    token = secrets.token_urlsafe(9)  # ~12 chars, URL-safe
    await db[COLLECTION].insert_one({
        "token": token,
        "user_id": user_id,
        "profile_name": profile_name,
        "birth_details": birth_details,
        "ayanamsa": ayanamsa,
        "created_at": _now_iso(),
    })
    return token


async def get_share(token: str) -> Optional[Dict[str, Any]]:
    db = get_database()
    doc = await db[COLLECTION].find_one({"token": token})
    if not doc:
        return None
    doc["_id"] = str(doc.get("_id", ""))
    return doc
