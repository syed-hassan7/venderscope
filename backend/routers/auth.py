import os
import uuid
from typing import Any, Literal, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Cookie, Response, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, field_validator
import jwt
from jwt.exceptions import PyJWTError as JWTError
from config import is_allowed_frontend_origin, is_production, get_primary_frontend_url
from database import get_db
from datetime import datetime, timezone
from models import User, RevokedToken
from limiter import limiter
from services.audit import audit
from services.auth_factors import get_user_factors
from services.auth_service import (
    verify_password,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_optional_user,
    REFRESH_TOKEN_EXPIRE_DAYS,
    JWT_SECRET,
    ALGORITHM,
)
from services.recovery_service import consume_recovery_code
from services.webauthn_service import (
    begin_registration,
    finish_registration,
    begin_assertion,
    finish_assertion,
    begin_step_up,
    finish_step_up,
)
from services.google_oauth_service import (
    build_authorize_url,
    exchange_code_and_verify_id_token,
    resolve_google_login,
)

router = APIRouter()

# Detect production (Render sets RENDER=true)
_IS_PROD = is_production()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 12:
            raise ValueError("Password must be at least 12 characters")
        if len(v) > 128:
            raise ValueError("Password must be under 128 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one number")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_max_length(cls, v):
        if len(v) > 128:
            raise ValueError("Password too long")
        return v


class DeleteAccountRequest(BaseModel):
    method: Literal["password", "recovery", "webauthn"]
    password: Optional[str] = None
    recovery_code: Optional[str] = None
    challenge_id: Optional[str] = None
    credential: Optional[dict[str, Any]] = None

    @field_validator("password")
    @classmethod
    def password_max_length(cls, v: str | None) -> str | None:
        if v is not None and len(v) > 128:
            raise ValueError("Password too long")
        return v


class WebAuthnRegisterBeginRequest(BaseModel):
    email: EmailStr


class WebAuthnRegisterFinishRequest(BaseModel):
    challenge_id: str
    credential: dict[str, Any]
    device_label: Optional[str] = None


class WebAuthnAssertBeginRequest(BaseModel):
    email: Optional[EmailStr] = None


class WebAuthnAssertFinishRequest(BaseModel):
    challenge_id: str
    credential: dict[str, Any]


class RecoveryConsumeRequest(BaseModel):
    email: EmailStr
    code: str


def _issue_session(
    response: Response,
    user: User,
    request: Request,
    db: Session,
    audit_event: str,
) -> dict:
    audit(db, audit_event, request, user_id=user.id)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="vs_refresh",
        value=token,
        httponly=True,
        secure=_IS_PROD,
        samesite="none" if _IS_PROD else "lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/api/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key="vs_refresh",
        path="/api/auth",
        samesite="none" if _IS_PROD else "lax",
        secure=_IS_PROD,
    )


def _verify_origin(request: Request) -> None:
    """
    Defence-in-depth CSRF protection for endpoints that consume the httpOnly refresh cookie.

    Primary protection: all JSON endpoints trigger a CORS preflight which blocks
    cross-origin requests for unlisted origins. This is the second layer — a
    server-side check that covers edge cases where preflight is bypassed (e.g.
    same-origin redirects, non-standard clients, future endpoint changes).

    Skipped when no Origin/Referer header is present.
    """
    origin = request.headers.get("origin") or request.headers.get("referer", "")
    if not origin:
        return
    if not is_allowed_frontend_origin(origin):
        raise HTTPException(status_code=403, detail="Origin not allowed")


@router.post("/register")
@limiter.limit("3/hour")
def register(request: Request, background_tasks: BackgroundTasks, payload: RegisterRequest, db: Session = Depends(get_db)):
    raise HTTPException(
        status_code=403,
        detail="Password registration is closed. Create an account with a passkey and recovery codes.",
    )


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    # Always run bcrypt to prevent timing-based user enumeration (CRIT-01)
    dummy_hash = "$2b$12$LJ3m4ys3Lk0TDBGfGgsZKeDUxPlvMNnbBOHJbEHYsV3eIEfpyQ1SK"
    pw_hash = user.password_hash if user else dummy_hash
    password_ok = verify_password(payload.password, pw_hash)
    if not (user is not None and password_ok):
        audit(db, "login.failed", request, detail=f"email={payload.email.lower()}")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    audit(db, "login.success", request, user_id=user.id)
    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, refresh_token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/refresh")
@limiter.limit("10/minute")
def refresh_token_endpoint(
    request: Request,
    response: Response,
    vs_refresh: str = Cookie(default=None),
    db: Session = Depends(get_db),
):
    _verify_origin(request)
    if not vs_refresh:
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = jwt.decode(vs_refresh, JWT_SECRET, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id: str = payload.get("sub")
        jti: str     = payload.get("jti")
        if not user_id or not jti:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Reject if this token was already revoked (logout or prior rotation)
    if db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        raise HTTPException(status_code=401, detail="Token has been revoked")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Revoke the old JTI immediately — each refresh token is single-use
    exp = payload.get("exp")
    if exp:
        db.add(RevokedToken(
            jti=jti,
            expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        ))
        db.commit()

    new_access_token  = create_access_token(user.id)
    new_refresh_token = create_refresh_token(user.id)
    _set_refresh_cookie(response, new_refresh_token)
    return {"access_token": new_access_token}


@router.post("/logout")
@limiter.limit("20/minute")
def logout(
    request: Request,
    response: Response,
    vs_refresh: str = Cookie(default=None),
    db: Session = Depends(get_db),
):
    _verify_origin(request)
    # Blacklist the refresh token's JTI so it can't be reused after logout
    if vs_refresh:
        try:
            payload = jwt.decode(vs_refresh, JWT_SECRET, algorithms=[ALGORITHM])
            jti = payload.get("jti")
            exp = payload.get("exp")
            if jti and exp:
                expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
                if expires_at > datetime.now(timezone.utc):
                    db.add(RevokedToken(jti=jti, expires_at=expires_at))
                    db.commit()
        except JWTError:
            pass  # Malformed or already-expired token — nothing to revoke
    # Determine user_id for the audit log (best-effort — token may already be expired)
    _uid = None
    if vs_refresh:
        try:
            _uid = jwt.decode(vs_refresh, JWT_SECRET, algorithms=[ALGORITHM]).get("sub")
        except JWTError:
            pass
    audit(db, "logout", request, user_id=_uid)
    _clear_refresh_cookie(response)
    return {"message": "Logged out"}


@router.get("/me")
@limiter.limit("60/minute")
def get_me(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {
        "email": current_user.email,
        "factors": get_user_factors(db, current_user),
    }


@router.post("/webauthn/register/begin")
@limiter.limit("3/hour")
def webauthn_register_begin(
    request: Request,
    payload: WebAuthnRegisterBeginRequest,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    if current_user is not None:
        return begin_registration(db, current_user.email, user=current_user, for_signup=False)
    return begin_registration(db, payload.email, for_signup=True)


@router.post("/webauthn/register/finish")
@limiter.limit("3/hour")
def webauthn_register_finish(
    request: Request,
    response: Response,
    payload: WebAuthnRegisterFinishRequest,
    db: Session = Depends(get_db),
):
    user, recovery_codes = finish_registration(
        db,
        payload.challenge_id,
        payload.credential,
        device_label=payload.device_label,
        issue_recovery_codes=True,
    )
    session = _issue_session(response, user, request, db, "webauthn.register.success")
    result = dict(session)
    if recovery_codes:
        result["recovery_codes"] = recovery_codes
    return result


@router.post("/webauthn/assert/begin")
@limiter.limit("5/minute")
def webauthn_assert_begin(
    request: Request,
    payload: WebAuthnAssertBeginRequest,
    db: Session = Depends(get_db),
):
    return begin_assertion(db, payload.email)


@router.post("/webauthn/assert/finish")
@limiter.limit("5/minute")
def webauthn_assert_finish(
    request: Request,
    response: Response,
    payload: WebAuthnAssertFinishRequest,
    db: Session = Depends(get_db),
):
    user = finish_assertion(db, payload.challenge_id, payload.credential)
    return _issue_session(response, user, request, db, "webauthn.login.success")


@router.post("/webauthn/step-up/begin")
@limiter.limit("5/minute")
def webauthn_step_up_begin(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return begin_step_up(db, current_user)


@router.post("/recovery/consume")
@limiter.limit("5/minute")
def recovery_consume(
    request: Request,
    response: Response,
    payload: RecoveryConsumeRequest,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    dummy_hash = "$2b$12$LJ3m4ys3Lk0TDBGfGgsZKeDUxPlvMNnbBOHJbEHYsV3eIEfpyQ1SK"
    ok = False
    if user:
        ok = consume_recovery_code(db, user.id, payload.code)
    if not ok:
        verify_password(payload.code, dummy_hash)
        audit(db, "recovery.login.failed", request, detail="recovery")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return _issue_session(response, user, request, db, "recovery.login.success")


@router.get("/google/start")
@limiter.limit("10/minute")
def google_start_login(request: Request, db: Session = Depends(get_db)):
    return RedirectResponse(build_authorize_url(db, "login"))


@router.get("/google/link/start")
@limiter.limit("10/minute")
def google_start_link(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RedirectResponse(build_authorize_url(db, "link", user_id=current_user.id))


@router.get("/google/callback")
@limiter.limit("20/minute")
def google_callback(
    request: Request,
    response: Response,
    code: str,
    state: str,
    db: Session = Depends(get_db),
):
    google_info = exchange_code_and_verify_id_token(db, code, state)
    frontend = get_primary_frontend_url()
    try:
        user = resolve_google_login(db, google_info)
    except HTTPException as exc:
        if exc.status_code == 409:
            return RedirectResponse(f"{frontend}/login?error=google_conflict")
        if exc.status_code == 404:
            email = google_info.get("email", "")
            return RedirectResponse(f"{frontend}/register?email={email}&from=google")
        raise

    refresh_token = create_refresh_token(user.id)
    audit(db, "google.login.success", request, user_id=user.id)
    redirect = RedirectResponse(f"{frontend}/?oauth=1")
    _set_refresh_cookie(redirect, refresh_token)
    return redirect


@router.delete("/account")
@limiter.limit("3/hour")
def delete_account(
    request: Request,
    response: Response,
    payload: DeleteAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _verify_origin(request)
    verified = False
    if payload.method == "password":
        if not payload.password or current_user.password_hash is None:
            raise HTTPException(status_code=400, detail="Password verification not available")
        verified = verify_password(payload.password, current_user.password_hash)
    elif payload.method == "recovery":
        if not payload.recovery_code:
            raise HTTPException(status_code=400, detail="Recovery code required")
        verified = consume_recovery_code(db, current_user.id, payload.recovery_code)
    elif payload.method == "webauthn":
        if not payload.challenge_id or not payload.credential:
            raise HTTPException(status_code=400, detail="WebAuthn assertion required")
        try:
            finish_step_up(db, payload.challenge_id, payload.credential, current_user)
            verified = True
        except HTTPException:
            verified = False

    if not verified:
        audit(db, "account.delete.failed", request, user_id=current_user.id)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_id = current_user.id
    db.delete(current_user)
    db.commit()
    audit(db, "account.deleted", request, user_id=user_id)
    _clear_refresh_cookie(response)
    return {"message": "Account deleted"}
