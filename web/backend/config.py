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

    QWEN_API_URL: str = "http://localhost:5000"
    USE_QWEN: bool = False

    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
