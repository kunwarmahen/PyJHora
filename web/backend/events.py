"""Your chart's forward calendar, and the alert that fires when it arrives (§70).

`scheduler.py` used to send digests and nothing else, so the app never told you
your Mahadasha changes next month, that Saturn leaves your 8th on a named date,
or that Mercury stations retrograde in your 10th. Every one of those was already
computed — §67 worked out a Saturn phase boundary in passing to answer a
question, and threw the date away.

Three parts, and only the middle one is new:

  • **Compute** — `AstrologyCompute.get_upcoming_events` (the engine layer), which
    joins the dasha bands, Saturn's phases, the eclipses, the ingresses and the
    retrograde stations onto one dated list, counted from *this* chart's Lagna,
    Moon and Arudha Lagna.
  • **Storage** — this module. Events are stored per (user, profile, key) so the
    calendar can be recomputed as often as we like without ever re-alerting on
    something already sent. `notified_at` is the only field a refresh must not
    clobber, and the upsert below is written around that one fact.
  • **Delivery** — the existing digest machinery: `email_service`, `send_push`,
    the notification preferences and the scheduler's per-user loop.

**Claiming is per event, not per day.** The digest cadences claim a *window*
(today's date, this paksha) because they send one thing per window. An alert is
tied to a specific crossing instead, so the claim is a conditional update on that
event's own `notified_at`. That is idempotent across ticks and across workers by
construction, and it means a user who adds a profile mid-week gets that profile's
alerts without waiting for a window to roll over.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from astrology import EVENT_KINDS, AstrologyCompute, DEFAULT_AYANAMSA
from bson import ObjectId

from config import settings
from database import get_database
import digest
import email_service
import notifications
import timezones

COLLECTION = "chart_events"

# How far ahead the stored calendar reaches, and how stale it may get before a
# refresh. Twelve months is far enough that a dasha change is rarely a surprise,
# and cheap: the whole scan is well under a second per profile.
HORIZON_MONTHS = 12
REFRESH_AFTER_DAYS = 7
# An alert for something that happened while the deployment was down is still
# worth sending; one for last month is just noise.
LATE_GRACE_DAYS = 3


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


async def refresh_profile(user_id: str, profile: Dict[str, Any],
                          today: Optional[str] = None,
                          months: int = HORIZON_MONTHS,
                          force: bool = False) -> int:
    """Recompute one profile's calendar and merge it into storage.

    Returns how many events are now stored for the window. Never raises: this is
    called from the scheduler, and one unparseable profile must not stop the
    others being alerted.

    The merge is an upsert keyed on the event's stable `key`, with `notified_at`
    deliberately absent from the `$set` — recomputing must never resurrect an
    alert that has already gone out. `$setOnInsert` carries it as null so a
    genuinely new event is immediately eligible.
    """
    db = get_database()
    profile_id = str(profile.get("_id") or "")
    bd = profile.get("birth_details") or {}
    if not bd.get("dob"):
        return 0
    today = today or _iso(_now())

    if not force:
        newest = await db[COLLECTION].find_one(
            {"user_id": user_id, "profile_id": profile_id},
            sort=[("computed_at", -1)], projection={"computed_at": 1})
        if newest and newest.get("computed_at"):
            try:
                age = _now() - datetime.fromisoformat(newest["computed_at"])
                if age < timedelta(days=REFRESH_AFTER_DAYS):
                    return await db[COLLECTION].count_documents(
                        {"user_id": user_id, "profile_id": profile_id})
            except (TypeError, ValueError):
                pass

    try:
        result = AstrologyCompute.get_upcoming_events(
            dob=bd["dob"], tob=bd.get("tob") or "12:00:00",
            place=bd.get("place") or "", lat=bd.get("latitude"),
            lon=bd.get("longitude"), tz=bd.get("timezone"),
            months=months, from_date=today,
            ayanamsa=profile.get("ayanamsa") or DEFAULT_AYANAMSA)
    except Exception as e:
        print(f"[events] compute failed for {user_id}/{profile_id}: {e}")
        return 0
    if result.get("status") != "success":
        print(f"[events] compute unsuccessful for {user_id}/{profile_id}: "
              f"{result.get('error')}")
        return 0

    now_iso = _now().isoformat()
    subject = profile.get("profile_name") or bd.get("name") or "this chart"
    stored = 0
    for ev in result.get("events") or []:
        try:
            await db[COLLECTION].update_one(
                {"user_id": user_id, "profile_id": profile_id, "key": ev["key"]},
                {"$set": {**ev, "user_id": user_id, "profile_id": profile_id,
                          "subject": subject, "computed_at": now_iso},
                 "$setOnInsert": {"notified_at": None}},
                upsert=True,
            )
            stored += 1
        except Exception as e:
            print(f"[events] store failed for {user_id}/{ev.get('key')}: {e}")
    # Anything still stored for this window that the recompute no longer produces
    # was a prediction that moved — an ingress date refined by a day, say. Drop
    # the un-alerted ones so the calendar matches the sky; keep the alerted ones,
    # because we told someone about them and the record should say so.
    try:
        await db[COLLECTION].delete_many({
            "user_id": user_id, "profile_id": profile_id,
            "notified_at": None,
            "date": {"$gte": result["from_date"], "$lte": result["to_date"]},
            "computed_at": {"$ne": now_iso},
        })
    except Exception as e:
        print(f"[events] prune failed for {user_id}/{profile_id}: {e}")
    return stored


async def refresh_user(user_id: str, prefs: Optional[Dict[str, Any]] = None,
                       today: Optional[str] = None, force: bool = False) -> int:
    """Refresh every profile this user's notifications cover."""
    if prefs is None:
        prefs = await notifications.get_prefs(user_id)
    total = 0
    for profile in await digest.resolve_profiles(user_id, prefs):
        total += await refresh_profile(user_id, profile, today=today, force=force)
    return total


async def upcoming(user_id: str, profile_id: Optional[str] = None,
                   kinds: Optional[List[str]] = None, limit: int = 100,
                   today: Optional[str] = None) -> List[Dict[str, Any]]:
    """The stored calendar from today forward, soonest first."""
    query: Dict[str, Any] = {"user_id": user_id,
                             "date": {"$gte": today or _iso(_now())}}
    if profile_id:
        query["profile_id"] = profile_id
    if kinds:
        query["kind"] = {"$in": [k for k in kinds if k in EVENT_KINDS]}
    rows: List[Dict[str, Any]] = []
    cursor = get_database()[COLLECTION].find(query).sort("date", 1).limit(
        max(1, min(limit, 500)))
    async for doc in cursor:
        doc["id"] = str(doc.pop("_id"))
        rows.append(doc)
    return rows


async def due(user_id: str, prefs: Dict[str, Any],
              today: Optional[str] = None) -> List[Dict[str, Any]]:
    """Events crossing within the lead window that nobody has been told about."""
    today = today or _iso(_now())
    lead = max(0, min(int(prefs.get("event_lead_days", 3) or 0), 60))
    horizon = _iso(datetime.strptime(today, "%Y-%m-%d") + timedelta(days=lead))
    floor = _iso(datetime.strptime(today, "%Y-%m-%d") - timedelta(days=LATE_GRACE_DAYS))
    kinds = [k for k in (prefs.get("event_kinds") or EVENT_KINDS) if k in EVENT_KINDS]
    rows: List[Dict[str, Any]] = []
    cursor = get_database()[COLLECTION].find({
        "user_id": user_id,
        "notified_at": None,
        "kind": {"$in": kinds},
        "date": {"$gte": floor, "$lte": horizon},
    }).sort("date", 1)
    async for doc in cursor:
        rows.append(doc)
    return rows


async def claim(event: Dict[str, Any]) -> bool:
    """Mark one event as told. The conditional update *is* the lock: two workers
    scanning the same tick cannot both win it, so nobody is mailed twice."""
    res = await get_database()[COLLECTION].find_one_and_update(
        {"_id": event["_id"], "notified_at": None},
        {"$set": {"notified_at": _now().isoformat()}},
    )
    return res is not None


def _lines(events: List[Dict[str, Any]], multi_profile: bool) -> List[str]:
    out = []
    for e in events:
        who = f"{e.get('subject')} — " if multi_profile else ""
        out.append(f"{e['date']} · {who}{e['title']}")
    return out


def _render(events: List[Dict[str, Any]], app_url: str,
            multi_profile: bool) -> tuple:
    """(text, html) for the alert email. Deliberately plain: an alert is a fact
    and a date, and the reading that explains it lives in the app."""
    text = ["Coming up in your chart:", ""]
    html = ['<p style="margin:0 0 16px">Coming up in your chart:</p>']
    for e in events:
        who = f"{e.get('subject')} — " if multi_profile else ""
        text.append(f"• {e['date']} — {who}{e['title']}")
        if e.get("detail"):
            text.append(f"    {e['detail']}")
        html.append(
            f'<div style="margin:0 0 14px;padding-left:12px;'
            f'border-left:3px solid #E27B5A">'
            f'<div style="font-weight:600">{who}{e["title"]}</div>'
            f'<div style="color:#6b6b6b;font-size:13px">{e["date"]}</div>'
            f'<div style="margin-top:4px">{e.get("detail", "")}</div></div>')
    link = f"{app_url}/timeline?tab=upcoming"
    text += ["", f"See the whole calendar: {link}"]
    html.append(f'<p style="margin:20px 0 0"><a href="{link}">'
                f"See the whole calendar</a></p>")
    return "\n".join(text), "\n".join(html)


async def send_alerts_for_user(user_id: str,
                               prefs: Optional[Dict[str, Any]] = None,
                               today: Optional[str] = None) -> Dict[str, Any]:
    """Deliver every due event for one user, in one message. Never raises.

    Events are claimed **before** the send, not after. A claimed event that then
    fails to mail is one alert someone misses; an unclaimed event that mails
    twice is an alert someone gets every fifteen minutes until the tick interval
    changes. The first failure is much the better one.
    """
    if prefs is None:
        prefs = await notifications.get_prefs(user_id)
    if not prefs.get("event_alerts"):
        return {"status": "skipped", "reason": "disabled"}

    pending = await due(user_id, prefs, today=today)
    if not pending:
        return {"status": "ok", "sent": 0}

    claimed = [e for e in pending if await claim(e)]
    if not claimed:
        return {"status": "ok", "sent": 0}   # another worker got there first

    app_url = settings.APP_BASE_URL.rstrip("/")
    multi = len({e.get("profile_id") for e in claimed}) > 1
    text, html = _render(claimed, app_url, multi)
    headline = claimed[0]["title"] if len(claimed) == 1 else \
        f"{len(claimed)} events coming up in your chart"
    subject = f"{settings.SITE_NAME}: {headline}"

    sent = {"email": False, "push": 0}
    if prefs.get("email"):
        user = await get_database()["users"].find_one({"username": user_id})
        address = (user or {}).get("email")
        if address:
            try:
                sent["email"] = await email_service.send_daily_digest(
                    address, subject, text, html)
            except Exception as e:
                print(f"[events] email failed for {user_id}: {e}")
    if prefs.get("push"):
        try:
            sent["push"] = await notifications.send_push(user_id, {
                "title": headline,
                "body": (claimed[0].get("detail") or "")[:140]
                        or "Open your chart's calendar.",
                "url": "/timeline?tab=upcoming",
            })
        except Exception as e:
            print(f"[events] push failed for {user_id}: {e}")

    return {"status": "ok", "sent": len(claimed), "channels": sent,
            "events": _lines(claimed, multi)}


async def delete_for_user(user_id: str) -> int:
    res = await get_database()[COLLECTION].delete_many({"user_id": user_id})
    return res.deleted_count


async def delete_for_profile(user_id: str, profile_id: str) -> int:
    res = await get_database()[COLLECTION].delete_many(
        {"user_id": user_id, "profile_id": str(profile_id)})
    return res.deleted_count
