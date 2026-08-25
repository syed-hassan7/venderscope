"""Google OAuth auth tests (mocked token exchange + JWT)."""

import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from database import engine, Base, SessionLocal
from models import User, OAuthState
from services.auth_service import hash_password

client = TestClient(app)
VALID_PASS = "SecureP@ss123!"


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
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
