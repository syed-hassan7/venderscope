"""Per-factor auth management: list/delete passkeys, unlink Google."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from config import is_allowed_frontend_origin
from database import get_db
from limiter import limiter
from models import User, WebAuthnCredential
from services.audit import audit
from services.auth_factors import can_remove_passkey, can_unlink_google
from services.auth_service import get_current_user

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


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


def _current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return get_current_user(credentials, db)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


@router.get("/webauthn/credentials")
@limiter.limit("60/minute")
def list_webauthn_credentials(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_current_user),
):
    creds = (
        db.query(WebAuthnCredential)
        .filter(WebAuthnCredential.user_id == current_user.id)
        .all()
    )
    return [
        {
            "id": c.id,
            "device_label": c.device_label,
            "created_at": _iso(c.created_at),
            "last_used_at": _iso(c.last_used_at),
        }
        for c in creds
    ]


@router.delete("/webauthn/credentials/{cred_id}")
@limiter.limit("10/minute")
def delete_webauthn_credential(
    request: Request,
    cred_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(_current_user),
):
    _verify_origin(request)
    cred = (
        db.query(WebAuthnCredential)
        .filter(
            WebAuthnCredential.id == cred_id,
            WebAuthnCredential.user_id == current_user.id,
        )
        .first()
    )
    if not cred:
        raise HTTPException(status_code=404, detail="Passkey not found")
    if not can_remove_passkey(db, current_user):
        raise HTTPException(status_code=400, detail="Cannot remove last sign-in method")
    db.delete(cred)
    db.commit()
    audit(db, "webauthn.credential.deleted", request, user_id=current_user.id, detail=cred_id)
    return {"message": "Passkey removed"}


@router.post("/google/unlink")
@limiter.limit("10/minute")
def unlink_google(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_current_user),
):
    _verify_origin(request)
    if current_user.google_sub is None:
        raise HTTPException(status_code=400, detail="Google is not linked")
    if not can_unlink_google(db, current_user):
        raise HTTPException(status_code=400, detail="Cannot remove last sign-in method")
    current_user.google_sub = None
    db.commit()
    audit(db, "google.unlinked", request, user_id=current_user.id)
    return {"message": "Google disconnected"}
