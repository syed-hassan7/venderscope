"""Google OAuth 2.0 — login and optional account linking."""

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import HTTPException
from jwt import PyJWKClient
from sqlalchemy.orm import Session

from config import get_primary_frontend_url
from models import OAuthState, User
from services.auth_service import ALGORITHM, JWT_SECRET

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")
STATE_TTL_MINUTES = 10


def _client_id() -> str:
    cid = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    if not cid:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    return cid


def _client_secret() -> str:
    secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured")
    return secret


def _redirect_uri() -> str:
    explicit = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    if explicit:
        return explicit
    return f"{get_primary_frontend_url()}/api/auth/google/callback"


def _frontend_login_url(query: str = "") -> str:
    base = f"{get_primary_frontend_url()}/login"
    return f"{base}{query}" if query else base


def create_oauth_state(
    db: Session,
    purpose: str,
    user_id: str | None = None,
) -> tuple[str, str]:
    state = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(48)
    nonce = secrets.token_urlsafe(16)
    row = OAuthState(
        id=str(uuid.uuid4()),
        state=state,
        code_verifier=code_verifier,
        nonce=nonce,
        purpose=purpose,
        user_id=user_id,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES),
    )
    db.add(row)
    db.commit()
    return state, code_verifier


def build_authorize_url(db: Session, purpose: str, user_id: str | None = None) -> str:
    state, code_verifier = create_oauth_state(db, purpose, user_id=user_id)
    params = {
        "client_id": _client_id(),
        "redirect_uri": _redirect_uri(),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": db.query(OAuthState).filter(OAuthState.state == state).first().nonce,
        "code_challenge": _pkce_challenge(code_verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def _pkce_challenge(verifier: str) -> str:
    import hashlib
    import base64

    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _consume_state(db: Session, state: str) -> OAuthState:
    row = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not row:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    db.delete(row)
    db.commit()
    return row


def exchange_code_and_verify_id_token(db: Session, code: str, state: str) -> dict:
    oauth_row = _consume_state(db, state)
    try:
        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "code": code,
                "code_verifier": oauth_row.code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": _redirect_uri(),
            },
            timeout=15,
        )
        resp.raise_for_status()
        token_data = resp.json()
    except httpx.HTTPError:
        raise HTTPException(status_code=400, detail="Google sign-in failed")

    id_token = token_data.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="Google sign-in failed")

    jwks_client = PyJWKClient("https://www.googleapis.com/oauth2/v3/certs")
    signing_key = jwks_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=_client_id(),
        issuer=GOOGLE_ISSUERS,
    )

    if claims.get("nonce") != oauth_row.nonce:
        raise HTTPException(status_code=400, detail="Google sign-in failed")

    if not claims.get("email_verified"):
        raise HTTPException(status_code=400, detail="Google email is not verified")

    return {
        "sub": claims["sub"],
        "email": claims.get("email", "").lower(),
        "purpose": oauth_row.purpose,
        "link_user_id": oauth_row.user_id,
    }


def resolve_google_login(db: Session, google_info: dict) -> User:
    sub = google_info["sub"]
    email = google_info["email"]
    purpose = google_info["purpose"]
    link_user_id = google_info.get("link_user_id")

    if purpose == "link":
        if not link_user_id:
            raise HTTPException(status_code=400, detail="Invalid link session")
        user = db.query(User).filter(User.id == link_user_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Invalid link session")
        existing_sub = db.query(User).filter(User.google_sub == sub).first()
        if existing_sub and existing_sub.id != user.id:
            raise HTTPException(status_code=409, detail="Google account already linked to another user")
        user.google_sub = sub
        db.commit()
        return user

    # login purpose — new user or existing google_sub only (no silent email link)
    by_sub = db.query(User).filter(User.google_sub == sub).first()
    if by_sub:
        return by_sub

    by_email = db.query(User).filter(User.email == email).first()
    if by_email:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists. Sign in with your password or passkey, then link Google from settings.",
        )

    raise HTTPException(
        status_code=404,
        detail="No account found. Create an account with a passkey first.",
    )


GOOGLE_PENDING_TTL_MINUTES = 15
GOOGLE_PENDING_TYPE = "google_pending"
GOOGLE_STEPUP_TTL_MINUTES = 5
GOOGLE_STEPUP_TYPE = "google_stepup"


def mint_google_pending_token(*, sub: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=GOOGLE_PENDING_TTL_MINUTES)
    payload = {
        "type": GOOGLE_PENDING_TYPE,
        "google_sub": sub,
        "email": email.lower().strip(),
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def read_google_pending_token(token: str | None) -> dict | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != GOOGLE_PENDING_TYPE:
        return None
    google_sub = payload.get("google_sub")
    email = payload.get("email")
    if not isinstance(google_sub, str) or not google_sub:
        return None
    if not isinstance(email, str) or not email:
        return None
    return {"google_sub": google_sub, "email": email.lower().strip()}


def mint_google_stepup_token(*, user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=GOOGLE_STEPUP_TTL_MINUTES)
    payload = {"type": GOOGLE_STEPUP_TYPE, "user_id": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)


def read_google_stepup_token(token: str | None) -> str | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != GOOGLE_STEPUP_TYPE:
        return None
    user_id = payload.get("user_id")
    if not isinstance(user_id, str) or not user_id:
        return None
    return user_id


def verify_google_stepup(db: Session, google_info: dict) -> User:
    """Verify a completed 'step_up' OAuth round trip proves control of the SAME
    Google account already on file — not just any Google login."""
    user_id = google_info.get("link_user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid step-up session")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid step-up session")
    if user.google_sub != google_info["sub"]:
        raise HTTPException(status_code=409, detail="Google account does not match")
    return user
