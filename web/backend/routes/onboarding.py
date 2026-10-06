"""The newcomer's first minute (§76): the "your chart in plain words" payload,
its anonymous twin for the landing page, and the funnel beacons.

The first look is structured data only — signs, a star, two dasha lords and their
dates — so it is instant, costs no model call, and translates on the frontend
(docs/I18N_DATA_LAYER_DESIGN.md, layer A). The AI stays behind login.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

import funnel
import ratelimit
from astrology import AstrologyCompute, DEFAULT_AYANAMSA, SUPPORTED_AYANAMSAS
from database import BirthDetails
from deps import get_current_user, viewer_tz

router = APIRouter()


class FirstLookRequest(BaseModel):
    birth_details: BirthDetails
    ayanamsa: Optional[str] = None
    # The viewer's UTC offset, which decides which dasha period is "now". Signed-in
    # readers have one on file; the anonymous preview sends the browser's.
    current_tz: Optional[float] = None


class FunnelEvent(BaseModel):
    event: str


_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")


def _validated(req: FirstLookRequest) -> dict:
    """The compute kwargs, or a 422 naming what's wrong. Strict on purpose: the
    public route takes input from anyone, and the engine is happier failing here
    than deep inside an ephemeris call."""
    bd = req.birth_details
    if not _DATE.match(bd.dob or "") or not _TIME.match(bd.tob or ""):
        raise HTTPException(status_code=422, detail="Birth date must be YYYY-MM-DD and time HH:MM.")
    year = int(bd.dob[:4])
    if not 1800 <= year <= 2200:
        raise HTTPException(status_code=422, detail="Birth year must be between 1800 and 2200.")
    if bd.latitude is None or bd.longitude is None or bd.timezone is None:
        raise HTTPException(status_code=422, detail="Choose the place of birth from the search.")
    if not (-90 <= bd.latitude <= 90 and -180 <= bd.longitude <= 180 and -14 <= bd.timezone <= 14):
        raise HTTPException(status_code=422, detail="Coordinates or timezone out of range.")
    tob = bd.tob if bd.tob.count(":") == 2 else f"{bd.tob}:00"
    ayanamsa = req.ayanamsa if req.ayanamsa in SUPPORTED_AYANAMSAS else DEFAULT_AYANAMSA
    return {"dob": bd.dob, "tob": tob, "place": bd.place or "", "lat": bd.latitude,
            "lon": bd.longitude, "tz": bd.timezone,
            "time_accuracy": bd.time_accuracy or "exact", "ayanamsa": ayanamsa}


def _compute(kwargs: dict, current_tz: Optional[float]) -> dict:
    result = AstrologyCompute.get_first_look(current_tz=current_tz, **kwargs)
    if result.get("status") != "success":
        raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
    return result


@router.post("/api/astrology/first-look")
async def first_look(req: FirstLookRequest, current_user: str = Depends(get_current_user)):
    """The signed-in "your chart in plain words" page (/start)."""
    kwargs = _validated(req)
    tz = await viewer_tz(current_user, explicit=req.current_tz,
                         fallback=req.birth_details.timezone)
    result = _compute(kwargs, tz)
    funnel.milestone(current_user, "payoff_seen")
    return result


@router.post("/api/public/first-look")
async def public_first_look(req: FirstLookRequest, request: Request):
    """The landing page's preview — the same payload with no account (§76.7).

    Nothing is stored: the details live in the visitor's browser until they sign
    up, when the welcome flow saves them as their first profile. Rate-limited per
    caller and globally (ratelimit.public_check)."""
    allowed, retry = ratelimit.public_check(ratelimit.public_caller(request))
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Too many previews — try again in {retry}s.",
                            headers={"Retry-After": str(retry)})
    kwargs = _validated(req)
    result = _compute(kwargs, req.current_tz)
    funnel.record("preview_seen")
    return result


@router.post("/api/public/funnel")
async def public_funnel_event(ev: FunnelEvent, request: Request):
    """Anonymous step beacons (landing page opened). Only the anonymous steps are
    accepted here; the per-account ones are recorded server-side where they
    happen, so a client can't claim them."""
    if ev.event not in funnel.ANON_EVENTS:
        raise HTTPException(status_code=422, detail="Unknown event.")
    allowed, _ = ratelimit.public_check(ratelimit.public_caller(request))
    if allowed:
        funnel.record(ev.event)
    return {"ok": True}


@router.post("/api/onboarding/welcome-done")
async def welcome_done(current_user: str = Depends(get_current_user)):
    """The welcome flow saved the account's first profile."""
    funnel.milestone(current_user, "welcome_done")
    return {"ok": True}
