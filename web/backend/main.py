from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Optional
from pydantic import BaseModel

from config import settings
from database import connect_to_mongo, close_mongo_connection
from auth import create_access_token, decode_token, get_password_hash, verify_password, Token
from database import User, BirthDetails, ChartData, Prediction
from astrology import AstrologyCompute
from qwen_predictor import QwenPredictor
from llm_service import llm_service, LLMProvider

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
    llm_provider: str = "qwen"  # qwen, gemini, or chatgpt

class PredictionRequest(BaseModel):
    birth_details: BirthDetails
    prediction_type: str = "general"  # general, health, career, relationships
    llm_provider: str = "qwen"

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
            tz=5.5
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
            tz=birth_details.timezone
        )
        return doshas
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/yogas")
async def get_yogas(
    birth_details: BirthDetails,
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
            tz=birth_details.timezone
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

@app.post("/api/astrology/transit")
async def get_transits(
    birth_details: BirthDetails,
    current_date: Optional[str] = None,
    current_user: str = Depends(get_current_user)
):
    """Get current transits"""
    try:
        transits = AstrologyCompute.get_transits(
            dob=birth_details.dob,
            tob=birth_details.tob,
            place=birth_details.place,
            lat=birth_details.latitude,
            lon=birth_details.longitude,
            tz=birth_details.timezone,
            current_date=current_date
        )
        return transits
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/compatibility")
async def get_compatibility(
    male_dob: str,
    male_tob: str,
    male_place: str,
    female_dob: str,
    female_tob: str,
    female_place: str,
    male_latitude: Optional[float] = None,
    male_longitude: Optional[float] = None,
    male_timezone: Optional[float] = None,
    female_latitude: Optional[float] = None,
    female_longitude: Optional[float] = None,
    female_timezone: Optional[float] = None,
    use_qwen: bool = False,
    current_user: str = Depends(get_current_user)
):
    """Calculate compatibility"""
    try:
        compatibility = AstrologyCompute.get_compatibility(
            male_dob=male_dob,
            male_tob=male_tob,
            male_place=male_place,
            male_lat=male_latitude,
            male_lon=male_longitude,
            female_dob=female_dob,
            female_tob=female_tob,
            female_place=female_place,
            female_lat=female_latitude,
            female_lon=female_longitude,
            tz=male_timezone or female_timezone or 5.5
        )

        if use_qwen and settings.USE_QWEN:
            chart1 = AstrologyCompute.get_horoscope_predictions(
                male_dob, male_tob, male_place,
                lat=male_latitude, lon=male_longitude, tz=male_timezone
            )
            chart2 = AstrologyCompute.get_horoscope_predictions(
                female_dob, female_tob, female_place,
                lat=female_latitude, lon=female_longitude, tz=female_timezone
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

@app.post("/api/astrology/ask")
async def ask_question(
    request: AskQuestionRequest,
    current_user: str = Depends(get_current_user)
):
    """Ask a question about the birth chart using AI"""
    try:
        # Get full chart data
        chart_data = AstrologyCompute.get_horoscope_predictions(
            dob=request.birth_details.dob,
            tob=request.birth_details.tob,
            place=request.birth_details.place,
            lat=request.birth_details.latitude,
            lon=request.birth_details.longitude,
            tz=5.5
        )

        # Validate LLM provider
        try:
            provider = LLMProvider(request.llm_provider.lower())
        except ValueError:
            provider = LLMProvider.QWEN

        # Get AI response
        answer = await llm_service.ask_question(
            chart_data=chart_data,
            question=request.question,
            provider=provider
        )

        return {
            "question": request.question,
            "answer": answer,
            "provider": request.llm_provider,
            "chart_summary": {
                "lagna": chart_data.get("lagna", {}),
                "moon_sign": chart_data.get("moon_sign", {}),
                "sun_sign": chart_data.get("sun_sign", {})
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/predict")
async def generate_prediction(
    request: PredictionRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate AI-powered predictions"""
    try:
        # Get full chart data
        chart_data = AstrologyCompute.get_horoscope_predictions(
            dob=request.birth_details.dob,
            tob=request.birth_details.tob,
            place=request.birth_details.place,
            lat=request.birth_details.latitude,
            lon=request.birth_details.longitude,
            tz=5.5
        )

        # Validate LLM provider
        try:
            provider = LLMProvider(request.llm_provider.lower())
        except ValueError:
            provider = LLMProvider.QWEN

        # Generate prediction
        prediction = await llm_service.generate_prediction(
            chart_data=chart_data,
            prediction_type=request.prediction_type,
            provider=provider
        )

        return {
            "prediction_type": request.prediction_type,
            "prediction": prediction,
            "provider": request.llm_provider,
            "chart_data": chart_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/astrology/compatibility-analysis")
async def analyze_compatibility(
    male_details: BirthDetails,
    female_details: BirthDetails,
    llm_provider: str = "qwen",
    current_user: str = Depends(get_current_user)
):
    """Get detailed compatibility analysis with AI"""
    try:
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
            tz=5.5
        )

        # Get chart data for both
        male_chart = AstrologyCompute.get_horoscope_predictions(
            dob=male_details.dob,
            tob=male_details.tob,
            place=male_details.place,
            lat=male_details.latitude,
            lon=male_details.longitude,
            tz=5.5
        )

        female_chart = AstrologyCompute.get_horoscope_predictions(
            dob=female_details.dob,
            tob=female_details.tob,
            place=female_details.place,
            lat=female_details.latitude,
            lon=female_details.longitude,
            tz=5.5
        )

        # Validate LLM provider
        try:
            provider = LLMProvider(llm_provider.lower())
        except ValueError:
            provider = LLMProvider.QWEN

        # Get AI analysis
        ai_analysis = await llm_service.analyze_compatibility(
            male_chart=male_chart,
            female_chart=female_chart,
            koota_score=compatibility.get("total_score", 0),
            provider=provider
        )

        return {
            "compatibility_score": compatibility,
            "ai_analysis": ai_analysis,
            "provider": llm_provider
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        "qwen_enabled": settings.USE_QWEN
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)