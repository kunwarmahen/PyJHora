"""Per-user settings — encrypted-at-rest API keys for the LLM providers.

Each user gets one document in the `user_settings` Mongo collection, keyed by
`user_id`, holding `api_keys: {provider_type: <fernet-encrypted-string>}`. Keys
are encrypted with Fernet (AES-128-CBC + HMAC); the symmetric key is derived from
`API_KEY_ENCRYPTION_KEY` (or `SECRET_KEY` as a fallback) so nothing readable is
stored in the database. Everything here is scoped to the owning `user_id`.
"""
import base64
import hashlib
import os
from typing import Dict, Optional

from cryptography.fernet import Fernet, InvalidToken

from config import settings
from database import get_database

COLLECTION = "user_settings"

# Providers that actually consume an API key (Ollama is local/keyless).
KEYED_PROVIDERS = ("gemini", "openai", "openai-compatible")


def _fernet() -> Fernet:
    """Build a Fernet from the configured secret (stable across restarts)."""
    secret = os.getenv("API_KEY_ENCRYPTION_KEY") or settings.SECRET_KEY
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def _decrypt(token: str) -> Optional[str]:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, Exception):
        # Wrong key / corrupted value — treat as "no key" rather than crashing.
        return None


def _mask(plaintext: str) -> str:
    """A non-secret hint so the UI can confirm a key is stored."""
    if not plaintext:
        return ""
    tail = plaintext[-4:] if len(plaintext) > 4 else ""
    return f"••••••{tail}"


async def set_api_key(user_id: str, provider: str, api_key: str) -> None:
    db = get_database()
    await db[COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": {f"api_keys.{provider}": _encrypt(api_key.strip())}},
        upsert=True,
    )


async def delete_api_key(user_id: str, provider: str) -> bool:
    db = get_database()
    res = await db[COLLECTION].update_one(
        {"user_id": user_id},
        {"$unset": {f"api_keys.{provider}": ""}},
    )
    return res.modified_count > 0


async def get_api_key(user_id: str, provider: str) -> Optional[str]:
    """Decrypted key for one provider, or None if not stored."""
    db = get_database()
    doc = await db[COLLECTION].find_one({"user_id": user_id})
    if not doc:
        return None
    token = (doc.get("api_keys") or {}).get(provider)
    return _decrypt(token) if token else None


async def get_user_keys(user_id: str) -> Dict[str, str]:
    """All decrypted keys for the user, {provider: key}."""
    db = get_database()
    doc = await db[COLLECTION].find_one({"user_id": user_id})
    out: Dict[str, str] = {}
    for provider, token in (doc.get("api_keys") if doc else {} or {}).items():
        plain = _decrypt(token)
        if plain:
            out[provider] = plain
    return out


async def get_key_status(user_id: str) -> Dict[str, Dict[str, object]]:
    """Per-provider {has_key, masked} — never returns the raw key."""
    keys = await get_user_keys(user_id)
    return {
        p: {"has_key": p in keys, "masked": _mask(keys.get(p, ""))}
        for p in KEYED_PROVIDERS
    }
