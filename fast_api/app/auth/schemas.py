# app/auth/schemas.py
from pydantic import BaseModel, EmailStr


# --- Register ---
class RegisterRequest(BaseModel):
    email: EmailStr          # pydantic validates it's a real email format
    password: str


# --- Login ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# --- Token responses ---
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --- Refresh ---
class RefreshRequest(BaseModel):
    refresh_token: str


# --- Profile (returned to the client, NEVER includes password) ---
class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    role: str | None = None

    model_config = {"from_attributes": True}  # allows creating from SQLAlchemy model