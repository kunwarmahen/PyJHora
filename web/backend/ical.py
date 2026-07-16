"""iCal feed (§5.10) — a token-authed, read-only `.ics` a calendar app can
subscribe to. Serves the chart's upcoming dated events: bhukti (sub-period)
changes, Sade Sati / Saturn phase boundaries, the solar return (birthday),
slow-planet ingresses and eclipses on natal nakshatras.

Calendar apps can't send bearer tokens, so the feed is authorised by a
**stateless signed token** — HMAC(user_id:profile_id, SECRET_KEY) — embedded in
the URL. No token table to maintain; the trade-off is that revocation means
rotating SECRET_KEY (documented). Everything is computed on demand from the
existing engine methods; this module only signs, gathers and serialises.
"""
import base64
import hashlib
import hmac
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any, Tuple

from config import settings
from astrology import AstrologyCompute, DEFAULT_AYANAMSA


# --------------------------------------------------------------------------- #
# Stateless signed token
# --------------------------------------------------------------------------- #
def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload: str) -> str:
    sig = hmac.new(settings.SECRET_KEY.encode(), payload.encode(), hashlib.sha256).digest()
    return _b64(sig)


def make_token(user_id: str, profile_id: str) -> str:
    """Signed, URL-safe token encoding (user_id, profile_id)."""
    payload = _b64(f"{user_id}:{profile_id}".encode())
    return f"{payload}.{_sign(payload)}"


def verify_token(token: str) -> Optional[Tuple[str, str]]:
    """Return (user_id, profile_id) if the token is valid, else None."""
    try:
        payload, sig = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(payload)):
        return None
    try:
        user_id, profile_id = _unb64(payload).decode().split(":", 1)
    except Exception:
        return None
    return user_id, profile_id


# --------------------------------------------------------------------------- #
# Event gathering
# --------------------------------------------------------------------------- #
def _today() -> date:
    return datetime.now(timezone.utc).date()


def gather_events(birth_details: Dict[str, Any],
                  ayanamsa: str = DEFAULT_AYANAMSA,
                  solar_return_years: int = 5) -> List[Dict[str, str]]:
    """Build the list of upcoming {date, title, desc} events for this chart."""
    dob = birth_details["dob"]
    tob = birth_details["tob"]
    place = birth_details.get("place", "")
    lat = birth_details.get("latitude")
    lon = birth_details.get("longitude")
    tz = birth_details.get("timezone")
    today = _today()
    events: List[Dict[str, str]] = []

    def add(d: str, title: str, desc: str = ""):
        try:
            if datetime.strptime(d, "%Y-%m-%d").date() >= today:
                events.append({"date": d, "title": title, "desc": desc})
        except (ValueError, TypeError):
            pass

    # Solar return (birthday) for the next few years.
    try:
        _, mm, dd = map(int, dob.split("-"))
        for y in range(today.year, today.year + solar_return_years + 1):
            add(f"{y:04d}-{mm:02d}-{dd:02d}", "☀️ Solar return (birthday)",
                "Your annual solar return — a natural point to review the year ahead.")
    except Exception:
        pass

    # Timeline: bhukti changes, Saturn phases, ingresses, eclipses.
    try:
        tl = AstrologyCompute.get_life_timeline(
            dob=dob, tob=tob, place=place, lat=lat, lon=lon, tz=tz, ayanamsa=ayanamsa)
        if tl.get("status") == "success":
            for b in tl.get("bhukti_bands", []):
                add(b.get("start_date"), f"Bhukti begins: {b.get('maha_lord')}/{b.get('lord')}",
                    "A new Vimsottari sub-period (antardasha) starts.")
            for ph in tl.get("saturn_phases", []):
                label = ph.get("description") or ph.get("kind", "Saturn phase")
                add(ph.get("start_date"), f"♄ {label} begins", ph.get("sign_name", ""))
                add(ph.get("end_date"), f"♄ {label} ends", ph.get("sign_name", ""))
            for ing in tl.get("ingresses", []):
                add(ing.get("date"), f"{ing.get('planet')} enters {ing.get('to_sign')}",
                    "A slow-planet sign change (gochara ingress).")
            for ec in tl.get("eclipses", []):
                if ec.get("on_natal_nakshatra"):
                    add(ec.get("date"), f"🌑 {ec.get('kind', 'Eclipse')} on {ec.get('nakshatra')}",
                        "Eclipse falling on a natal nakshatra — a sensitive window.")
    except Exception:
        pass

    events.sort(key=lambda e: e["date"])
    return events


# --------------------------------------------------------------------------- #
# ICS serialisation
# --------------------------------------------------------------------------- #
def _esc(text: str) -> str:
    return (text or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545 line folding at 75 octets."""
    out = []
    while len(line.encode("utf-8")) > 75:
        # step back to a safe cut under 75 bytes
        cut = 74
        while len(line[:cut].encode("utf-8")) > 74:
            cut -= 1
        out.append(line[:cut])
        line = " " + line[cut:]
    out.append(line)
    return "\r\n".join(out)


def build_ics(calendar_name: str, events: List[Dict[str, str]]) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Jyotir AI//Astro Feed//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        _fold(f"X-WR-CALNAME:{_esc(calendar_name)}"),
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]
    for i, ev in enumerate(events):
        d = ev["date"].replace("-", "")
        uid = hashlib.sha1(f"{calendar_name}:{ev['date']}:{ev['title']}:{i}".encode()).hexdigest()
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}@jyotir.ai",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{d}",
            _fold(f"SUMMARY:{_esc(ev['title'])}"),
        ]
        if ev.get("desc"):
            lines.append(_fold(f"DESCRIPTION:{_esc(ev['desc'])}"))
        lines += ["TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
