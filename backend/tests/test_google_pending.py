"""Google pending-signup JWT + passkey bind tests."""

import base64
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt
import pytest
from fastapi import HTTPException
from webauthn.helpers import bytes_to_base64url

from database import Base, SessionLocal, engine
from models import User, WebAuthnCredential
from services.auth_service import ALGORITHM, JWT_SECRET
from services.google_oauth_service import mint_google_pending_token, read_google_pending_token
from services.webauthn_service import begin_registration, finish_registration


def _mock_registration_verification(cred_id: bytes = b"test-credential-id-bytes"):
    from unittest.mock import MagicMock

    mock = MagicMock()
    mock.credential_id = cred_id
    mock.credential_public_key = b"public-key-bytes"
    mock.sign_count = 0
    mock.aaguid = None
    return mock


def _credential(cred_id: bytes = b"test-credential-id-bytes") -> dict:
    encoded = bytes_to_base64url(cred_id)
    return {
        "id": encoded,
        "rawId": encoded,
        "type": "public-key",
        "response": {
            "clientDataJSON": base64.b64encode(b"{}").decode(),
            "attestationObject": base64.b64encode(b"att").decode(),
        },
    }


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


class TestGooglePendingToken:
    def test_mint_read_roundtrip_lowercases_email(self):
        token = mint_google_pending_token(sub="GoogleSub123", email="Mix.Case@Example.COM")
        got = read_google_pending_token(token)
        assert got == {"google_sub": "GoogleSub123", "email": "mix.case@example.com"}

        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        assert payload["type"] == "google_pending"
        assert payload["google_sub"] == "GoogleSub123"
        assert payload["email"] == "mix.case@example.com"
        assert payload.get("sub") != "GoogleSub123"

    def test_read_missing_garbage_expired_wrong_type_are_none(self):
        assert read_google_pending_token(None) is None
        assert read_google_pending_token("") is None
        assert read_google_pending_token("not-a-jwt") is None

        expired = jwt.encode(
            {
                "type": "google_pending",
                "google_sub": "gs-expired",
                "email": "gone@example.com",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            JWT_SECRET,
            algorithm=ALGORITHM,
        )
        assert read_google_pending_token(expired) is None

        wrong_type = jwt.encode(
            {
                "type": "access",
                "google_sub": "gs-wrong",
                "email": "a@example.com",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            JWT_SECRET,
            algorithm=ALGORITHM,
        )
        assert read_google_pending_token(wrong_type) is None


class TestFinishRegistrationGoogleBind:
    def test_finish_with_google_sub_binds(self):
        email = f"gp_{uuid.uuid4().hex[:8]}@example.com"
        google_sub = "gs-" + uuid.uuid4().hex
        db = SessionLocal()
        try:
            options = begin_registration(db, email, for_signup=True)
            with patch(
                "services.webauthn_service.verify_registration_response",
                return_value=_mock_registration_verification(),
            ):
                user, _ = finish_registration(
                    db,
                    options["challengeId"],
                    _credential(),
                    google_sub=google_sub,
                )
            db.refresh(user)
            assert user.google_sub == google_sub
            assert user.email == email.lower()
            assert db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).count() == 1
        finally:
            db.close()

    def test_occupied_google_sub_conflict(self):
        occupied_sub = "gs-taken-" + uuid.uuid4().hex
        db = SessionLocal()
        try:
            db.add(
                User(
                    id=str(uuid.uuid4()),
                    email=f"owner_{uuid.uuid4().hex[:8]}@example.com",
                    password_hash=None,
                    google_sub=occupied_sub,
                )
            )
            db.commit()

            email = f"gp_{uuid.uuid4().hex[:8]}@example.com"
            options = begin_registration(db, email, for_signup=True)
            with patch(
                "services.webauthn_service.verify_registration_response",
                return_value=_mock_registration_verification(),
            ):
                with pytest.raises(HTTPException) as exc:
                    finish_registration(
                        db,
                        options["challengeId"],
                        _credential(),
                        google_sub=occupied_sub,
                    )
            assert exc.value.status_code == 409
            assert exc.value.detail == "Google account already linked to another user"
            created = db.query(User).filter(User.email == email.lower()).first()
            assert created is None
        finally:
            db.close()

    def test_verify_failure_does_not_insert_user(self):
        email = f"gp_{uuid.uuid4().hex[:8]}@example.com"
        db = SessionLocal()
        try:
            options = begin_registration(db, email, for_signup=True)
            with patch(
                "services.webauthn_service.verify_registration_response",
                side_effect=ValueError("bad attestation"),
            ):
                with pytest.raises(HTTPException) as exc:
                    finish_registration(
                        db,
                        options["challengeId"],
                        _credential(),
                        google_sub="gs-" + uuid.uuid4().hex,
                    )
            assert exc.value.status_code == 400
            assert db.query(User).filter(User.email == email.lower()).first() is None
        finally:
            db.close()

    def test_incomplete_user_retry_binds_google_sub(self):
        email = f"gp_{uuid.uuid4().hex[:8]}@example.com"
        google_sub = "gs-" + uuid.uuid4().hex
        db = SessionLocal()
        try:
            db.add(User(id=str(uuid.uuid4()), email=email, password_hash=None))
            db.commit()
            options = begin_registration(db, email, for_signup=True)
            with patch(
                "services.webauthn_service.verify_registration_response",
                return_value=_mock_registration_verification(),
            ):
                user, _ = finish_registration(
                    db,
                    options["challengeId"],
                    _credential(),
                    google_sub=google_sub,
                )
            db.refresh(user)
            assert user.google_sub == google_sub
            assert user.email == email.lower()
        finally:
            db.close()

    def test_finish_without_google_sub_leaves_none(self):
        email = f"gp_{uuid.uuid4().hex[:8]}@example.com"
        db = SessionLocal()
        try:
            options = begin_registration(db, email, for_signup=True)
            with patch(
                "services.webauthn_service.verify_registration_response",
                return_value=_mock_registration_verification(),
            ):
                user, _ = finish_registration(
                    db,
                    options["challengeId"],
                    _credential(),
                )
            db.refresh(user)
            assert user.google_sub is None
        finally:
            db.close()
