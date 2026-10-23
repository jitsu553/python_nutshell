# app/auth/security.py
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# --- Configuration ---
ALGORITHM = "HS256"
REFRESH_TOKEN_EXPIRE_DAYS = 7

# --- Password hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Takes a plain string, returns a bcrypt hash."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Checks if plain_password matches the stored hash. Returns True/False."""
    return pwd_context.verify(plain_password, hashed_password)


# --- JWT tokens ---
def create_access_token(subject: str, role: str | None = None) -> str:
    """
    Create a short-lived access token.
    'subject' is typically the user's email or id (the identity claim).
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=get_settings().access_token_expire_minutes)
    payload = {
        "sub": subject,         # 'sub' is a standard JWT claim meaning 'subject'
        "role": role,
        "exp": expire,          # 'exp' is a standard JWT claim meaning 'expires at'
        "type": "access",
    }
    return jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)


def create_refresh_token(subject: str) -> tuple[str, datetime]:
    """
    Create a long-lived refresh token.
    Returns the token string AND its expiry datetime (so you can store it in DB).
    """
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
    }
    token = jwt.encode(payload, get_settings().secret_key, algorithm=ALGORITHM)
    return token, expire


def decode_token(token: str) -> dict:
    """
    Decode and verify a JWT. Raises JWTError if invalid or expired.
    Returns the payload dict if valid.
    """
    return jwt.decode(token, get_settings().secret_key, algorithms=[ALGORITHM])