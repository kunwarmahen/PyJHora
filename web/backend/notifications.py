"""Notifications — daily-digest preferences, Web Push subscriptions & sending.

Two stores, both scoped to the owning `user_id`:

* **Preferences** live inside the existing `user_settings` doc under a
  `notifications` key: whether the daily digest is enabled, which channels
  (email / push), the profile it should be computed for, and the preferred hour.
* **Push subscriptions** live in their own `push_subscriptions` collection
  (a browser can have several; keyed by user_id + endpoint).

Web Push uses VAPID (`VAPID_PUBLIC_KEY`/`VAPID_PRIVATE_KEY` in config). When
those are unset, `push_enabled()` is False and the send helpers no-op — the rest
of the app keeps working. Sending uses `pywebpush` (optional dep); if it's not
installed, pushes are skipped with a log line rather than crashing.

Run `python -m notifications genkeys` to print a fresh VAPID keypair to paste
into the environment.
"""
import json
from typing import Any, Dict, List, Optional

from config import settings
from database import get_database

SETTINGS_COLLECTION = "user_settings"
PUSH_COLLECTION = "push_subscriptions"

DEFAULT_PREFS: Dict[str, Any] = {
    "daily_digest": False,   # daily digest master switch
    "email": False,          # deliver by email (shared across cadences)
    "push": False,           # deliver by browser push (shared across cadences)
    "profile_id": None,      # legacy single-profile selection (kept for back-compat)
    "profile_ids": [],       # explicit set of saved profiles to include
    "all_profiles": True,    # default: include every saved profile (and any added later)
    "include_ai": True,      # embed the AI "how the day/fortnight/month looks" narrative
    "hour": 7,               # preferred local hour (0-23) for the DAILY send
    # Fortnightly reading (the Paksha Pravesha digest). The paksha boundary *is*
    # the schedule — it fires when a new Shukla/Krishna fortnight opens, so there
    # is no day picker, only an hour.
    "fortnightly": False,
    "fortnightly_hour": 7,
    # Monthly reading (Maasa Pravesha, or the lunar birth-tithi return).
    "monthly": False,
    "monthly_dom": 1,        # preferred day-of-month 1-28 (kept <=28 so it always exists)
    "monthly_hour": 7,
    # Which pravesha ladder the delivered readings are cast on:
    # "solar" (Tajaka: Maasa Pravesha) or "lunar" (tithi: birth-tithi return).
    # The fortnight rung is lunar-only regardless.
    "basis": "solar",
}


# --------------------------------------------------------------------------- #
# Preferences (stored on the user_settings doc)
# --------------------------------------------------------------------------- #
async def get_prefs(user_id: str) -> Dict[str, Any]:
    doc = await get_database()[SETTINGS_COLLECTION].find_one({"user_id": user_id})
    prefs = (doc or {}).get("notifications") or {}
    return {**DEFAULT_PREFS, **prefs}


async def set_prefs(user_id: str, prefs: Dict[str, Any]) -> Dict[str, Any]:
    # Whitelist + coerce so callers can't stuff arbitrary keys onto the doc.
    clean: Dict[str, Any] = {}
    if "daily_digest" in prefs:
        clean["daily_digest"] = bool(prefs["daily_digest"])
    if "email" in prefs:
        clean["email"] = bool(prefs["email"])
    if "push" in prefs:
        clean["push"] = bool(prefs["push"])
    if "profile_id" in prefs:
        clean["profile_id"] = prefs["profile_id"] or None
    if "profile_ids" in prefs:
        ids = prefs["profile_ids"] or []
        clean["profile_ids"] = [str(x) for x in ids if x] if isinstance(ids, list) else []
    if "all_profiles" in prefs:
        clean["all_profiles"] = bool(prefs["all_profiles"])
    if "include_ai" in prefs:
        clean["include_ai"] = bool(prefs["include_ai"])
    for hour_key in ("hour", "fortnightly_hour", "monthly_hour"):
        if hour_key in prefs:
            try:
                clean[hour_key] = max(0, min(23, int(prefs[hour_key])))
            except (TypeError, ValueError):
                pass
    if "fortnightly" in prefs:
        clean["fortnightly"] = bool(prefs["fortnightly"])
    if "monthly" in prefs:
        clean["monthly"] = bool(prefs["monthly"])
    if "monthly_dom" in prefs:
        try:
            clean["monthly_dom"] = max(1, min(28, int(prefs["monthly_dom"])))
        except (TypeError, ValueError):
            pass
    if "basis" in prefs:
        clean["basis"] = "lunar" if str(prefs["basis"]).lower() == "lunar" else "solar"
    await get_database()[SETTINGS_COLLECTION].update_one(
        {"user_id": user_id},
        {"$set": {f"notifications.{k}": v for k, v in clean.items()}},
        upsert=True,
    )
    return await get_prefs(user_id)


# --------------------------------------------------------------------------- #
# Push subscriptions
# --------------------------------------------------------------------------- #
def push_enabled() -> bool:
    """True when VAPID keys are configured (browser push can be used)."""
    return bool((settings.VAPID_PUBLIC_KEY or "").strip()
                and (settings.VAPID_PRIVATE_KEY or "").strip())


def vapid_public_key() -> str:
    return (settings.VAPID_PUBLIC_KEY or "").strip()


async def save_subscription(user_id: str, subscription: Dict[str, Any]) -> None:
    """Upsert a browser push subscription (idempotent per endpoint)."""
    endpoint = (subscription or {}).get("endpoint")
    if not endpoint:
        raise ValueError("subscription missing 'endpoint'")
    await get_database()[PUSH_COLLECTION].update_one(
        {"user_id": user_id, "endpoint": endpoint},
        {"$set": {"user_id": user_id, "endpoint": endpoint,
                  "subscription": subscription}},
        upsert=True,
    )


async def delete_subscription(user_id: str, endpoint: str) -> bool:
    res = await get_database()[PUSH_COLLECTION].delete_one(
        {"user_id": user_id, "endpoint": endpoint})
    return res.deleted_count > 0


async def list_subscriptions(user_id: str) -> List[Dict[str, Any]]:
    cur = get_database()[PUSH_COLLECTION].find({"user_id": user_id})
    return [d async for d in cur]


async def send_push(user_id: str, payload: Dict[str, Any]) -> int:
    """Send a push notification to every subscription of `user_id`. Returns the
    number of successful deliveries. Dead subscriptions (410/404) are pruned.
    No-ops (returns 0) when push isn't configured or pywebpush isn't installed."""
    if not push_enabled():
        return 0
    try:
        from pywebpush import webpush, WebPushException
    except Exception:
        print("[push] pywebpush not installed; skipping send")
        return 0

    subs = await list_subscriptions(user_id)
    if not subs:
        return 0

    vapid_claims = {"sub": settings.VAPID_SUBJECT}
    data = json.dumps(payload)
    sent = 0
    for row in subs:
        sub = row.get("subscription")
        try:
            webpush(
                subscription_info=sub,
                data=data,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims=dict(vapid_claims),
            )
            sent += 1
        except WebPushException as e:  # pragma: no cover - network dependent
            status = getattr(getattr(e, "response", None), "status_code", None)
            if status in (404, 410):
                # Subscription expired/unsubscribed — clean it up.
                await delete_subscription(user_id, row.get("endpoint"))
            else:
                print(f"[push] send failed ({status}): {e}")
        except Exception as e:  # pragma: no cover
            print(f"[push] unexpected send error: {e}")
    return sent


# --------------------------------------------------------------------------- #
# CLI: generate a VAPID keypair
# --------------------------------------------------------------------------- #
def _genkeys() -> None:
    try:
        from py_vapid import Vapid01
    except Exception:
        print("py_vapid not installed. Run: pip install pywebpush")
        return
    from cryptography.hazmat.primitives import serialization
    import base64

    v = Vapid01()
    v.generate_keys()

    def _b64url(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    # Public key: base64url of the raw uncompressed P-256 point (the value the
    # browser needs as applicationServerKey — also exposed to the frontend).
    pub_raw = v.public_key.public_bytes(
        serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint,
    )
    # Private key: base64url of the raw 32-byte scalar — a single line that
    # pywebpush/py_vapid load via Vapid.from_string, so it drops straight into .env.
    priv_raw = v.private_key.private_numbers().private_value.to_bytes(32, "big")

    print("# Paste these into web/backend/.env")
    print("VAPID_PUBLIC_KEY=" + _b64url(pub_raw))
    print("VAPID_PRIVATE_KEY=" + _b64url(priv_raw))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "genkeys":
        _genkeys()
    else:
        print("Usage: python -m notifications genkeys")
