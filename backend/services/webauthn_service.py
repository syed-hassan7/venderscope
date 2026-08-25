"""WebAuthn / passkey registration and authentication."""

import base64
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
    options_to_json,
)
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from config import get_frontend_origins, get_primary_frontend_url
from models import User, WebAuthnChallenge, WebAuthnCredential, RecoveryCodeHash

CHALLENGE_TTL_MINUTES = 5


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _rp_id() -> str:
    explicit = os.getenv("WEBAUTHN_RP_ID", "").strip()
    if explicit:
        return explicit
    primary = get_primary_frontend_url()
    if "localhost" in primary:
        return "localhost"
    from urllib.parse import urlparse
    return urlparse(primary).hostname or "localhost"


def _rp_name() -> str:
    return os.getenv("WEBAUTHN_RP_NAME", "VenderScope")


def _expected_origins() -> list[str]:
    return list(get_frontend_origins())


def _challenge_expiry() -> datetime:
    return _utc_now() + timedelta(minutes=CHALLENGE_TTL_MINUTES)


def _options_payload(options, challenge_id: str, **extra) -> dict:
    payload = json.loads(options_to_json(options))
    payload["challengeId"] = challenge_id
    payload.update(extra)
    return payload


def _store_challenge(
    db: Session,
    challenge_bytes: bytes,
    purpose: str,
    user_id: str | None = None,
    email: str | None = None,
) -> str:
    row = WebAuthnChallenge(
        id=str(uuid.uuid4()),
        user_id=user_id,
        email=email.lower() if email else None,
        challenge=bytes_to_base64url(challenge_bytes),
        purpose=purpose,
        expires_at=_challenge_expiry(),
    )
    db.add(row)
    db.commit()
    return row.id


def _consume_challenge(db: Session, challenge_id: str, purpose: str) -> WebAuthnChallenge:
    row = db.query(WebAuthnChallenge).filter(WebAuthnChallenge.id == challenge_id).first()
    if not row or row.purpose != purpose:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    if row.used_at is not None:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    if _as_utc(row.expires_at) < _utc_now():
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    row.used_at = _utc_now()
    db.commit()
    return row


def begin_registration(
    db: Session,
    email: str,
    user: User | None = None,
    for_signup: bool = False,
) -> dict:
    email_lower = email.lower().strip()
    if for_signup:
        existing = db.query(User).filter(User.email == email_lower).first()
        if existing and db.query(WebAuthnCredential).filter(
            WebAuthnCredential.user_id == existing.id
        ).first():
            raise HTTPException(status_code=409, detail="An account with this email already exists.")
        if not existing:
            user = User(id=str(uuid.uuid4()), email=email_lower, password_hash=None)
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            user = existing
    elif user is None:
        raise HTTPException(status_code=400, detail="User required")

    exclude: list[PublicKeyCredentialDescriptor] = []
    for cred in db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id):
        exclude.append(
            PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id))
        )

    options = generate_registration_options(
        rp_id=_rp_id(),
        rp_name=_rp_name(),
        user_name=user.email,
        user_id=user.id.encode("utf-8"),
        exclude_credentials=exclude,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    challenge_id = _store_challenge(
        db,
        options.challenge,
        "register",
        user_id=user.id,
        email=user.email if for_signup else None,
    )
    return _options_payload(options, challenge_id, userId=user.id)


def finish_registration(
    db: Session,
    challenge_id: str,
    credential: dict,
    device_label: str | None = None,
    issue_recovery_codes: bool = False,
) -> tuple[User, list[str] | None]:
    row = _consume_challenge(db, challenge_id, "register")
    if not row.user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")
    user = db.query(User).filter(User.id == row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired challenge")

    verification = verify_registration_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(row.challenge),
        expected_rp_id=_rp_id(),
        expected_origin=_expected_origins(),
        require_user_verification=True,
    )

    cred_id = bytes_to_base64url(verification.credential_id)
    if db.query(WebAuthnCredential).filter(WebAuthnCredential.credential_id == cred_id).first():
        raise HTTPException(status_code=409, detail="Credential already registered")

    transports = credential.get("response", {}).get("transports")
    transport_str = ",".join(transports) if transports else None

    db.add(
        WebAuthnCredential(
            user_id=user.id,
            credential_id=cred_id,
            public_key=base64.b64encode(verification.credential_public_key).decode("ascii"),
            sign_count=verification.sign_count,
            aaguid=str(verification.aaguid) if verification.aaguid else None,
            transports=transport_str,
            device_label=device_label,
        )
    )
    db.commit()

    recovery_plain: list[str] | None = None
    if issue_recovery_codes:
        existing_codes = db.query(RecoveryCodeHash).filter(
            RecoveryCodeHash.user_id == user.id
        ).count()
        if existing_codes == 0:
            from services.recovery_service import generate_plain_codes, store_recovery_codes

            recovery_plain = generate_plain_codes()
            store_recovery_codes(db, user.id, recovery_plain)

    return user, recovery_plain


def begin_assertion(db: Session, email: str | None = None) -> dict:
    allow: list[PublicKeyCredentialDescriptor] = []
    user_id: str | None = None

    if email:
        user = db.query(User).filter(User.email == email.lower().strip()).first()
        if user:
            user_id = user.id
            for cred in db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id):
                allow.append(
                    PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id))
                )

    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge_id = _store_challenge(
        db,
        options.challenge,
        "assert",
        user_id=user_id,
        email=email.lower().strip() if email else None,
    )
    return _options_payload(options, challenge_id)


def finish_assertion(db: Session, challenge_id: str, credential: dict) -> User:
    row = _consume_challenge(db, challenge_id, "assert")
    return _verify_assertion_with_row(db, row, credential)


def _verify_assertion_with_row(db: Session, row: WebAuthnChallenge, credential: dict) -> User:
    raw_id = credential.get("rawId") or credential.get("id")
    if not raw_id:
        raise HTTPException(status_code=400, detail="Invalid credential")

    cred_id = raw_id if isinstance(raw_id, str) else bytes_to_base64url(raw_id)
    stored = db.query(WebAuthnCredential).filter(WebAuthnCredential.credential_id == cred_id).first()
    if not stored:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    public_key = base64.b64decode(stored.public_key)

    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=base64url_to_bytes(row.challenge),
        expected_rp_id=_rp_id(),
        expected_origin=_expected_origins(),
        credential_public_key=public_key,
        credential_current_sign_count=stored.sign_count,
        require_user_verification=True,
    )

    if verification.new_sign_count <= stored.sign_count:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    stored.sign_count = verification.new_sign_count
    stored.last_used_at = datetime.now(timezone.utc)
    db.commit()

    user = db.query(User).filter(User.id == stored.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user


def begin_step_up(db: Session, user: User) -> dict:
    allow: list[PublicKeyCredentialDescriptor] = []
    for cred in db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id):
        allow.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id)))

    if not allow:
        raise HTTPException(status_code=400, detail="No passkey registered")

    options = generate_authentication_options(
        rp_id=_rp_id(),
        allow_credentials=allow,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge_id = _store_challenge(db, options.challenge, "step_up", user_id=user.id)
    return _options_payload(options, challenge_id)


def finish_step_up(db: Session, challenge_id: str, credential: dict, user: User) -> None:
    row = _consume_challenge(db, challenge_id, "step_up")
    if row.user_id != user.id:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _verify_assertion_with_row(db, row, credential)
