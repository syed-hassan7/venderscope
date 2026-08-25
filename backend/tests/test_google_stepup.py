"""Google-reauth step-up: closes the Google-only-account takeover chain.

Adding a first passkey to a Google-only account (0 passkeys, no password) or
unlinking Google can't use the existing password/WebAuthn step-up primitives —
a Google-only account has neither. This proves current control of the same
Google account already on file via a fresh OAuth round trip instead.
"""

import base64
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

import jwt
import pytest
from fastapi.testclient import TestClient
from webauthn.helpers import bytes_to_base64url

from main import app
from database import engine, Base, SessionLocal
from models import User, OAuthState
from services.auth_service import ALGORITHM, JWT_SECRET, create_access_token
from services.google_oauth_service import (
    mint_google_stepup_token,
    read_google_stepup_token,
)

client = TestClient(app)
ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client.cookies.clear()
    yield


def _headers(user_id: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _google_only_user(google_sub: str | None = None) -> User:
    google_sub = google_sub or "gsub-" + uuid.uuid4().hex
    db = SessionLocal()
    user = User(
        id=str(uuid.uuid4()),
        email=f"gonly_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=None,
        google_sub=google_sub,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


def _seed_oauth_state(purpose: str, user_id: str | None) -> tuple[str, str]:
    state = "state-" + uuid.uuid4().hex
    db = SessionLocal()
    db.add(
        OAuthState(
            state=state,
            code_verifier="verifier-" + uuid.uuid4().hex,
            nonce="nonce-" + uuid.uuid4().hex[:8],
            purpose=purpose,
            user_id=user_id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
        )
    )
    db.commit()
    nonce = db.query(OAuthState).filter(OAuthState.state == state).first().nonce
    db.close()
    return state, nonce


def _google_callback(*, sub: str, email: str, state: str, nonce: str):
    with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "secret"}):
        with patch(
            "services.google_oauth_service.httpx.post",
            return_value=MagicMock(raise_for_status=lambda: None, json=lambda: {"id_token": "token"}),
        ):
            with patch("services.google_oauth_service.PyJWKClient") as mock_jwk:
                mock_jwk.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="key")
                with patch(
                    "services.google_oauth_service.jwt.decode",
                    return_value={"sub": sub, "email": email, "email_verified": True, "nonce": nonce},
                ):
                    return client.get(
                        f"/api/auth/google/callback?code=abc&state={state}",
                        follow_redirects=False,
                    )


class TestStepupToken:
    def test_mint_read_roundtrip(self):
        token = mint_google_stepup_token(user_id="user-123")
        assert read_google_stepup_token(token) == "user-123"

        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        assert payload["type"] == "google_stepup"
        assert payload["user_id"] == "user-123"

    def test_read_missing_garbage_expired_wrong_type_are_none(self):
        assert read_google_stepup_token(None) is None
        assert read_google_stepup_token("") is None
        assert read_google_stepup_token("not-a-jwt") is None

        expired = jwt.encode(
            {
                "type": "google_stepup",
                "user_id": "user-123",
                "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            },
            JWT_SECRET,
            algorithm=ALGORITHM,
        )
        assert read_google_stepup_token(expired) is None

        wrong_type = jwt.encode(
            {
                "type": "access",
                "user_id": "user-123",
                "exp": datetime.now(timezone.utc) + timedelta(minutes=15),
            },
            JWT_SECRET,
            algorithm=ALGORITHM,
        )
        assert read_google_stepup_token(wrong_type) is None


class TestReauthStart:
    def test_requires_existing_google_link(self):
        db = SessionLocal()
        user = User(id=str(uuid.uuid4()), email=f"nopass_{uuid.uuid4().hex[:6]}@example.com", password_hash=None)
        db.add(user)
        db.commit()
        uid = user.id
        db.close()

        with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "secret"}):
            resp = client.post("/api/auth/google/reauth/start", headers={**_headers(uid), **ORIGIN})
        assert resp.status_code == 400

    def test_returns_authorize_url_for_google_only_account(self):
        user = _google_only_user()
        with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "secret"}):
            resp = client.post("/api/auth/google/reauth/start", headers={**_headers(user.id), **ORIGIN})
        assert resp.status_code == 200
        assert "accounts.google.com" in resp.json()["url"]

        db = SessionLocal()
        row = db.query(OAuthState).filter(OAuthState.purpose == "step_up").first()
        assert row is not None
        assert row.user_id == user.id
        db.close()

    def test_unauthenticated_returns_401(self):
        resp = client.post("/api/auth/google/reauth/start", headers=ORIGIN)
        assert resp.status_code == 401


class TestCallbackStepupPurpose:
    def test_matching_sub_sets_cookie_and_redirects(self):
        user = _google_only_user()
        state, nonce = _seed_oauth_state("step_up", user.id)
        resp = _google_callback(sub=user.google_sub, email=user.email, state=state, nonce=nonce)
        assert resp.status_code in (302, 307)
        assert "stepup=1" in resp.headers.get("location", "")
        token = resp.cookies.get("vs_google_stepup")
        assert token
        assert read_google_stepup_token(token) == user.id

    def test_mismatched_sub_does_not_set_cookie(self):
        user = _google_only_user()
        state, nonce = _seed_oauth_state("step_up", user.id)
        other_sub = "gsub-" + uuid.uuid4().hex
        resp = _google_callback(sub=other_sub, email=user.email, state=state, nonce=nonce)
        assert resp.status_code in (302, 307)
        assert not resp.cookies.get("vs_google_stepup")


class TestAddPasskeyRequiresStepupOnGoogleOnly:
    def test_begin_without_stepup_cookie_is_403(self):
        user = _google_only_user()
        resp = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": user.email},
            headers={**_headers(user.id), **ORIGIN},
        )
        assert resp.status_code == 403

    def test_begin_with_valid_stepup_cookie_succeeds(self):
        user = _google_only_user()
        client.cookies.set("vs_google_stepup", mint_google_stepup_token(user_id=user.id))
        resp = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": user.email},
            headers={**_headers(user.id), **ORIGIN},
        )
        assert resp.status_code == 200

    def test_begin_with_stepup_cookie_for_a_different_user_is_403(self):
        user = _google_only_user()
        other = _google_only_user()
        client.cookies.set("vs_google_stepup", mint_google_stepup_token(user_id=other.id))
        resp = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": user.email},
            headers={**_headers(user.id), **ORIGIN},
        )
        assert resp.status_code == 403

    def test_finish_success_clears_stepup_cookie(self):
        user = _google_only_user()
        client.cookies.set("vs_google_stepup", mint_google_stepup_token(user_id=user.id))
        begin = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": user.email},
            headers={**_headers(user.id), **ORIGIN},
        )
        assert begin.status_code == 200
        challenge_id = begin.json()["challengeId"]

        cred_id = bytes_to_base64url(b"stepup-cred-bytes")
        mock = MagicMock()
        mock.credential_id = b"stepup-cred-bytes"
        mock.credential_public_key = b"public-key-bytes"
        mock.sign_count = 0
        mock.aaguid = None
        with patch("services.webauthn_service.verify_registration_response", return_value=mock):
            finish = client.post(
                "/api/auth/webauthn/register/finish",
                json={
                    "challenge_id": challenge_id,
                    "credential": {
                        "id": cred_id,
                        "rawId": cred_id,
                        "type": "public-key",
                        "response": {
                            "clientDataJSON": base64.b64encode(b"{}").decode(),
                            "attestationObject": base64.b64encode(b"att").decode(),
                        },
                    },
                },
                headers={**_headers(user.id), **ORIGIN},
            )
        assert finish.status_code == 200
        assert not finish.cookies.get("vs_google_stepup")
