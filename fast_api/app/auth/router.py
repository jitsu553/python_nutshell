# app/auth/router.py
from datetime import datetime, timezone
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user, get_db
from app.auth.models import Role, Session as DBSession, User
from app.auth.schemas import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.auth.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_SAMESITE = os.getenv("COOKIE_SAMESITE", "lax")


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str | None = None):
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    if refresh_token:
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE,
            max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    # 1. Check if user already exists
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 2. Get or create default "user" role
    role = db.query(Role).filter(Role.name == "user").first()
    if not role:
        role = Role(name="user")
        db.add(role)
        db.flush()  # flush to get role.id without committing yet

    # 3. Hash password and create user
    new_user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role_id=role.id,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        is_active=new_user.is_active,
        role=role.name,
    )


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    # 1. Find user
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # 2. Issue tokens
    role_name = user.role.name if user.role else None
    access_token = create_access_token(subject=user.email, role=role_name)
    refresh_token, expires_at = create_refresh_token(subject=user.email)

    # 3. Store refresh token in sessions table
    session = DBSession(
        refresh_token=refresh_token,
        user_id=user.id,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    _set_auth_cookies(response=response, access_token=access_token, refresh_token=refresh_token)

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    body: RefreshRequest | None = None,
    db: Session = Depends(get_db),
):
    credentials_exception = HTTPException(status_code=401, detail="Invalid refresh token")
    refresh_token = body.refresh_token if body else request.cookies.get("refresh_token")
    if not refresh_token:
        raise credentials_exception

    # 1. Decode the refresh token
    try:
        payload = decode_token(refresh_token)
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "refresh":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    # 2. Verify it exists in DB and is not expired
    session = db.query(DBSession).filter(
        DBSession.refresh_token == refresh_token
    ).first()

    if not session or session.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise credentials_exception

    # 3. Find user and issue new access token
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise credentials_exception

    role_name = user.role.name if user.role else None
    new_access_token = create_access_token(subject=user.email, role=role_name)
    _set_auth_cookies(response=response, access_token=new_access_token)

    return AccessTokenResponse(access_token=new_access_token)


@router.get("/profile", response_model=UserResponse)
def profile(current_user: User = Depends(get_current_user)):
    """
    Protected route — no DB query needed here.
    get_current_user already fetched the user from DB via the token.
    FastAPI calls Depends(get_current_user) before this function runs.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        is_active=current_user.is_active,
        role=current_user.role.name if current_user.role else None,
    )