"""Daily-digest delivery — shared by the manual endpoint and the scheduler.

`send_digest_for_user` computes a user's personalized daily digest for their
chosen (or default) birth profile and delivers it on the channels they enabled
in Settings → Notifications (email via SMTP, browser push via Web Push). Both
the "send me a test now" endpoint and the background scheduler call this, so the
delivery logic lives in exactly one place.
"""
from typing import Any, Dict, Optional

from astrology import AstrologyCompute, DEFAULT_AYANAMSA
from config import settings
from database import get_database
import email_service
import notifications


async def resolve_profile(user_id: str, prefs: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The birth profile the digest should be computed for: the one chosen in
    prefs, else the user's default, else their first saved profile, else None."""
    db = get_database()
    profile = None
    if prefs.get("profile_id"):
        try:
            from bson import ObjectId
            profile = await db["saved_profiles"].find_one(
                {"_id": ObjectId(prefs["profile_id"]), "user_id": user_id})
        except Exception:
            profile = None
    if not profile:
        profile = await db["saved_profiles"].find_one(
            {"user_id": user_id, "is_default": True}
        ) or await db["saved_profiles"].find_one({"user_id": user_id})
    return profile


async def send_digest_for_user(user_id: str, prefs: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build + deliver the daily digest for one user. Returns
    `{status, sent:{email,push}, highlights, date}` or `{status:"error", ...}`.
    Never raises — the scheduler must survive one bad user."""
    db = get_database()
    if prefs is None:
        prefs = await notifications.get_prefs(user_id)

    profile = await resolve_profile(user_id, prefs)
    if not profile:
        return {"status": "error", "reason": "no_profile"}

    bd = profile["birth_details"]
    digest = AstrologyCompute.get_daily_digest(
        dob=bd["dob"], tob=bd["tob"], place=bd.get("place", ""),
        lat=bd.get("latitude"), lon=bd.get("longitude"), tz=bd.get("timezone"),
        ayanamsa=DEFAULT_AYANAMSA)
    if digest.get("status") != "success":
        return {"status": "error", "reason": digest.get("error", "calc_failed")}

    name = bd.get("name") or profile.get("profile_name") or "there"
    highlights = digest.get("highlights", [])
    date = digest.get("date")
    subject = f"Your {settings.SITE_NAME} digest — {date}"
    text = (
        f"Hi {name},\n\nHere's your Vedic digest for {date}:\n\n"
        + "\n".join(f"• {h}" for h in highlights)
        + f"\n\nOpen {settings.SITE_NAME} for the full reading."
    )
    html = (
        f"<p>Hi {name}, here's your Vedic digest for <b>{date}</b>:</p><ul>"
        + "".join(f"<li>{h}</li>" for h in highlights)
        + "</ul>"
    )

    sent = {"email": False, "push": 0}
    if prefs.get("email"):
        user = await db["users"].find_one({"username": user_id})
        if user and user.get("email"):
            sent["email"] = await email_service.send_daily_digest(user["email"], subject, text, html)
    if prefs.get("push"):
        sent["push"] = await notifications.send_push(user_id, {
            "title": subject,
            "body": highlights[0] if highlights else "Your daily Vedic digest is ready.",
            "url": "/daily-digest",
        })

    return {"status": "ok", "sent": sent, "highlights": highlights, "date": date}
