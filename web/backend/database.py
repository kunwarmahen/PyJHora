from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import settings
from typing import Any, Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from bson import ObjectId

# MongoDB Connection
mongodb_client: Optional[AsyncIOMotorClient] = None
database: Optional[AsyncIOMotorDatabase] = None

async def connect_to_mongo():
    global mongodb_client, database
    try:
        mongodb_client = AsyncIOMotorClient(settings.MONGODB_URL)
        await mongodb_client.admin.command('ping')
        database = mongodb_client[settings.DATABASE_NAME]
        print("✅ Connected to MongoDB successfully")
        return True
    except Exception as e:
        print(f"❌ MongoDB connection failed: {str(e)}")
        raise

async def close_mongo_connection():
    global mongodb_client
    if mongodb_client:
        mongodb_client.close()
        print("Disconnected from MongoDB")

def get_database():
    """Get database instance, ensuring it's initialized"""
    if database is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo() first.")
    return database

# Pydantic Models
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, schema: dict, model_type):
        json_schema = super().__get_pydantic_json_schema__(schema, model_type)
        json_schema = {"type": "string"}
        return json_schema

class BirthDetails(BaseModel):
    name: str
    dob: str  # YYYY-MM-DD
    tob: str  # HH:MM (24-hour format)
    place: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    timezone: Optional[float] = None  # Add this line
    # How reliable the birth time is: "exact" (default) | "approximate" | "unknown".
    # "unknown" means Lagna/house-based results should be treated as unreliable and
    # only Moon-referenced indications read.
    time_accuracy: Optional[str] = None

class ChartData(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    user_id: str
    birth_details: BirthDetails
    chart_type: str  # "rasi", "navamsa", "dhasa", etc
    planets_positions: dict
    houses: dict
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    username: str
    email: str
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    # Admin console (§44). `is_admin` is reconciled from ADMIN_USERNAMES at
    # startup — do not set it by hand. `suspended` blocks login/refresh when a
    # moderator disables the account.
    is_admin: bool = False
    suspended: bool = False

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class SavedProfile(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    profile_name: str  # e.g., "My Chart", "John Doe", etc.
    birth_details: BirthDetails
    is_default: bool = False
    # Where this person's digest should be delivered. Empty/None → the account
    # owner receives it (in their combined copy). Set to send this subject their
    # own personal digest at their own address.
    notify_email: Optional[str] = None
    # How often this profile appears in the daily digest: "daily" (default) or
    # "weekly" (only on Mondays — cuts the mail volume for family members whose
    # day-to-day rarely changes). None is treated as "daily".
    digest_frequency: Optional[str] = None
    # Where this person lives *now* (IANA zone + coords), for pacing THEIR digest
    # to THEIR today — distinct from birth details, which never move. None → the
    # digest uses the account owner's clock. Same shape as user_settings'
    # account-level current_location.
    current_location: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}