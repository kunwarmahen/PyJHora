from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import StreamingResponse
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
import json
from pydantic import BaseModel

from config import settings
from database import connect_to_mongo, close_mongo_connection
from auth import create_access_token, decode_token, get_password_hash, verify_password, Token
from database import User, BirthDetails, ChartData
from astrology import AstrologyCompute, SUPPORTED_AYANAMSAS, DEFAULT_AYANAMSA, SUPPORTED_VARGAS, SUPPORTED_DASHAS
from chart_context import build_chart_context
from qwen_predictor import QwenPredictor
from llm_service import llm_service, LLMProvider
import tools as tool_registry
import conversations as convo
import tool_traces
import user_settings
import ratelimit
import shares
import quiz
import uuid

# Request models
class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class AskQuestionRequest(BaseModel):
    birth_details: BirthDetails
    question: str
    llm_provider: str = "qwen"  # legacy: qwen, gemini, or chatgpt
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None   # ollama | openai-compatible | gemini | openai
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Context controls (optional)
    ayanamsa: Optional[str] = None
    sections: Optional[dict] = None  # toggle dasha_tree/yogas/doshas/transits
    vargas: Optional[list] = None    # divisional-chart factors, e.g. [1, 9, 10]
    # Answer mode: "pass_all" (default) pre-sends the full context; "tools" lets the
    # model fetch chart data on demand. Set per conversation (first turn wins).
    mode: Optional[str] = None
    # Conversation (save + multi-turn)
    conversation_id: Optional[str] = None
    profile_id: Optional[str] = None
    # Where the thread originated, so the Ask page can label/filter it:
    # "astrologer" (default) or "transit" (the Transits-page chat). Only honoured
    # when the conversation is first created.
    source: Optional[str] = None
    # When true, replace the last assistant answer instead of appending a new turn
    regenerate: bool = False

class PredictionRequest(BaseModel):
    birth_details: BirthDetails
    prediction_type: str = "general"  # general, health, career, relationships
    llm_provider: str = "qwen"  # legacy fallback
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None   # ollama | openai-compatible | gemini | openai
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    # Context controls (optional)
    ayanamsa: Optional[str] = None
    sections: Optional[dict] = None  # toggle dasha_tree/yogas/doshas/transits
    vargas: Optional[list] = None    # divisional-chart factors, e.g. [1, 9, 10]


class ShareRequest(BaseModel):
    birth_details: BirthDetails
    ayanamsa: Optional[str] = None
    profile_name: Optional[str] = None


class CompatibilityRequest(BaseModel):
    """Ashtakoot compatibility scoring. Flat birth fields for both partners —
    sent as a JSON body by the frontend (these were previously declared as bare
    function args, which FastAPI treated as query params)."""
    male_dob: str
    male_tob: str
    male_place: str
    female_dob: str
    female_tob: str
    female_place: str
    male_latitude: Optional[float] = None
    male_longitude: Optional[float] = None
    male_timezone: Optional[float] = None
    female_latitude: Optional[float] = None
    female_longitude: Optional[float] = None
    female_timezone: Optional[float] = None
    use_qwen: bool = False

class CompatibilityAnalysisRequest(BaseModel):
    male_details: BirthDetails
    female_details: BirthDetails
    llm_provider: str = "qwen"  # legacy fallback
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    ayanamsa: Optional[str] = None

class CompareAnalysisRequest(BaseModel):
    person1_details: BirthDetails
    person2_details: BirthDetails
    person1_name: Optional[str] = None
    person2_name: Optional[str] = None
    llm_provider: str = "qwen"  # legacy fallback
    # New model-selection fields (optional; fall back to llm_provider when absent)
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    ayanamsa: Optional[str] = None

class SarvatobhadraAnalysisRequest(BaseModel):
    birth_details: BirthDetails
    person_name: Optional[str] = None
    name_nakshatra: Optional[int] = None  # 1..27 naama-nakshatra (optional anchor)
    current_date: Optional[str] = None
    current_time: Optional[str] = None
    current_tz: Optional[float] = None
    llm_provider: str = "qwen"  # legacy fallback
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    ayanamsa: Optional[str] = None

# Lifecycle events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title="PyJHora Web API",
    description="Vedic Astrology Web Application",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# ============= AUTH ROUTES =============

@app.post("/api/auth/register", response_model=Token)
async def register(req: RegisterRequest):
    """Register a new user"""
    try:
        from database import database
        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        users_collection = database["users"]
        
        # Check if user exists
        existing = await users_collection.find_one({"username": req.username})
        if existing:
            raise HTTPException(status_code=400, detail="Username already registered")
        
        # Create new user
        hashed_password = get_password_hash(req.password)
        user_doc = {
            "username": req.username,
            "email": req.email,
            "hashed_password": hashed_password
        }
        result = await users_collection.insert_one(user_doc)
        
        # Create token
        access_token = create_access_token(
            data={"sub": req.username},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Register error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/auth/login", response_model=Token)
async def login(req: LoginRequest):
    """Login user and return token"""
    try:
        from database import database
        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")
        
        users_collection = database["users"]
        user = await users_collection.find_one({"username": req.username})
        
        if not user or not verify_password(req.password, user["hashed_password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        access_token = create_access_token(
            data={"sub": req.username},
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        return {"access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify token and return username"""
    username = decode_token(credentials.credentials)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    return username

# ============= ASTROLOGY ROUTES =============

@app.post("/api/astrology/birth-chart")
async def calculate_birth_chart(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Calculate birth chart for given details"""
    try:
        from database import database

        chart = AstrologyCompute.get_birth_chart(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa
        )

        charts_collection = database["charts"]
        chart_doc = {
            "user_id": current_user,
            "birth_details": birth_details.model_dump(),
            "chart_type": "rasi",
            "planets_positions": chart.get("planets", {}),
            "houses": chart.get("houses", {})
        }
        result = await charts_collection.insert_one(chart_doc)
        chart["_id"] = str(result.inserted_id)
        
        return chart
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/astrology/ayanamsas")
async def list_ayanamsas():
    """Supported ayanamsa options for chart calculation."""
    return {
        "default": DEFAULT_AYANAMSA,
        "options": [{"value": k, "label": v} for k, v in SUPPORTED_AYANAMSAS.items()],
    }

@app.get("/api/astrology/vargas")
async def list_vargas():
    """Supported divisional (varga) charts for the varga picker."""
    return {
        "options": [
            {"value": factor, "code": code, "name": name, "significance": significance}
            for factor, (code, name, significance) in SUPPORTED_VARGAS.items()
        ]
    }

@app.post("/api/astrology/divisional-chart")
async def calculate_divisional_chart(
    birth_details: BirthDetails,
    varga: int = 9,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Calculate a single divisional (varga) chart, e.g. varga=10 for Dasamsa."""
    try:
        chart = AstrologyCompute.calculate_divisional_chart(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            varga_factor=varga,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa,
        )
        if chart.get("status") != "success":
            raise HTTPException(status_code=400, detail=chart.get("error", "Calculation failed"))
        return chart
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/astrology/panchanga")
async def get_panchanga(
    date: Optional[str] = None,
    place: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    timezone: Optional[float] = None,
    current_user: str = Depends(get_current_user),
):
    """Daily almanac (panchanga) for a place and optional date (defaults to
    today at that place). Used by the 'Today' panel."""
    try:
        panchanga = AstrologyCompute.get_panchanga(
            date=date,
            place=place,
            lat=latitude,
            lon=longitude,
            tz=timezone,
        )
        if panchanga.get("status") != "success":
            raise HTTPException(status_code=400, detail=panchanga.get("error", "Calculation failed"))
        return panchanga
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/astrology/birth-chart/{chart_id}")
async def get_birth_chart(chart_id: str, current_user: str = Depends(get_current_user)):
    """Retrieve stored birth chart"""
    try:
        from database import database
        from bson import ObjectId
        
        charts_collection = database["charts"]
        chart = await charts_collection.find_one({
            "_id": ObjectId(chart_id),
            "user_id": current_user
        })
        
        if not chart:
            raise HTTPException(status_code=404, detail="Chart not found")
        
        chart["_id"] = str(chart["_id"])
        return chart
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/horoscope")
async def get_horoscope(
    birth_details: BirthDetails,
    use_qwen: bool = False,
    current_user: str = Depends(get_current_user)
):
    """Get horoscope predictions"""
    try:
        chart_data = AstrologyCompute.get_horoscope_predictions(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone
        )

        if use_qwen and settings.USE_QWEN:
            qwen_prediction = await QwenPredictor.generate_horoscope_prediction(chart_data)
            chart_data["ai_prediction"] = qwen_prediction
        elif use_qwen:
            # Basic predictions when AI is not available
            chart_data["ai_prediction"] = generate_basic_predictions(chart_data)

        return chart_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def generate_basic_predictions(chart_data):
    """Generate basic astrological predictions from chart data"""
    lagna = chart_data.get("lagna", {})
    moon = chart_data.get("moon_sign", {})
    sun = chart_data.get("sun_sign", {})

    predictions = []

    # Lagna predictions
    lagna_sign = lagna.get("sign_name", "")
    if lagna_sign:
        predictions.append(f"**Ascendant in {lagna_sign}:** Your rising sign suggests your outer personality and how others perceive you.")

    # Moon sign predictions
    moon_sign = moon.get("sign_name", "")
    moon_nak = moon.get("nakshatra", "")
    if moon_sign:
        predictions.append(f"**Moon in {moon_sign}** ({moon_nak} nakshatra): This placement influences your emotions, mind, and instincts.")

    # Sun sign predictions
    sun_sign = sun.get("sign_name", "")
    if sun_sign:
        predictions.append(f"**Sun in {sun_sign}:** Represents your core self, ego, and vitality.")

    # Planetary strength analysis
    planets = chart_data.get("planetary_positions", {})

    # Check for exalted planets
    exalted = {
        "Sun": "Aries", "Moon": "Taurus", "Mars": "Capricorn",
        "Mercury": "Virgo", "Jupiter": "Cancer", "Venus": "Pisces", "Saturn": "Libra"
    }

    for planet, data in planets.items():
        if planet in exalted and data.get("sign_name") == exalted[planet]:
            predictions.append(f"✨ **{planet} is exalted in {data['sign_name']}** - This is a very strong placement bringing positive results.")

    # General life areas
    predictions.append("\n**General Outlook:**")
    predictions.append(f"- Your birth chart shows a combination of {lagna_sign} Ascendant with Moon in {moon_sign}")
    predictions.append(f"- The nakshatra {moon_nak} adds specific qualities to your personality")
    predictions.append("- Consult an astrologer for detailed life predictions and remedies")

    return "\n\n".join(predictions)

@app.post("/api/astrology/doshas")
async def get_doshas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Get doshas"""
    try:
        doshas = AstrologyCompute.get_doshas(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa
        )
        return doshas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/yogas")
async def get_yogas(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Get yogas"""
    try:
        yogas = AstrologyCompute.get_yogas(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            ayanamsa=ayanamsa
        )
        return yogas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/dhasa")
async def get_dhasa(
    birth_details: BirthDetails,
    dhasa_type: str = "vimsottari",
    current_user: str = Depends(get_current_user)
):
    """Get Dasha periods"""
    try:
        dhasa = AstrologyCompute.get_dashas(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            dhasa_type=dhasa_type
        )
        return dhasa
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/dhasa/children")
async def get_dhasa_children(
    birth_details: BirthDetails,
    lords: str = "",
    current_user: str = Depends(get_current_user)
):
    """Lazily fetch the immediate child periods (Antara/Sookshma) of a Vimsottari
    node. `lords` is a comma-separated lord-path, e.g. `Venus,Saturn`."""
    try:
        lords_path = [p.strip() for p in lords.split(",") if p.strip()]
        result = AstrologyCompute.get_dasha_children(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            lords_path=lords_path,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/astrology/dasha-systems")
async def list_dasha_systems(current_user: str = Depends(get_current_user)):
    """List the supported non-Vimsottari dasha systems."""
    return {
        "systems": [
            {"key": k, "name": v["name"], "lord_type": v["lord_type"],
             "description": v["description"]}
            for k, v in SUPPORTED_DASHAS.items()
        ]
    }

@app.post("/api/astrology/dasha-periods")
async def get_dasha_periods(
    birth_details: BirthDetails,
    dhasa_type: str,
    current_user: str = Depends(get_current_user)
):
    """Maha-level periods for one of the non-Vimsottari dasha systems
    (ashtottari/yogini/narayana/kalachakra)."""
    try:
        result = AstrologyCompute.get_dasha_periods(
            dhasa_type=dhasa_type,
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/ashtakavarga")
async def get_ashtakavarga(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Bhinna + Sarva Ashtakavarga bindu tables."""
    try:
        result = AstrologyCompute.get_ashtakavarga(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/aspects")
async def get_aspects(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Graha drishti (planetary aspects) + rasi drishti + sphuta aspect strength."""
    try:
        result = AstrologyCompute.get_aspects(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/chart-details")
async def get_chart_details(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Advanced chart factors: Arudha padas, Chara karakas, Special lagnas, Upagrahas."""
    try:
        result = AstrologyCompute.get_chart_details(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/shadbala")
async def get_shadbala(
    birth_details: BirthDetails,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Shadbala (six-fold planetary strength) for Sun..Saturn."""
    try:
        result = AstrologyCompute.get_shadbala(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude,
            tz=birth_details.timezone, ayanamsa=ayanamsa,
        )
        if result.get("status") != "success":
            raise HTTPException(status_code=400, detail=result.get("error", "Calculation failed"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/share")
async def create_share_link(
    request: ShareRequest,
    current_user: str = Depends(get_current_user)
):
    """Create a read-only share token for a chart (birth details + ayanamsa)."""
    try:
        token = await shares.create_share(
            user_id=current_user,
            profile_name=request.profile_name,
            birth_details=request.birth_details.model_dump(),
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
        return {"token": token, "path": f"/share/{token}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/astrology/share/{token}")
async def get_shared_chart(token: str):
    """Public, read-only: recompute and return the shared chart. No auth."""
    try:
        share = await shares.get_share(token)
        if not share:
            raise HTTPException(status_code=404, detail="Shared chart not found")
        bd = share.get("birth_details", {})
        ayanamsa = share.get("ayanamsa", DEFAULT_AYANAMSA)
        chart = AstrologyCompute.calculate_birth_chart(
            dob=bd.get("dob"), tob=bd.get("tob"), place=bd.get("place"),
            lat=bd.get("latitude"), lon=bd.get("longitude"),
            tz=bd.get("timezone"), ayanamsa=ayanamsa,
        )
        if chart.get("error"):
            raise HTTPException(status_code=400, detail=chart.get("error"))
        return {
            "profile_name": share.get("profile_name"),
            "ayanamsa": ayanamsa,
            "birth_details": {
                "name": bd.get("name"),
                "dob": bd.get("dob"),
                "tob": bd.get("tob"),
                "place": bd.get("place"),
            },
            "chart": chart,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/astrology/transit")
async def get_transits(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user)
):
    """Get current transits (Gochara) over the natal chart"""
    try:
        transits = AstrologyCompute.get_transits(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            current_date=current_date,
            current_time=current_time,
            current_tz=current_tz,
            ayanamsa=ayanamsa
        )
        if transits.get("status") != "success":
            raise HTTPException(status_code=400, detail=transits.get("error", "Calculation failed"))
        return transits
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/compatibility")
async def get_compatibility(
    request: CompatibilityRequest,
    current_user: str = Depends(get_current_user)
):
    """Calculate compatibility"""
    try:
        compatibility = AstrologyCompute.get_compatibility(
            male_dob=request.male_dob,
            male_tob=request.male_tob,
            male_place=request.male_place,
            male_lat=request.male_latitude,
            male_lon=request.male_longitude,
            female_dob=request.female_dob,
            female_tob=request.female_tob,
            female_place=request.female_place,
            female_lat=request.female_latitude,
            female_lon=request.female_longitude,
            male_tz=request.male_timezone,
            female_tz=request.female_timezone,
            tz=request.male_timezone or request.female_timezone or 5.5
        )

        if request.use_qwen and settings.USE_QWEN:
            chart1 = AstrologyCompute.get_horoscope_predictions(
                request.male_dob, request.male_tob, request.male_place,
                lat=request.male_latitude, lon=request.male_longitude, tz=request.male_timezone
            )
            chart2 = AstrologyCompute.get_horoscope_predictions(
                request.female_dob, request.female_tob, request.female_place,
                lat=request.female_latitude, lon=request.female_longitude, tz=request.female_timezone
            )
            qwen_analysis = await QwenPredictor.generate_compatibility_prediction(
                chart1, chart2, compatibility.get("total_score", 0)
            )
            compatibility["ai_analysis"] = qwen_analysis
        
        return compatibility
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= USER ROUTES =============

@app.get("/api/user/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    """Get user profile"""
    try:
        from database import database
        
        users_collection = database["users"]
        user = await users_collection.find_one({"username": current_user})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user["_id"] = str(user.get("_id", ""))
        del user["hashed_password"]
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/user/charts")
async def get_user_charts(current_user: str = Depends(get_current_user)):
    """Get user charts"""
    try:
        from database import database
        
        charts_collection = database["charts"]
        charts = await charts_collection.find({"user_id": current_user}).to_list(length=100)
        
        for chart in charts:
            chart["_id"] = str(chart.get("_id", ""))
        
        return {"charts": charts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= LLM Q&A ROUTES =============

@app.get("/api/llm/providers")
async def list_llm_providers(current_user: str = Depends(get_current_user)):
    """List available AI providers, their reachability, and installed/known models.

    Availability also reflects the calling user's own stored API keys."""
    try:
        user_keys = await user_settings.get_user_keys(current_user)
        providers = await llm_service.list_providers(user_keys)
        return {"providers": providers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/tools")
async def list_ai_tools():
    """The catalog of tools the AI astrologer can call while answering. Static,
    user-independent capability disclosure for the 'What the AI can do' page."""
    return {"tools": tool_registry.tool_catalog()}


async def _resolve_cfg(current_user: str, request: "AskQuestionRequest"):
    """Resolve the model config, falling back to the user's stored API key when
    the request didn't carry an explicit key and no env key is configured."""
    cfg = llm_service.resolve_config(
        provider_type=request.provider_type,
        model=request.model,
        base_url=request.base_url,
        api_key=request.api_key,
        legacy_provider=request.llm_provider,
    )
    if not cfg.api_key and cfg.provider_type.value in user_settings.KEYED_PROVIDERS:
        stored = await user_settings.get_api_key(current_user, cfg.provider_type.value)
        if stored:
            cfg.api_key = stored
    return cfg


def _enforce_rate_limit(current_user: str):
    allowed, retry_after, reason = ratelimit.check(current_user)
    if not allowed:
        raise HTTPException(
            status_code=429, detail=reason,
            headers={"Retry-After": str(retry_after)},
        )

@app.post("/api/astrology/ask")
async def ask_question(
    request: AskQuestionRequest,
    current_user: str = Depends(get_current_user)
):
    """Ask a question about the birth chart using AI"""
    _enforce_rate_limit(current_user)
    try:
        # Build the rich, structured chart context (D1 + running dasha chain +
        # yogas + doshas + transits), token-budgeted and section-toggleable.
        chart_data = build_chart_context(
            birth_details=request.birth_details.model_dump(),
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            sections=request.sections,
            vargas=request.vargas,
        )

        # Resolve the model config (request key → user's stored key → env key)
        cfg = await _resolve_cfg(current_user, request)

        # Multi-turn: load prior turns from the conversation (if any)
        conv = await convo.get_conversation(current_user, request.conversation_id) \
            if request.conversation_id else None
        history = convo.history_for_model(conv)
        mode = _resolve_mode(request, conv)

        # Get AI response
        started = datetime.now(timezone.utc)
        usage: dict = {}
        tool_trace: list = []
        if mode == "tools":
            # Drain the tool loop, collecting the final answer + the call trace.
            seed_block = llm_service._render_context_block(chart_data, tool_mode=True)
            bd = request.birth_details.model_dump()
            parts = []
            async for ev in llm_service.run_tool_loop(
                    seed_block, request.question, history, cfg, bd,
                    request.ayanamsa or DEFAULT_AYANAMSA,
                    tool_names=tool_registry.tool_names_for_sections(request.sections),
                    usage=usage):
                et = ev.get("type")
                if et == "token":
                    parts.append(ev["text"])
                elif et == "tool_call":
                    tool_trace.append({"name": ev["name"], "args": ev.get("args", {})})
                elif et == "tool_result":
                    for tr in reversed(tool_trace):
                        if tr["name"] == ev["name"] and "ok" not in tr:
                            tr["ok"] = ev["ok"]
                            tr["result"] = ev.get("result")
                            break
            answer = "".join(parts)
        else:
            answer = await llm_service.ask_question(
                chart_data=chart_data,
                question=request.question,
                config=cfg,
                history=history,
                usage=usage,
            )
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)

        # Persist the turn (create the conversation on first message)
        conv_id = await _save_turn(current_user, request, cfg, chart_data, answer,
                                   elapsed_ms=elapsed_ms, usage=usage or None,
                                   mode=mode, tool_trace=tool_trace or None)

        return {
            "question": request.question,
            "answer": answer,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
            "mode": mode,
            "elapsed_ms": elapsed_ms,
            "usage": usage or None,
            "conversation_id": conv_id,
            "sections": chart_data.get("_sections", {}),
            "vargas": chart_data.get("_vargas", []),
            "tool_trace": tool_trace,
            "context": chart_data,  # full structured context (for the "what was sent" view)
            "chart_summary": {
                "lagna": chart_data.get("lagna", {}),
                "moon_sign": chart_data.get("moon_sign", {}),
                "sun_sign": chart_data.get("sun_sign", {})
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _resolve_mode(request: "AskQuestionRequest", conv: Optional[dict]) -> str:
    """The effective answer mode. A conversation's mode is fixed on its first turn,
    so follow-ups inherit it; a brand-new conversation takes the request's mode."""
    if conv and conv.get("mode"):
        return conv["mode"]
    m = request.mode or "pass_all"
    return m if m in ("pass_all", "tools") else "pass_all"


async def _save_turn(user_id: str, request: "AskQuestionRequest", cfg, chart_data: dict,
                     answer: str, elapsed_ms: Optional[int] = None,
                     usage: Optional[dict] = None, mode: str = "pass_all",
                     tool_trace: Optional[list] = None) -> str:
    """Persist a user question + assistant answer, creating the conversation if new.

    When `request.regenerate` is set and a conversation exists, the previous
    assistant answer is replaced in place (no duplicate question/answer turn)."""
    conv_id = request.conversation_id
    if not conv_id:
        conv_id = await convo.create_conversation(
            user_id, request.profile_id, request.question,
            request.birth_details.model_dump(), mode=mode,
            source=request.source or "astrologer",
        )
    now = datetime.now(timezone.utc).isoformat()
    ai_msg = {
        "role": "assistant", "content": answer, "ts": now,
        "provider": cfg.provider_type.value, "model": cfg.model,
        "vargas": chart_data.get("_vargas", []),
        "sections": chart_data.get("_sections", {}),
        "elapsed_ms": elapsed_ms,
    }
    if usage:
        ai_msg["usage"] = usage
    if tool_trace:
        # Keep only the light trace (name/args/ok) on the message so listing/loading
        # stays fast; stash the full per-call results in the side collection keyed by
        # an opaque trace_id, fetched lazily when the user opens "Behind the scenes".
        trace_id = uuid.uuid4().hex
        ai_msg["trace_id"] = trace_id
        ai_msg["tool_trace"] = [
            {"name": e.get("name"), "args": e.get("args", {}), "ok": e.get("ok")}
            for e in tool_trace
        ]
        full = [e for e in tool_trace if e.get("result") is not None]
        if full:
            await tool_traces.save_trace(user_id, conv_id, trace_id, full)
    if request.regenerate and request.conversation_id:
        await convo.replace_last_assistant(user_id, conv_id, ai_msg)
    else:
        user_msg = {"role": "user", "content": request.question, "ts": now}
        await convo.append_messages(user_id, conv_id, [user_msg, ai_msg])
    return conv_id


@app.post("/api/astrology/ask/stream")
async def ask_question_stream(
    request: AskQuestionRequest,
    current_user: str = Depends(get_current_user)
):
    """Stream an answer token-by-token (SSE), with multi-turn context, and persist
    the completed turn. Frontend reads this with a fetch + ReadableStream."""
    _enforce_rate_limit(current_user)
    # Build context + resolve model up front so failures surface as HTTP errors.
    chart_data = build_chart_context(
        birth_details=request.birth_details.model_dump(),
        ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        sections=request.sections,
        vargas=request.vargas,
    )
    cfg = await _resolve_cfg(current_user, request)
    conv = await convo.get_conversation(current_user, request.conversation_id) \
        if request.conversation_id else None
    history = convo.history_for_model(conv)
    mode = _resolve_mode(request, conv)

    async def event_gen():
        # Tell the client which conversation + model + mode up front.
        meta = {
            "type": "meta",
            "conversation_id": request.conversation_id,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
            "mode": mode,
            "sections": chart_data.get("_sections", {}),
            "vargas": chart_data.get("_vargas", []),
            "context": chart_data,  # exact structured context (seed, in tool mode)
        }
        yield f"data: {json.dumps(meta)}\n\n"

        parts = []
        tool_trace: list = []
        usage: dict = {}
        started = datetime.now(timezone.utc)
        try:
            if mode == "tools":
                # Seed = the toggled-on sections; the model fetches the rest via tools.
                seed_block = llm_service._render_context_block(chart_data, tool_mode=True)
                bd = request.birth_details.model_dump()
                async for ev in llm_service.run_tool_loop(
                        seed_block, request.question, history, cfg, bd,
                        request.ayanamsa or DEFAULT_AYANAMSA,
                        tool_names=tool_registry.tool_names_for_sections(request.sections),
                        usage=usage):
                    et = ev.get("type")
                    if et == "token":
                        parts.append(ev["text"])
                    elif et == "tool_call":
                        tool_trace.append({"name": ev["name"], "args": ev.get("args", {})})
                    elif et == "tool_result":
                        for tr in reversed(tool_trace):
                            if tr["name"] == ev["name"] and "ok" not in tr:
                                tr["ok"] = ev["ok"]
                                tr["result"] = ev.get("result")
                                break
                    yield f"data: {json.dumps(ev)}\n\n"
            else:
                async for chunk in llm_service.stream_answer(chart_data, request.question,
                                                             history, cfg, usage=usage):
                    parts.append(chunk)
                    yield f"data: {json.dumps({'type': 'token', 'text': chunk})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return

        answer = "".join(parts)
        elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        usage = usage or None
        try:
            conv_id = await _save_turn(current_user, request, cfg, chart_data, answer,
                                       elapsed_ms=elapsed_ms, usage=usage, mode=mode,
                                       tool_trace=tool_trace or None)
        except Exception as e:
            conv_id = request.conversation_id
            print(f"Failed to persist conversation: {e}")
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': conv_id, 'elapsed_ms': elapsed_ms, 'usage': usage})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no",
                 "Connection": "keep-alive"},
    )


@app.get("/api/ai/conversations")
async def list_ai_conversations(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """List the current user's saved AI conversations (optionally for one profile)."""
    try:
        return {"conversations": await convo.list_conversations(current_user, profile_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ai/conversations/{conversation_id}")
async def get_ai_conversation(
    conversation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Fetch a full conversation thread."""
    c = await convo.get_conversation(current_user, conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return convo.serialize_conversation(c)


@app.get("/api/ai/conversations/{conversation_id}/traces/{trace_id}")
async def get_ai_trace(
    conversation_id: str,
    trace_id: str,
    current_user: str = Depends(get_current_user)
):
    """Fetch the full per-call tool results for one smart-lookup answer (the
    "Behind the scenes" data), loaded lazily so threads stay light."""
    doc = await tool_traces.get_trace(current_user, trace_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Trace not found")
    return doc


@app.delete("/api/ai/conversations/{conversation_id}")
async def delete_ai_conversation(
    conversation_id: str,
    current_user: str = Depends(get_current_user)
):
    """Delete a conversation (and any stored tool traces)."""
    ok = await convo.delete_conversation(current_user, conversation_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    await tool_traces.delete_for_conversation(current_user, conversation_id)
    return {"success": True}


class FeedbackRequest(BaseModel):
    message_index: int
    rating: Optional[str] = None  # "up" | "down" | null to clear


@app.post("/api/ai/conversations/{conversation_id}/feedback")
async def submit_feedback(
    conversation_id: str,
    request: FeedbackRequest,
    current_user: str = Depends(get_current_user)
):
    """Store thumbs up/down on a specific assistant message in a conversation."""
    if request.rating not in (None, "", "up", "down"):
        raise HTTPException(status_code=400, detail="rating must be 'up', 'down', or null")
    ok = await convo.set_feedback(current_user, conversation_id,
                                  request.message_index, request.rating)
    if not ok:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"success": True}


# ============= PER-USER API KEYS =============

class ApiKeyRequest(BaseModel):
    api_key: str


@app.get("/api/user/api-keys")
async def get_api_keys(current_user: str = Depends(get_current_user)):
    """Per-provider key status for the current user (masked — never the raw key)."""
    return {"keys": await user_settings.get_key_status(current_user)}


@app.put("/api/user/api-keys/{provider}")
async def put_api_key(
    provider: str,
    request: ApiKeyRequest,
    current_user: str = Depends(get_current_user)
):
    """Store (encrypted) the user's API key for one provider."""
    if provider not in user_settings.KEYED_PROVIDERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown provider '{provider}'. Expected one of {user_settings.KEYED_PROVIDERS}.",
        )
    if not request.api_key.strip():
        raise HTTPException(status_code=400, detail="api_key cannot be empty")
    await user_settings.set_api_key(current_user, provider, request.api_key)
    return {"success": True, "provider": provider}


@app.delete("/api/user/api-keys/{provider}")
async def remove_api_key(
    provider: str,
    current_user: str = Depends(get_current_user)
):
    """Remove the user's stored API key for one provider."""
    if provider not in user_settings.KEYED_PROVIDERS:
        raise HTTPException(status_code=400, detail=f"Unknown provider '{provider}'.")
    await user_settings.delete_api_key(current_user, provider)
    return {"success": True, "provider": provider}


@app.post("/api/astrology/predict")
async def generate_prediction(
    request: PredictionRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate AI-powered predictions"""
    _enforce_rate_limit(current_user)
    try:
        # Build the rich, structured chart context (same path as /ask):
        # D1 + running dasha chain + yogas + doshas + transits + selected vargas.
        chart_data = build_chart_context(
            birth_details=request.birth_details.model_dump(),
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
            sections=request.sections,
            vargas=request.vargas,
        )

        # Resolve the model config (request key → user's stored key → env key)
        cfg = await _resolve_cfg(current_user, request)

        # Generate prediction
        prediction = await llm_service.generate_prediction(
            chart_data=chart_data,
            prediction_type=request.prediction_type,
            config=cfg,
        )

        return {
            "prediction_type": request.prediction_type,
            "prediction": prediction,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
            "chart_data": chart_data,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/compatibility-analysis")
async def analyze_compatibility(
    request: CompatibilityAnalysisRequest,
    current_user: str = Depends(get_current_user)
):
    """Get detailed compatibility analysis with AI"""
    _enforce_rate_limit(current_user)
    try:
        male_details = request.male_details
        female_details = request.female_details

        # Calculate compatibility score
        compatibility = AstrologyCompute.get_compatibility(
            male_dob=male_details.dob,
            male_tob=male_details.tob,
            male_place=male_details.place,
            female_dob=female_details.dob,
            female_tob=female_details.tob,
            female_place=female_details.place,
            male_lat=male_details.latitude,
            male_lon=male_details.longitude,
            female_lat=female_details.latitude,
            female_lon=female_details.longitude,
            male_tz=male_details.timezone,
            female_tz=female_details.timezone,
            tz=male_details.timezone or female_details.timezone
        )

        # Build the natal summary for both partners (lagna/moon/sun/planets).
        ayanamsa = request.ayanamsa or DEFAULT_AYANAMSA
        male_chart = AstrologyCompute.get_horoscope_predictions(
            dob=male_details.dob, tob=male_details.tob, place=male_details.place,
            lat=male_details.latitude, lon=male_details.longitude,
            tz=male_details.timezone, ayanamsa=ayanamsa,
        )
        female_chart = AstrologyCompute.get_horoscope_predictions(
            dob=female_details.dob, tob=female_details.tob, place=female_details.place,
            lat=female_details.latitude, lon=female_details.longitude,
            tz=female_details.timezone, ayanamsa=ayanamsa,
        )

        # Resolve the model config (request key → user's stored key → env key)
        cfg = await _resolve_cfg(current_user, request)

        # Get AI analysis
        ai_analysis = await llm_service.analyze_compatibility(
            male_chart=male_chart,
            female_chart=female_chart,
            koota_score=compatibility.get("total_score", 0),
            config=cfg,
        )

        return {
            "compatibility_score": compatibility,
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/compare-analysis")
async def analyze_comparison(
    request: CompareAnalysisRequest,
    current_user: str = Depends(get_current_user)
):
    """Neutral AI comparison of two charts (not marriage compatibility)."""
    _enforce_rate_limit(current_user)
    try:
        p1 = request.person1_details
        p2 = request.person2_details
        ayanamsa = request.ayanamsa or DEFAULT_AYANAMSA

        chart_a = AstrologyCompute.get_horoscope_predictions(
            dob=p1.dob, tob=p1.tob, place=p1.place,
            lat=p1.latitude, lon=p1.longitude, tz=p1.timezone, ayanamsa=ayanamsa,
        )
        chart_b = AstrologyCompute.get_horoscope_predictions(
            dob=p2.dob, tob=p2.tob, place=p2.place,
            lat=p2.latitude, lon=p2.longitude, tz=p2.timezone, ayanamsa=ayanamsa,
        )

        cfg = await _resolve_cfg(current_user, request)

        ai_analysis = await llm_service.compare_charts(
            chart_a=chart_a,
            chart_b=chart_b,
            name_a=request.person1_name or "Person 1",
            name_b=request.person2_name or "Person 2",
            config=cfg,
        )

        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= SARVATOBHADRA CHAKRA =============

@app.post("/api/astrology/sarvatobhadra")
async def get_sarvatobhadra(
    birth_details: BirthDetails,
    name_nakshatra: Optional[int] = None,
    current_date: Optional[str] = None,
    current_time: Optional[str] = None,
    current_tz: Optional[float] = None,
    ayanamsa: str = DEFAULT_AYANAMSA,
    current_user: str = Depends(get_current_user),
):
    """Sarvatobhadra Chakra with today's transits + vedha on the native's stars."""
    try:
        sbc = AstrologyCompute.get_sarvatobhadra_chakra(
            dob=birth_details.dob, tob=birth_details.tob, place=birth_details.place,
            lat=birth_details.latitude, lon=birth_details.longitude, tz=birth_details.timezone,
            name_nakshatra=name_nakshatra, current_date=current_date,
            current_time=current_time, current_tz=current_tz, ayanamsa=ayanamsa,
        )
        if sbc.get("status") != "success":
            raise HTTPException(status_code=400, detail=sbc.get("error", "Calculation failed"))
        return sbc
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/astrology/sarvatobhadra-analysis")
async def analyze_sarvatobhadra(
    request: SarvatobhadraAnalysisRequest,
    current_user: str = Depends(get_current_user),
):
    """Plain-language AI reading of the Sarvatobhadra Chakra transit picture."""
    _enforce_rate_limit(current_user)
    try:
        bd = request.birth_details
        sbc = AstrologyCompute.get_sarvatobhadra_chakra(
            dob=bd.dob, tob=bd.tob, place=bd.place,
            lat=bd.latitude, lon=bd.longitude, tz=bd.timezone,
            name_nakshatra=request.name_nakshatra, current_date=request.current_date,
            current_time=request.current_time, current_tz=request.current_tz,
            ayanamsa=request.ayanamsa or DEFAULT_AYANAMSA,
        )
        if sbc.get("status") != "success":
            raise HTTPException(status_code=400, detail=sbc.get("error", "Calculation failed"))

        cfg = await _resolve_cfg(current_user, request)
        ai_analysis = await llm_service.analyze_sarvatobhadra(
            sbc_data=sbc, name=request.person_name or "this person", config=cfg,
        )
        return {
            "ai_analysis": ai_analysis,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= LEARN THE CHART (AI QUIZ) =============

QUIZ_TOPICS = ("planets", "yogas", "dashas", "vargas")
QUIZ_LEVELS = ("beginner", "intermediate", "advanced")


def _quiz_context(birth_details: dict, topics: list, ayanamsa: str) -> dict:
    """Build a chart context tailored to the quiz topics. The full /ask context
    (ashtakavarga + shadbala + every varga) is ~3.5k tokens — too big for small
    local models, which then exhaust their output budget and return nothing. Only
    pull the sections a topic actually needs."""
    sections = {"dasha_tree": False, "yogas": False, "doshas": False,
                "transits": False, "ashtakavarga": False, "shadbala": False}
    vargas = [1]
    if "yogas" in topics:
        sections["yogas"] = True
        sections["doshas"] = True
    if "dashas" in topics:
        sections["dasha_tree"] = True
        sections["transits"] = True
    if "vargas" in topics:
        vargas = [1, 9, 10]
    return build_chart_context(
        birth_details=birth_details, ayanamsa=ayanamsa,
        sections=sections, vargas=vargas,
    )


class QuizGenerateRequest(BaseModel):
    birth_details: BirthDetails
    profile_id: Optional[str] = None
    topics: Optional[list] = None        # subset of planets/yogas/dashas/vargas
    level: str = "beginner"              # beginner|intermediate|advanced
    adaptive: bool = False               # when true, level is chosen from the user's stats
    num_mcq: int = 5
    num_free: int = 3
    # Model selection (same shape as the other AI endpoints; used by _resolve_cfg)
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    ayanamsa: Optional[str] = None


class QuizGradeRequest(BaseModel):
    session_id: str
    answers: dict                        # {question_id: answer}  (str for free, int index for mcq)
    # Model selection (free-text grading uses the AI; MCQ is graded deterministically)
    llm_provider: str = "qwen"
    provider_type: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    ayanamsa: Optional[str] = None


@app.post("/api/astrology/quiz/generate")
async def quiz_generate(
    request: QuizGenerateRequest,
    current_user: str = Depends(get_current_user),
):
    """Generate an AI quiz grounded in this chart's computed facts. Returns the
    questions WITHOUT their answer keys (kept server-side until grading)."""
    _enforce_rate_limit(current_user)
    try:
        topics = [t for t in (request.topics or []) if t in QUIZ_TOPICS] or list(QUIZ_TOPICS)
        level = request.level if request.level in QUIZ_LEVELS else "beginner"
        num_mcq = max(0, min(10, int(request.num_mcq)))
        num_free = max(0, min(10, int(request.num_free)))
        if num_mcq + num_free == 0:
            raise HTTPException(status_code=422, detail="Ask for at least one question.")

        # Adaptive: pick the level (and emphasise weak topics) from the user's history.
        focus_note = ""
        if request.adaptive:
            stats = await quiz.get_stats(current_user, request.profile_id)
            level = quiz.suggest_level(stats.get("overall_avg"))
            weak = [t for t in stats.get("weak_topics", []) if t in topics]
            if weak:
                focus_note = ("Weight more questions toward these weaker topics: "
                              + ", ".join(weak))

        chart_data = _quiz_context(
            request.birth_details.model_dump(), topics,
            request.ayanamsa or DEFAULT_AYANAMSA,
        )
        cfg = await _resolve_cfg(current_user, request)
        items = await llm_service.generate_quiz(
            chart_data=chart_data, topics=topics, level=level,
            num_mcq=num_mcq, num_free=num_free, focus_note=focus_note, config=cfg,
        )
        session_id = await quiz.create_session(
            user_id=current_user, profile_id=request.profile_id,
            birth_details=request.birth_details.model_dump(), topics=topics,
            level=level, adaptive=request.adaptive, items=items,
            provider=cfg.provider_type.value, model=cfg.model,
        )
        return {
            "session_id": session_id,
            "topics": topics,
            "level": level,
            "adaptive": request.adaptive,
            "questions": quiz.public_items(items),
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/astrology/quiz/grade")
async def quiz_grade(
    request: QuizGradeRequest,
    current_user: str = Depends(get_current_user),
):
    """Grade a quiz: MCQ deterministically, free-text via the AI. Persists the
    result and returns per-question feedback + reasoning, score, and topic scores."""
    _enforce_rate_limit(current_user)
    try:
        session = await quiz.get_session(current_user, request.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Quiz session not found.")
        if session.get("status") == "graded":
            raise HTTPException(status_code=409, detail="This quiz was already graded.")

        items = session.get("items", [])
        answers = request.answers or {}

        # MCQ — graded deterministically against the stored key.
        graded: dict = {}
        for it in items:
            if it.get("format") != "mcq":
                continue
            raw = answers.get(it["id"])
            try:
                chosen = int(raw)
            except (TypeError, ValueError):
                chosen = None
            correct = it.get("correct_index")
            is_correct = chosen is not None and chosen == correct
            graded[it["id"]] = {
                "score": 1.0 if is_correct else 0.0,
                "verdict": "correct" if is_correct else "incorrect",
                "chosen_index": chosen,
                "correct_index": correct,
                "reasoning": it.get("rationale", ""),
            }

        # Free-text — graded by the AI against expected points + chart facts.
        free_items = [it for it in items if it.get("format") == "free"]
        cfg = await _resolve_cfg(current_user, request)
        if free_items:
            chart_data = _quiz_context(
                session.get("birth_details", {}), session.get("topics", []),
                request.ayanamsa or DEFAULT_AYANAMSA,
            )
            free_grades = await llm_service.grade_quiz_answers(
                chart_data=chart_data, free_items=free_items, answers=answers, config=cfg,
            )
            for it in free_items:
                g = free_grades.get(it["id"], {
                    "score": 0.0, "verdict": "incorrect",
                    "what_was_right": "", "what_was_wrong": "Answer could not be graded.",
                    "reasoning": it.get("rationale", ""),
                })
                graded[it["id"]] = g

        # Assemble per-question result rows (reveal the answer key now).
        results = []
        for it in items:
            g = graded.get(it["id"], {})
            row = {
                "id": it["id"],
                "topic": it.get("topic"),
                "format": it.get("format"),
                "difficulty": it.get("difficulty"),
                "question": it.get("question"),
                "your_answer": answers.get(it["id"]),
                "score": g.get("score", 0.0),
                "verdict": g.get("verdict", "incorrect"),
                "reasoning": g.get("reasoning", it.get("rationale", "")),
            }
            if it.get("format") == "mcq":
                row["options"] = it.get("options", [])
                row["correct_index"] = it.get("correct_index")
                row["chosen_index"] = g.get("chosen_index")
            else:
                row["expected_points"] = it.get("expected_points", [])
                row["what_was_right"] = g.get("what_was_right", "")
                row["what_was_wrong"] = g.get("what_was_wrong", "")
            results.append(row)

        overall = round(sum(r["score"] for r in results) / len(results), 3) if results else 0.0
        topic_scores = quiz.compute_topic_scores(results)
        await quiz.save_grading(current_user, request.session_id, answers,
                                results, overall, topic_scores)
        return {
            "session_id": request.session_id,
            "score": overall,
            "topic_scores": topic_scores,
            "results": results,
            "provider": cfg.provider_type.value,
            "model": cfg.model,
        }
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/astrology/quiz/history")
async def quiz_history(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """List the user's past quiz sessions (optionally for one profile)."""
    sessions = await quiz.list_sessions(current_user, profile_id)
    return {"sessions": sessions}


@app.get("/api/astrology/quiz/stats")
async def quiz_stats(
    profile_id: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    """Per-topic mastery, overall average, streak and weak areas for the user."""
    return await quiz.get_stats(current_user, profile_id)


@app.delete("/api/astrology/quiz/{session_id}")
async def quiz_delete(
    session_id: str,
    current_user: str = Depends(get_current_user),
):
    ok = await quiz.delete_session(current_user, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Quiz session not found.")
    return {"status": "deleted"}

# ============= LOCATION SEARCH =============

class LocationSearchRequest(BaseModel):
    query: str  # e.g., "Chennai, India" or "New York, USA"

@app.post("/api/location/search")
async def search_location(req: LocationSearchRequest):
    """
    Search for a location and return its coordinates and timezone.
    This makes it easy for users to get lat/long without manually looking it up.

    Example queries:
    - "Chennai, India"
    - "New York, USA"
    - "London, UK"
    """
    try:
        result = AstrologyCompute.search_location(req.query)
        if result:
            return {
                "success": True,
                "place": result[0],
                "latitude": result[1],
                "longitude": result[2],
                "timezone": result[3]
            }
        else:
            return {
                "success": False,
                "message": f"Location '{req.query}' not found. Try format: 'City, Country' (e.g., 'Mumbai, India')"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Location search error: {str(e)}")


class ReverseGeocodeRequest(BaseModel):
    latitude: float
    longitude: float

@app.post("/api/location/reverse")
async def reverse_geocode(req: ReverseGeocodeRequest):
    """Resolve a map-picked lat/long to a place name + timezone offset.

    Backs the interactive map picker. Gated by MAP_PICKER_ENABLED so the whole
    feature can be switched off for production deployments (the frontend hides
    the UI via REACT_APP_ENABLE_MAP_PICKER; this guard is defense in depth).
    """
    if not settings.MAP_PICKER_ENABLED:
        raise HTTPException(status_code=403, detail="Map location picker is disabled.")
    if not (-90 <= req.latitude <= 90) or not (-180 <= req.longitude <= 180):
        raise HTTPException(status_code=400, detail="Coordinates out of range.")
    try:
        result = AstrologyCompute.reverse_geocode(req.latitude, req.longitude)
        if result:
            return {
                "success": True,
                "place": result[0],
                "latitude": result[1],
                "longitude": result[2],
                "timezone": result[3],
            }
        return {"success": False, "message": "Could not resolve that location."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reverse geocode error: {str(e)}")

# ============= SAVED PROFILES =============

class SaveProfileRequest(BaseModel):
    profile_name: str
    birth_details: BirthDetails
    is_default: bool = False

@app.post("/api/profiles/save")
async def save_profile(req: SaveProfileRequest, current_user: str = Depends(get_current_user)):
    """Save a birth profile for quick access"""
    try:
        from database import database, SavedProfile

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        # If this is set as default, unset all other defaults
        if req.is_default:
            await profiles_collection.update_many(
                {"user_id": current_user},
                {"$set": {"is_default": False}}
            )

        # Create profile
        profile = SavedProfile(
            user_id=current_user,
            profile_name=req.profile_name,
            birth_details=req.birth_details,
            is_default=req.is_default
        )

        result = await profiles_collection.insert_one(profile.model_dump(by_alias=True, exclude={"id"}))

        return {
            "success": True,
            "profile_id": str(result.inserted_id),
            "message": f"Profile '{req.profile_name}' saved successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/profiles/{profile_id}")
async def update_profile(profile_id: str, req: SaveProfileRequest, current_user: str = Depends(get_current_user)):
    """Update an existing birth profile"""
    try:
        from database import database
        from bson import ObjectId

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        # If this is set as default, unset all other defaults
        if req.is_default:
            await profiles_collection.update_many(
                {"user_id": current_user},
                {"$set": {"is_default": False}}
            )

        result = await profiles_collection.update_one(
            {"_id": ObjectId(profile_id), "user_id": current_user},
            {"$set": {
                "profile_name": req.profile_name,
                "birth_details": req.birth_details.model_dump(),
                "is_default": req.is_default,
            }}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {
            "success": True,
            "message": f"Profile '{req.profile_name}' updated successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/profiles/list")
async def list_profiles(current_user: str = Depends(get_current_user)):
    """Get all saved profiles for the current user"""
    try:
        from database import database

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        profiles = await profiles_collection.find({"user_id": current_user}).sort("created_at", -1).to_list(100)

        # Convert ObjectId to string
        for profile in profiles:
            profile["_id"] = str(profile["_id"])

        return {
            "success": True,
            "profiles": profiles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/profiles/{profile_id}")
async def delete_profile(profile_id: str, current_user: str = Depends(get_current_user)):
    """Delete a saved profile"""
    try:
        from database import database
        from bson import ObjectId

        if database is None:
            raise HTTPException(status_code=500, detail="Database not connected")

        profiles_collection = database["saved_profiles"]

        result = await profiles_collection.delete_one({
            "_id": ObjectId(profile_id),
            "user_id": current_user
        })

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Profile not found")

        return {"success": True, "message": "Profile deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= HEALTH CHECK =============

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "pyjhora_available": AstrologyCompute.PYJHORA_AVAILABLE,
        "qwen_enabled": settings.USE_QWEN,
        "map_picker_enabled": settings.MAP_PICKER_ENABLED
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)