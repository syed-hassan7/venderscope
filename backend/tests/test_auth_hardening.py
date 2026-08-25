"""Auth hardening: closed password login, Google link step-up, session family, origin."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from database import engine, Base, SessionLocal
from models import User
from services.auth_service import (
    create_access_token,
    create_refresh_token,
    hash_password,
)

client = TestClient(app)
VALID_PASS = "SecureP@ss123!"
ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    client.cookies.clear()
    yield


def _password_user() -> User:
    db = SessionLocal()
    user = User(
        id=str(uuid.uuid4()),
        email=f"hd_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password(VALID_PASS),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.expunge(user)
    db.close()
    return user


def _bearer(user: User) -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(user.id)}",
        **ORIGIN,
    }


class TestPasswordLoginClosed:
    def test_login_always_403(self):
        user = _password_user()
        resp = client.post(
            "/api/auth/login",
            json={"email": user.email, "password": VALID_PASS},
        )
        assert resp.status_code == 403
        assert "closed" in resp.json()["detail"].lower()


class TestGoogleLinkStart:
    def test_get_link_start_is_405(self):
        resp = client.get("/api/auth/google/link/start", follow_redirects=False)
        assert resp.status_code == 405

    def test_post_without_bearer_is_401(self):
        user = _password_user()
        token = create_refresh_token(user.id)
        client.cookies.set("vs_refresh", token)
        resp = client.post(
            "/api/auth/google/link/start",
            json={"password": VALID_PASS},
            headers=ORIGIN,
        )
        assert resp.status_code == 401

    def test_post_without_origin_is_403(self):
        user = _password_user()
        resp = client.post(
            "/api/auth/google/link/start",
            json={"password": VALID_PASS},
            headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
        )
        assert resp.status_code == 403

    def test_post_without_step_up_is_403(self):
        user = _password_user()
        resp = client.post(
            "/api/auth/google/link/start",
            json={},
            headers=_bearer(user),
        )
        assert resp.status_code == 403

    def test_post_with_password_returns_authorize_url(self):
        user = _password_user()
        with patch(
            "routers.auth.build_authorize_url",
            return_value="https://accounts.google.com/o/oauth2/v2/auth?mock=1",
        ):
            resp = client.post(
                "/api/auth/google/link/start",
                json={"password": VALID_PASS},
                headers=_bearer(user),
            )
        assert resp.status_code == 200
        assert resp.json()["url"].startswith("https://accounts.google.com/")


class TestAddPasskeyStepUp:
    def test_logged_in_begin_without_step_up_is_403(self):
        user = _password_user()
        resp = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": user.email},
            headers=_bearer(user),
        )
        assert resp.status_code == 403
        assert "step-up" in resp.json()["detail"].lower()

    def test_logged_in_begin_with_password_is_200(self):
        user = _password_user()
        resp = client.post(
            "/api/auth/webauthn/register/begin",
            json={"email": user.email, "password": VALID_PASS},
            headers=_bearer(user),
        )
        assert resp.status_code == 200
        assert "challengeId" in resp.json()


class TestRefreshFamily:
    def test_refresh_without_origin_is_403(self):
        user = _password_user()
        token = create_refresh_token(user.id)
        client.cookies.set("vs_refresh", token)
        resp = client.post("/api/auth/refresh")
        assert resp.status_code == 403

    def test_revoked_refresh_reuse_kills_family(self):
        user = _password_user()
        t1 = create_refresh_token(user.id)
        client.cookies.set("vs_refresh", t1)
        first = client.post("/api/auth/refresh", headers=ORIGIN)
        assert first.status_code == 200
        t2 = first.cookies.get("vs_refresh")
        assert t2

        client.cookies.set("vs_refresh", t1)
        replay = client.post("/api/auth/refresh", headers=ORIGIN)
        assert replay.status_code == 401

        client.cookies.set("vs_refresh", t2)
        after = client.post("/api/auth/refresh", headers=ORIGIN)
        assert after.status_code == 401

    def test_logout_invalidates_access_token(self):
        user = _password_user()
        access = create_access_token(user.id)
        refresh = create_refresh_token(user.id)
        client.cookies.set("vs_refresh", refresh)
        headers = {"Authorization": f"Bearer {access}", **ORIGIN}
        assert client.get("/api/auth/me", headers=headers).status_code == 200
        assert client.post("/api/auth/logout", headers=ORIGIN).status_code == 200
        assert client.get("/api/auth/me", headers=headers).status_code == 401
