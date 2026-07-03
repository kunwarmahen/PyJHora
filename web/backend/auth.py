from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from pydantic import BaseModel
import bcrypt
from config import settings

# We use the `bcrypt` library directly rather than passlib: passlib 1.7.4 is
# unmaintained and breaks with bcrypt >= 4.1 (it reads bcrypt.__about__.__version__,
# which was removed, and bcrypt 5.x now *raises* on >72-byte inputs instead of
# silently truncating). Produced hashes are standard `$2b$...`, so any existing
# passlib-created hashes remain verifiable.

class TokenData(BaseModel):
    username: Optional[str] = None

class Token(BaseModel):
    access_token: str
    token_type: str
    refresh_token: Optional[str] = None

def _to_bcrypt_bytes(password: str) -> bytes:
    """bcrypt only considers the first 72 BYTES of the password. Encode to UTF-8
    and truncate to 72 bytes (not characters — multibyte chars can exceed it)."""
    return password.encode("utf-8")[:72]

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False

def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(password), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        return username
    except JWTError:
        return None
