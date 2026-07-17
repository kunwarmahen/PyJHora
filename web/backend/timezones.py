"""Where the user is **now** — the zone they live in, and the offset it implies.

Birth details carry a fixed float offset (`birth_details.timezone`, e.g. 5.5) and
that is correct for them: a birth chart is cast for one instant at one place, so
the offset in force at that instant is a constant of the chart, forever. It is
the wrong tool for *now*. Two reasons:

1. **DST.** A stored `-6.0` for Chicago is an hour wrong for half the year. India
   has no DST, so a codebase that grew up on IST never had to notice this.
2. **It's the wrong place.** Someone born in India and living in the US has a
   birth offset of +5.5 and a life that runs on America/Chicago.

So a current location stores an **IANA zone name**, never an offset, and the
offset is derived from it *for the moment it's needed*. `zoneinfo` carries the
DST rules; `TimezoneFinder` maps coordinates to the zone offline (no network).
"""
from datetime import datetime, timezone as _utc
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# TimezoneFinder loads a sizeable coordinate index; build it once and reuse.
_finder = None


def _tf():
    global _finder
    if _finder is None:
        from timezonefinder import TimezoneFinder

        _finder = TimezoneFinder()
    return _finder


def zone_at(latitude: float, longitude: float) -> Optional[str]:
    """The IANA zone name for a point ("America/Chicago"), or None.

    Offline. None is a real answer for a point at sea, not only an error."""
    try:
        return _tf().timezone_at(lat=float(latitude), lng=float(longitude))
    except Exception as e:
        print(f"[timezones] zone lookup failed for {latitude},{longitude}: {e}")
        return None


def is_valid_zone(zone: str) -> bool:
    """Whether `zone` names a zone this machine's tz database knows."""
    if not zone:
        return False
    try:
        ZoneInfo(zone)
        return True
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return False


def offset_hours(zone: str, when: Optional[datetime] = None) -> Optional[float]:
    """The UTC offset `zone` is on at `when` (default: now), in hours.

    Hours-as-float because that is what the engine takes. DST-aware by
    construction — ask for a summer instant and you get the summer offset, which
    is exactly the bug a stored offset can't avoid. Half-hour and 45-minute zones
    (Kolkata +5.5, Kathmandu +5.75) come out exact.
    """
    if not zone:
        return None
    try:
        tz = ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None
    moment = when or datetime.now(_utc.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=_utc.utc)
    off = moment.astimezone(tz).utcoffset()
    return None if off is None else off.total_seconds() / 3600.0


def representative_place(zone: str) -> Optional[str]:
    """A geocodable place name for `zone` ("America/Chicago" → "Chicago"), or None.

    IANA names their zones after a representative city, which is what makes this
    a real lookup rather than an invention. It is the city that *defines the
    zone*, though, not necessarily where the user is — someone in Milwaukee is
    America/Chicago. So the coordinates this leads to are metro-accurate, and the
    caller must treat them as a starting point the user can refine, never as a
    detected position.

    None for the zones that name no city: Etc/GMT±N (open water, and the
    POSIX-inverted naming would mislead anyway), UTC, and bare region names.
    """
    if not zone or "/" not in zone:
        return None
    region, _, rest = zone.partition("/")
    if region in ("Etc", "SystemV", "US"):  # no city / legacy aliases
        return None
    # "America/Argentina/Buenos_Aires" → the last segment is the city.
    city = rest.split("/")[-1].replace("_", " ").strip()
    return city or None


def local_now(zone: str) -> Optional[datetime]:
    """The current wall-clock time in `zone`, as an aware datetime, or None.

    This is what "is it 7am for them yet?" must be asked of. The scheduler's
    older `utcnow() + offset` trick produces the right answer only while the
    offset is right, which for a DST zone is half the year.
    """
    if not zone:
        return None
    try:
        return datetime.now(ZoneInfo(zone))
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return None
