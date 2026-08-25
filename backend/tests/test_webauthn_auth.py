"""WebAuthn auth route tests (mocked verification)."""

import base64
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from webauthn.helpers import bytes_to_base64url

from main import app
from database import engine, Base, SessionLocal
from models import User, WebAuthnCredential
from services.auth_service import hash_password

client = TestClient(app)
VALID_PASS = "SecureP@ss123!"


def _password_user(email: str) -> None:
    db = SessionLocal()
    db.add(
        User(
            id=str(uuid.uuid4()),
            email=email.lower(),
            password_hash=hash_password(VALID_PASS),
        )
    )
    db.commit()
    db.close()


def _mock_registration_verification():
    cred_id = b"test-credential-id-bytes"
    mock = MagicMock()
    mock.credential_id = cred_id
    mock.credential_public_key = b"public-key-bytes"
    mock.sign_count = 0
    mock.aaguid = None
    return mock


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


class TestWebAuthnRegister:
    def test_challenge_single_use(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        begin = client.post("/api/auth/webauthn/register/begin", json={"email": email})
        assert begin.status_code == 200
        challenge_id = begin.json()["challengeId"]

        with patch(
            "services.webauthn_service.verify_registration_response",
            return_value=_mock_registration_verification(),
        ):
            cred = {
                "id": bytes_to_base64url(b"test-credential-id-bytes"),
                "rawId": bytes_to_base64url(b"test-credential-id-bytes"),
                "type": "public-key",
                "response": {
                    "clientDataJSON": base64.b64encode(b"{}").decode(),
                    "attestationObject": base64.b64encode(b"att").decode(),
                },
            }
            finish = client.post(
                "/api/auth/webauthn/register/finish",
                json={"challenge_id": challenge_id, "credential": cred},
            )
            assert finish.status_code == 200
            assert "access_token" in finish.json()
            assert len(finish.json().get("recovery_codes", [])) == 10

            retry = client.post(
                "/api/auth/webauthn/register/finish",
                json={"challenge_id": challenge_id, "credential": cred},
            )
            assert retry.status_code == 400

    def test_finish_creates_credential_row(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        begin = client.post("/api/auth/webauthn/register/begin", json={"email": email})
        challenge_id = begin.json()["challengeId"]

        with patch(
            "services.webauthn_service.verify_registration_response",
            return_value=_mock_registration_verification(),
        ):
            cred = {
                "id": bytes_to_base64url(b"test-credential-id-bytes"),
                "rawId": bytes_to_base64url(b"test-credential-id-bytes"),
                "type": "public-key",
                "response": {
                    "clientDataJSON": base64.b64encode(b"{}").decode(),
                    "attestationObject": base64.b64encode(b"att").decode(),
                },
            }
            client.post(
                "/api/auth/webauthn/register/finish",
                json={"challenge_id": challenge_id, "credential": cred},
            )

        db = SessionLocal()
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None
        assert user.password_hash is None
        assert db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).count() == 1
        db.close()


class TestWebAuthnAssert:
    def _seed_user_with_cred(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        user_id = str(uuid.uuid4())
        cred_id = bytes_to_base64url(b"assert-cred-id")
        db = SessionLocal()
        db.add(
            User(id=user_id, email=email, password_hash=None)
        )
        db.add(
            WebAuthnCredential(
                user_id=user_id,
                credential_id=cred_id,
                public_key=base64.b64encode(b"public-key-bytes").decode(),
                sign_count=1,
            )
        )
        db.commit()
        db.close()
        return email, cred_id, user_id

    def test_assert_login_sets_refresh_cookie(self):
        email, cred_id, _ = self._seed_user_with_cred()
        begin = client.post("/api/auth/webauthn/assert/begin", json={"email": email})
        challenge_id = begin.json()["challengeId"]

        mock_result = MagicMock()
        mock_result.new_sign_count = 2

        with patch(
            "services.webauthn_service.verify_authentication_response",
            return_value=mock_result,
        ):
            finish = client.post(
                "/api/auth/webauthn/assert/finish",
                json={
                    "challenge_id": challenge_id,
                    "credential": {
                        "id": cred_id,
                        "rawId": cred_id,
                        "type": "public-key",
                        "response": {
                            "clientDataJSON": base64.b64encode(b"{}").decode(),
                            "authenticatorData": base64.b64encode(b"auth").decode(),
                            "signature": base64.b64encode(b"sig").decode(),
                        },
                    },
                },
            )
        assert finish.status_code == 200
        assert "access_token" in finish.json()
        assert "vs_refresh" in finish.cookies

    def test_sign_count_rollback_rejected(self):
        email, cred_id, user_id = self._seed_user_with_cred()
        begin = client.post("/api/auth/webauthn/assert/begin", json={"email": email})
        challenge_id = begin.json()["challengeId"]

        mock_result = MagicMock()
        mock_result.new_sign_count = 0

        with patch(
            "services.webauthn_service.verify_authentication_response",
            return_value=mock_result,
        ):
            finish = client.post(
                "/api/auth/webauthn/assert/finish",
                json={
                    "challenge_id": challenge_id,
                    "credential": {
                        "id": cred_id,
                        "rawId": cred_id,
                        "type": "public-key",
                        "response": {
                            "clientDataJSON": base64.b64encode(b"{}").decode(),
                            "authenticatorData": base64.b64encode(b"auth").decode(),
                            "signature": base64.b64encode(b"sig").decode(),
                        },
                    },
                },
            )
        assert finish.status_code == 401
