from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config import settings
from typing import Optional
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
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}

class Prediction(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id")
    user_id: str
    chart_id: str
    prediction_type: str  # "horoscope", "compatibility", etc
    prediction_text: str
    generated_by: str  # "rule_based" or "qwen"
    created_at: datetime = Field(default_factory=datetime.utcnow)

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
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}