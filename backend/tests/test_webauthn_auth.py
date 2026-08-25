"""WebAuthn auth route tests (mocked verification)."""

import base64
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.exceptions import InvalidAuthenticationResponse

from main import app
from database import engine, Base, SessionLocal
from models import User, WebAuthnCredential
from services.auth_service import hash_password, create_access_token
from services.google_oauth_service import mint_google_pending_token

client = TestClient(app)
VALID_PASS = "SecureP@ss123!"
ORIGIN = {"Origin": "http://localhost:5173"}


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
    client.cookies.clear()
    yield


def _attach_pending(email: str, sub: str | None = None) -> str:
    sub = sub or "gs-" + uuid.uuid4().hex
    token = mint_google_pending_token(sub=sub, email=email)
    client.cookies.set("vs_google_pending", token)
    return sub


class TestWebAuthnRegister:
    def test_signup_begin_without_pending_is_403(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        begin = client.post("/api/auth/webauthn/register/begin", json={"email": email})
        assert begin.status_code == 403
        assert begin.json()["detail"] == "Start with Google to create an account"

    def test_challenge_single_use(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        _attach_pending(email)
        begin = client.post("/api/auth/webauthn/register/begin", json={"email": "ignored@example.com"}, headers=ORIGIN)
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
                headers=ORIGIN,
            )
            assert finish.status_code == 200
            assert "access_token" in finish.json()
            assert len(finish.json().get("recovery_codes", [])) == 10

            retry = client.post(
                "/api/auth/webauthn/register/finish",
                json={"challenge_id": challenge_id, "credential": cred},
                headers=ORIGIN,
            )
            assert retry.status_code == 400

    def test_begin_does_not_insert_user(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        _attach_pending(email)
        begin = client.post("/api/auth/webauthn/register/begin", json={"email": email}, headers=ORIGIN)
        assert begin.status_code == 200
        db = SessionLocal()
        assert db.query(User).filter(User.email == email.lower()).first() is None
        db.close()

    def test_finish_creates_credential_row(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        sub = _attach_pending(email)
        begin = client.post("/api/auth/webauthn/register/begin", json={"email": email}, headers=ORIGIN)
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
                headers=ORIGIN,
            )

        db = SessionLocal()
        user = db.query(User).filter(User.email == email.lower()).first()
        assert user is not None
        assert user.password_hash is None
        assert user.google_sub == sub
        assert db.query(WebAuthnCredential).filter(WebAuthnCredential.user_id == user.id).count() == 1
        db.close()

    def test_logged_in_add_passkey_does_not_need_pending(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        user_id = str(uuid.uuid4())
        db = SessionLocal()
        db.add(User(id=user_id, email=email, password_hash=hash_password(VALID_PASS)))
        db.commit()
        db.close()
        token = create_access_token(user_id)
        begin = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": email, "password": VALID_PASS},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert begin.status_code == 200

    def test_logged_in_finish_without_bearer_is_401(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        user_id = str(uuid.uuid4())
        db = SessionLocal()
        db.add(User(id=user_id, email=email, password_hash=hash_password(VALID_PASS)))
        db.commit()
        db.close()
        token = create_access_token(user_id)
        begin = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": email, "password": VALID_PASS},
            headers={"Authorization": f"Bearer {token}"},
        )
        challenge_id = begin.json()["challengeId"]
        with patch(
            "services.webauthn_service.verify_registration_response",
            return_value=_mock_registration_verification(),
        ):
            finish = client.post(
                "/api/auth/webauthn/register/finish",
                json={
                    "challenge_id": challenge_id,
                    "credential": {
                        "id": bytes_to_base64url(b"test-credential-id-bytes"),
                        "rawId": bytes_to_base64url(b"test-credential-id-bytes"),
                        "type": "public-key",
                        "response": {
                            "clientDataJSON": base64.b64encode(b"{}").decode(),
                            "attestationObject": base64.b64encode(b"att").decode(),
                        },
                    },
                },
            )
        assert finish.status_code == 401

    def test_failed_verify_does_not_insert_user(self):
        email = f"wk_{uuid.uuid4().hex[:8]}@example.com"
        _attach_pending(email)
        begin = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": email},
            headers=ORIGIN,
        )
        challenge_id = begin.json()["challengeId"]
        with patch(
            "services.webauthn_service.verify_registration_response",
            side_effect=ValueError("bad attestation"),
        ):
            finish = client.post(
                "/api/auth/webauthn/register/finish",
                json={
                    "challenge_id": challenge_id,
                    "credential": {
                        "id": bytes_to_base64url(b"test-credential-id-bytes"),
                        "rawId": bytes_to_base64url(b"test-credential-id-bytes"),
                        "type": "public-key",
                        "response": {
                            "clientDataJSON": base64.b64encode(b"{}").decode(),
                            "attestationObject": base64.b64encode(b"att").decode(),
                        },
                    },
                },
                headers=ORIGIN,
            )
        assert finish.status_code == 400
        db = SessionLocal()
        assert db.query(User).filter(User.email == email.lower()).first() is None
        db.close()
    def _seed_user_with_cred(self, sign_count=1):
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
                sign_count=sign_count,
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

    def test_sign_count_zero_zero_login_succeeds(self):
        """Synced/platform passkeys (Google Password Manager, iCloud Keychain, Windows
        Hello resident keys) commonly always report sign_count=0. The library's own
        verify_authentication_response already exempts 0-vs-0 from clone detection —
        our app must not re-reject it with a stricter redundant check."""
        email, cred_id, user_id = self._seed_user_with_cred(sign_count=0)
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
        assert finish.status_code == 200
        assert "access_token" in finish.json()

    def test_sign_count_rollback_rejected(self):
        """A genuine clone/replay makes the real library raise InvalidAuthenticationResponse
        — the endpoint must translate that to a clean 401, not let it 500."""
        email, cred_id, user_id = self._seed_user_with_cred(sign_count=5)
        begin = client.post("/api/auth/webauthn/assert/begin", json={"email": email})
        challenge_id = begin.json()["challengeId"]

        with patch(
            "services.webauthn_service.verify_authentication_response",
            side_effect=InvalidAuthenticationResponse("sign count did not increase"),
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
