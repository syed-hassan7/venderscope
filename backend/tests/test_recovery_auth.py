"""Recovery code login tests."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from database import engine, Base, SessionLocal
from models import User, RecoveryCodeHash
from services.auth_service import hash_password
from services.recovery_service import generate_plain_codes, hash_recovery_code

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _user_with_codes() -> tuple[str, list[str]]:
    email = f"rc_{uuid.uuid4().hex[:8]}@example.com"
    codes = generate_plain_codes(3)
    user_id = str(uuid.uuid4())
    db = SessionLocal()
    db.add(User(id=user_id, email=email, password_hash=None))
    for code in codes:
        db.add(RecoveryCodeHash(user_id=user_id, code_hash=hash_recovery_code(code)))
    db.commit()
    db.close()
    return email, codes


class TestRecoveryCodes:
    def test_consume_once(self):
        email, codes = _user_with_codes()
        resp = client.post(
            "/api/auth/recovery/consume",
            json={"email": email, "code": codes[0]},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()

        again = client.post(
            "/api/auth/recovery/consume",
            json={"email": email, "code": codes[0]},
        )
        assert again.status_code == 401

    def test_generic_error_wrong_code(self):
        email, _ = _user_with_codes()
        resp = client.post(
            "/api/auth/recovery/consume",
            json={"email": email, "code": "AAAA-BBBB-CCCC-DDDD"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid credentials"

    def test_null_password_user_cannot_password_login(self):
        email, codes = _user_with_codes()
        resp = client.post(
            "/api/auth/login",
            json={"email": email, "password": codes[0]},
        )
        assert resp.status_code == 403

    def test_regenerate_invalidates_old_codes(self):
        from services.auth_service import create_access_token, hash_password

        email = f"regen_{uuid.uuid4().hex[:8]}@example.com"
        old_codes = generate_plain_codes(3)
        user_id = str(uuid.uuid4())
        db = SessionLocal()
        db.add(User(id=user_id, email=email, password_hash=hash_password("SecureP@ss123!")))
        for code in old_codes:
            db.add(RecoveryCodeHash(user_id=user_id, code_hash=hash_recovery_code(code)))
        db.commit()
        db.close()

        token = create_access_token(user_id)
        with patch("routers.auth.finish_step_up"):
            regen = client.post(
                "/api/auth/recovery/regenerate",
                headers={"Authorization": f"Bearer {token}"},
                json={"challenge_id": "cid", "credential": {"id": "x"}},
            )
        assert regen.status_code == 200
        new_codes = regen.json()["recovery_codes"]
        assert len(new_codes) == 10

        old = client.post(
            "/api/auth/recovery/consume",
            json={"email": email, "code": old_codes[0]},
        )
        assert old.status_code == 401

        fresh = client.post(
            "/api/auth/recovery/consume",
            json={"email": email, "code": new_codes[0]},
        )
        assert fresh.status_code == 200
