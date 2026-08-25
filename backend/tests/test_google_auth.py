"""Google OAuth auth tests (mocked token exchange + JWT)."""

import base64
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from webauthn.helpers import bytes_to_base64url

from main import app
from database import engine, Base, SessionLocal
from models import User, OAuthState
from services.auth_service import hash_password
from services.google_oauth_service import read_google_pending_token

client = TestClient(app)
VALID_PASS = "SecureP@ss123!"
ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client.cookies.clear()
    yield


def _seed_oauth_state(purpose: str = "login", user_id: str | None = None) -> tuple[str, str]:
    state = "state-" + uuid.uuid4().hex
    db = SessionLocal()
    db.add(
        OAuthState(
            state=state,
            code_verifier="verifier-" + uuid.uuid4().hex,
            nonce="nonce-" + uuid.uuid4().hex[:8],
            purpose=purpose,
            user_id=user_id,
            expires_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            + __import__("datetime").timedelta(minutes=10),
        )
    )
    db.commit()
    nonce = db.query(OAuthState).filter(OAuthState.state == state).first().nonce
    db.close()
    return state, nonce


class TestGoogleAuth:
    def test_rejects_unverified_email(self):
        state, nonce = _seed_oauth_state()
        with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "secret"}):
            with patch(
                "services.google_oauth_service.httpx.post",
                return_value=MagicMock(
                    raise_for_status=lambda: None,
                    json=lambda: {"id_token": "token"},
                ),
            ):
                with patch("services.google_oauth_service.PyJWKClient") as mock_jwk:
                    mock_jwk.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="key")
                    with patch(
                        "services.google_oauth_service.jwt.decode",
                        return_value={
                            "sub": "sub1",
                            "email": "new@example.com",
                            "email_verified": False,
                            "nonce": nonce,
                        },
                    ):
                        resp = client.get(
                            f"/api/auth/google/callback?code=abc&state={state}",
                            follow_redirects=False,
                        )
        assert resp.status_code == 400

    def test_rejects_auto_link_existing_password_email(self):
        email = f"existing_{uuid.uuid4().hex[:6]}@example.com"
        db = SessionLocal()
        db.add(
            User(
                id=str(uuid.uuid4()),
                email=email,
                password_hash=hash_password(VALID_PASS),
            )
        )
        db.commit()
        db.close()

        state, nonce = _seed_oauth_state()
        with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "secret"}):
            with patch(
                "services.google_oauth_service.httpx.post",
                return_value=MagicMock(
                    raise_for_status=lambda: None,
                    json=lambda: {"id_token": "token"},
                ),
            ):
                with patch("services.google_oauth_service.PyJWKClient") as mock_jwk:
                    mock_jwk.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="key")
                    with patch(
                        "services.google_oauth_service.jwt.decode",
                        return_value={
                            "sub": "google-sub-new",
                            "email": email,
                            "email_verified": True,
                            "nonce": nonce,
                        },
                    ):
                        resp = client.get(
                            f"/api/auth/google/callback?code=abc&state={state}",
                            follow_redirects=False,
                        )
        assert resp.status_code in (302, 307, 409)
        if resp.status_code == 302:
            assert "google_conflict" in resp.headers.get("location", "")

    def test_login_by_google_sub(self):
        sub = "google-" + uuid.uuid4().hex
        email = f"google_{uuid.uuid4().hex[:6]}@example.com"
        db = SessionLocal()
        db.add(User(id=str(uuid.uuid4()), email=email, password_hash=None, google_sub=sub))
        db.commit()
        db.close()

        state, nonce = _seed_oauth_state()
        with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "secret"}):
            with patch(
                "services.google_oauth_service.httpx.post",
                return_value=MagicMock(
                    raise_for_status=lambda: None,
                    json=lambda: {"id_token": "token"},
                ),
            ):
                with patch("services.google_oauth_service.PyJWKClient") as mock_jwk:
                    mock_jwk.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="key")
                    with patch(
                        "services.google_oauth_service.jwt.decode",
                        return_value={
                            "sub": sub,
                            "email": email,
                            "email_verified": True,
                            "nonce": nonce,
                        },
                    ):
                        resp = client.get(
                            f"/api/auth/google/callback?code=abc&state={state}",
                            follow_redirects=False,
                        )
        assert resp.status_code in (302, 307)
        assert "vs_refresh" in resp.cookies


def _google_callback(email: str, sub: str):
    state, nonce = _seed_oauth_state()
    with patch.dict("os.environ", {"GOOGLE_CLIENT_ID": "test-client", "GOOGLE_CLIENT_SECRET": "secret"}):
        with patch(
            "services.google_oauth_service.httpx.post",
            return_value=MagicMock(
                raise_for_status=lambda: None,
                json=lambda: {"id_token": "token"},
            ),
        ):
            with patch("services.google_oauth_service.PyJWKClient") as mock_jwk:
                mock_jwk.return_value.get_signing_key_from_jwt.return_value = MagicMock(key="key")
                with patch(
                    "services.google_oauth_service.jwt.decode",
                    return_value={
                        "sub": sub,
                        "email": email,
                        "email_verified": True,
                        "nonce": nonce,
                    },
                ):
                    return client.get(
                        f"/api/auth/google/callback?code=abc&state={state}",
                        follow_redirects=False,
                    )


def _mock_registration_verification():
    mock = MagicMock()
    mock.credential_id = b"pending-bind-cred-bytes"
    mock.credential_public_key = b"public-key-bytes"
    mock.sign_count = 0
    mock.aaguid = None
    return mock


def _registration_credential():
    encoded = bytes_to_base64url(b"pending-bind-cred-bytes")
    return {
        "id": encoded,
        "rawId": encoded,
        "type": "public-key",
        "response": {
            "clientDataJSON": base64.b64encode(b"{}").decode(),
            "attestationObject": base64.b64encode(b"att").decode(),
        },
    }


class TestGooglePendingCookie:
    def test_unknown_google_user_sets_pending_cookie(self):
        email = f"newg_{uuid.uuid4().hex[:6]}@example.com"
        sub = "gsub-" + uuid.uuid4().hex
        resp = _google_callback(email, sub)
        assert resp.status_code in (302, 307)
        location = resp.headers.get("location", "")
        assert "/register" in location
        assert "from=google" in location
        token = resp.cookies.get("vs_google_pending")
        assert token
        pending = read_google_pending_token(token)
        assert pending == {"google_sub": sub, "email": email.lower()}
        assert "vs_refresh" not in resp.cookies

    def test_register_finish_binds_google_from_pending_cookie(self):
        email = f"bind_{uuid.uuid4().hex[:6]}@example.com"
        sub = "gsub-" + uuid.uuid4().hex
        cb = _google_callback(email, sub)
        assert cb.cookies.get("vs_google_pending")

        begin = client.post("/api/auth/webauthn/register/begin", json={"email": email}, headers=ORIGIN)
        assert begin.status_code == 200
        challenge_id = begin.json()["challengeId"]

        with patch(
            "services.webauthn_service.verify_registration_response",
            return_value=_mock_registration_verification(),
        ):
            finish = client.post(
                "/api/auth/webauthn/register/finish",
                json={"challenge_id": challenge_id, "credential": _registration_credential()},
                headers=ORIGIN,
            )
        assert finish.status_code == 200
        db = SessionLocal()
        user = db.query(User).filter(User.email == email.lower()).one()
        assert user.google_sub == sub
        db.close()
        assert not finish.cookies.get("vs_google_pending")

    def test_register_finish_does_not_bind_on_email_mismatch(self):
        pending_email = f"alice_{uuid.uuid4().hex[:6]}@example.com"
        other_email = f"bob_{uuid.uuid4().hex[:6]}@example.com"
        sub = "gsub-" + uuid.uuid4().hex
        _google_callback(pending_email, sub)

        begin = client.post("/api/auth/webauthn/register/begin", json={"email": other_email}, headers=ORIGIN)
        assert begin.status_code == 200
        challenge_id = begin.json()["challengeId"]

        with patch(
            "services.webauthn_service.verify_registration_response",
            return_value=_mock_registration_verification(),
        ):
            finish = client.post(
                "/api/auth/webauthn/register/finish",
                json={"challenge_id": challenge_id, "credential": _registration_credential()},
                headers=ORIGIN,
            )
        assert finish.status_code == 200
        db = SessionLocal()
        assert db.query(User).filter(User.email == other_email.lower()).first() is None
        user = db.query(User).filter(User.email == pending_email.lower()).one()
        assert user.google_sub == sub
        db.close()

    def test_signup_finish_without_pending_is_403(self):
        from services.webauthn_service import begin_registration

        email = f"np_{uuid.uuid4().hex[:6]}@example.com"
        db = SessionLocal()
        options = begin_registration(db, email, for_signup=True)
        db.close()
        client.cookies.clear()
        with patch(
            "services.webauthn_service.verify_registration_response",
            return_value=_mock_registration_verification(),
        ):
            finish = client.post(
                "/api/auth/webauthn/register/finish",
                json={
                    "challenge_id": options["challengeId"],
                    "credential": _registration_credential(),
                },
            )
        assert finish.status_code == 403
        db = SessionLocal()
        assert db.query(User).filter(User.email == email.lower()).first() is None
        db.close()
