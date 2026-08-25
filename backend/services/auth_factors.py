"""User authentication factor helpers."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models import User, WebAuthnCredential, RecoveryCodeHash
from services.auth_service import verify_password
from services.webauthn_service import finish_step_up


def passkey_count(db: Session, user_id: str) -> int:
    return db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user_id).count()


def unused_recovery_count(db: Session, user_id: str) -> int:
    return (
        db.query(RecoveryCodeHash)
        .filter(RecoveryCodeHash.user_id == user_id, RecoveryCodeHash.used_at.is_(None))
        .count()
    )


def get_user_factors(db: Session, user: User) -> dict:
    return {
        "password": user.password_hash is not None,
        "passkey_count": passkey_count(db, user.id),
        "google": user.google_sub is not None,
        "recovery_codes_remaining": unused_recovery_count(db, user.id),
    }


def count_login_factors(db: Session, user: User) -> int:
    n = 0
    if user.google_sub:
        n += 1
    n += passkey_count(db, user.id)
    if unused_recovery_count(db, user.id) > 0:
        n += 1
    return n


def can_remove_passkey(db: Session, user: User) -> bool:
    """False if deleting the last passkey would leave no remaining login method.

    Password hashes are step-up only — they do not count as a sign-in method.
    """
    if passkey_count(db, user.id) <= 1:
        return user.google_sub is not None
    return True


def can_unlink_google(db: Session, user: User) -> bool:
    """False if Google is not linked, or unlinking would leave no remaining login method."""
    if user.google_sub is None:
        return False
    return passkey_count(db, user.id) > 0


def require_step_up(
    db: Session,
    user: User,
    *,
    password: str | None = None,
    challenge_id: str | None = None,
    credential: dict | None = None,
) -> None:
    if challenge_id and credential:
        finish_step_up(db, challenge_id, credential, user)
        return
    if password and user.password_hash:
        if verify_password(password, user.password_hash):
            return
        raise HTTPException(status_code=401, detail="Invalid credentials")
    raise HTTPException(status_code=403, detail="Step-up required")
