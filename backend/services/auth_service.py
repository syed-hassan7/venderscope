import config  # Loads backend/.env once with process env precedence.
import os
import uuid
import bcrypt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import PyJWTError as JWTError
from config import is_production
from database import get_db
from models import User

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable is required — set it in .env")
if is_production() and len(JWT_SECRET) < 32:
    raise RuntimeError(
        "JWT_SECRET is too short for production (minimum 32 characters) — a weak "
        "secret makes every JWT forgeable. Set a long random value, e.g. "
        "`openssl rand -hex 32`."
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days is standard for rotation-based refresh tokens; reduced from 30
BCRYPT_ROUNDS = 12

_bearer = HTTPBearer()
_optional_bearer = HTTPBearer(auto_error=False)


def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    return get_current_user(credentials, db)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(BCRYPT_ROUNDS)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def create_access_token(user_id: str, session_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(
        {"sub": user_id, "exp": expire, "type": "access", "sv": int(session_version)},
        JWT_SECRET,
        algorithm=ALGORITHM,
    )


def create_refresh_token(user_id: str, session_version: int = 0) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {
            "sub": user_id,
            "exp": expire,
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "sv": int(session_version),
        },
        JWT_SECRET,
        algorithm=ALGORITHM,
    )


def bump_session_version(db: Session, user: User) -> int:
    user.session_version = int(user.session_version or 0) + 1
    db.commit()
    db.refresh(user)
    return user.session_version


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — validates the Bearer access token and returns the User."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id: str = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")
    if int(payload.get("sv", 0)) != int(user.session_version or 0):
        raise HTTPException(status_code=401, detail="Invalid token")
    return user
