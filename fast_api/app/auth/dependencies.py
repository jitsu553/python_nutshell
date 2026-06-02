# app/auth/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.security import decode_token
from app.db import SessionLocal

# --- DB dependency ---
def get_db():
    """
    Yields a database session, then closes it after the request finishes.
    FastAPI calls this automatically for any route that declares it as a dependency.
    The 'yield' makes it a context manager — cleanup happens after the response.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# --- Token extractor ---
# HTTPBearer reads the "Authorization: Bearer <token>" header automatically
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Extracts and validates the access token from the Authorization header.
    Returns the User object if valid. Raises 401 if not.
    This function is injected into any protected route.
    """
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        email: str = payload.get("sub")
        token_type: str = payload.get("type")
        if email is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.email == email).first()
    if user is None or not user.is_active:
        raise credentials_exception

    return user


def require_role(required_role: str):
    """
    Factory function that returns a dependency checking for a specific role.
    Usage: Depends(require_role("admin"))
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if not current_user.role or current_user.role.name != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return current_user
    return role_checker