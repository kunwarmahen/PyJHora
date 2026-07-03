from pydantic_settings import BaseSettings
from typing import List

# Populate os.environ from .env so modules that read os.getenv() directly
# (e.g. llm_service) see the same values pydantic-settings loads here.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

class Settings(BaseSettings):
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "pyjhora_db"
    SECRET_KEY: str = "your-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    # Refresh-token lifetimes. A long-lived, revocable refresh token lets the
    # frontend silently mint fresh access tokens, so users aren't logged out
    # every ACCESS_TOKEN_EXPIRE_MINUTES. "Remember me" picks the long TTL; a
    # plain login gets the short one.
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    REFRESH_TOKEN_SHORT_DAYS: int = 1

    QWEN_API_URL: str = "http://localhost:5000"
    USE_QWEN: bool = False

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Interactive map location picker (Leaflet + OpenStreetMap). When False the
    # backend reverse-geocode endpoint returns 403 so the feature can be fully
    # disabled for production deployments. The frontend has its own
    # REACT_APP_ENABLE_MAP_PICKER flag to hide the UI; keep the two in sync.
    MAP_PICKER_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
