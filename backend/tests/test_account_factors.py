"""Per-factor management: list/delete passkeys, unlink Google."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from main import app
from database import engine, Base, SessionLocal
from models import User, WebAuthnCredential
from services.auth_service import create_access_token, hash_password
from services.recovery_service import generate_plain_codes, store_recovery_codes

client = TestClient(app)
VALID_PASS = "SecureP@ss123!"


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _headers(user_id: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def _add_user(
    db,
    *,
    password: str | None = VALID_PASS,
    google_sub: str | None = None,
) -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"af_{uuid.uuid4().hex[:8]}@example.com",
        password_hash=hash_password(password) if password else None,
        google_sub=google_sub,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _add_passkey(db, user_id: str, label: str | None = "YubiKey") -> WebAuthnCredential:
    cred = WebAuthnCredential(
        user_id=user_id,
        credential_id="cred-" + uuid.uuid4().hex,
        public_key="dGVzdC1wdWJsaWMta2V5",
        sign_count=0,
        device_label=label,
        last_used_at=None,
    )
    db.add(cred)
    db.commit()
    db.refresh(cred)
    return cred


class TestListWebAuthnCredentials:
    def test_list_returns_only_own_rows_without_secrets(self):
        db = SessionLocal()
        owner = _add_user(db)
        other = _add_user(db)
        own_a = _add_passkey(db, owner.id, "Laptop")
        own_b = _add_passkey(db, owner.id, "Phone")
        own_b.last_used_at = datetime.now(timezone.utc)
        db.commit()
        _add_passkey(db, other.id, "Other")
        owner_id, own_a_id, own_b_id = owner.id, own_a.id, own_b.id
        db.close()

        resp = client.get("/api/auth/webauthn/credentials", headers=_headers(owner_id))
        assert resp.status_code == 200
        body = resp.json()
        assert isinstance(body, list)
        ids = {row["id"] for row in body}
        assert ids == {own_a_id, own_b_id}
        for row in body:
            assert set(row.keys()) == {"id", "device_label", "created_at", "last_used_at"}
            assert "public_key" not in row
            assert "credential_id" not in row
            datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
            if row["last_used_at"] is not None:
                datetime.fromisoformat(row["last_used_at"].replace("Z", "+00:00"))


class TestDeleteWebAuthnCredential:
    def test_delete_last_passkey_when_only_password_hash_remains_returns_400(self):
        db = SessionLocal()
        user = _add_user(db, password=VALID_PASS)
        cred = _add_passkey(db, user.id)
        user_id, cred_id = user.id, cred.id
        db.close()

        resp = client.delete(
            f"/api/auth/webauthn/credentials/{cred_id}",
            headers=_headers(user_id),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cannot remove last sign-in method"

    def test_delete_own_passkey_when_google_remains(self):
        db = SessionLocal()
        user = _add_user(db, password=None, google_sub="google-sub-" + uuid.uuid4().hex)
        cred = _add_passkey(db, user.id)
        user_id, cred_id = user.id, cred.id
        db.close()

        resp = client.delete(
            f"/api/auth/webauthn/credentials/{cred_id}",
            headers=_headers(user_id),
        )
        assert resp.status_code == 200

    def test_delete_last_passkey_when_only_recovery_remains_returns_400(self):
        db = SessionLocal()
        user = _add_user(db, password=None)
        cred = _add_passkey(db, user.id)
        store_recovery_codes(db, user.id, generate_plain_codes(2))
        user_id, cred_id = user.id, cred.id
        db.close()

        resp = client.delete(
            f"/api/auth/webauthn/credentials/{cred_id}",
            headers=_headers(user_id),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cannot remove last sign-in method"

    def test_delete_own_passkey_when_second_passkey_remains(self):
        db = SessionLocal()
        user = _add_user(db, password=None)
        keep = _add_passkey(db, user.id, "Keep")
        drop = _add_passkey(db, user.id, "Drop")
        user_id, keep_id, drop_id = user.id, keep.id, drop.id
        db.close()

        resp = client.delete(
            f"/api/auth/webauthn/credentials/{drop_id}",
            headers=_headers(user_id),
        )
        assert resp.status_code == 200

        db = SessionLocal()
        remaining = db.query(WebAuthnCredential).filter_by(user_id=user_id).all()
        assert [c.id for c in remaining] == [keep_id]
        db.close()

    def test_delete_last_passkey_with_no_other_factors_returns_400(self):
        db = SessionLocal()
        user = _add_user(db, password=None)
        cred = _add_passkey(db, user.id)
        user_id, cred_id = user.id, cred.id
        db.close()

        resp = client.delete(
            f"/api/auth/webauthn/credentials/{cred_id}",
            headers=_headers(user_id),
        )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cannot remove last sign-in method"

        db = SessionLocal()
        assert db.query(WebAuthnCredential).filter_by(id=cred_id).first() is not None
        db.close()

    def test_delete_other_users_credential_returns_404(self):
        db = SessionLocal()
        owner = _add_user(db)
        attacker = _add_user(db)
        cred = _add_passkey(db, owner.id)
        attacker_id, cred_id = attacker.id, cred.id
        db.close()

        resp = client.delete(
            f"/api/auth/webauthn/credentials/{cred_id}",
            headers=_headers(attacker_id),
        )
        assert resp.status_code == 404
        assert resp.status_code != 403

        db = SessionLocal()
        assert db.query(WebAuthnCredential).filter_by(id=cred_id).first() is not None
        db.close()

    def test_delete_missing_credential_returns_404(self):
        db = SessionLocal()
        user = _add_user(db)
        user_id = user.id
        db.close()

        resp = client.delete(
            f"/api/auth/webauthn/credentials/{uuid.uuid4()}",
            headers=_headers(user_id),
        )
        assert resp.status_code == 404


class TestUnlinkGoogle:
    def test_unlink_google_when_only_password_hash_remains_returns_400(self):
        db = SessionLocal()
        user = _add_user(db, password=VALID_PASS, google_sub="google-sub-" + uuid.uuid4().hex)
        uid = user.id
        db.close()

        resp = client.post("/api/auth/google/unlink", headers=_headers(uid))
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cannot remove last sign-in method"

    def test_unlink_google_when_passkey_remains(self):
        db = SessionLocal()
        user = _add_user(db, password=None, google_sub="google-sub-" + uuid.uuid4().hex)
        _add_passkey(db, user.id)
        uid = user.id
        db.close()

        resp = client.post("/api/auth/google/unlink", headers=_headers(uid))
        assert resp.status_code == 200
        db = SessionLocal()
        assert db.query(User).filter_by(id=uid).one().google_sub is None
        db.close()

    def test_unlink_google_last_factor_returns_400(self):
        db = SessionLocal()
        user = _add_user(db, password=None, google_sub="google-sub-" + uuid.uuid4().hex)
        uid = user.id
        db.close()

        resp = client.post("/api/auth/google/unlink", headers=_headers(uid))
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Cannot remove last sign-in method"

        db = SessionLocal()
        assert db.query(User).filter_by(id=uid).one().google_sub is not None
        db.close()

    def test_unlink_when_not_linked_returns_400(self):
        db = SessionLocal()
        user = _add_user(db, password=VALID_PASS, google_sub=None)
        uid = user.id
        db.close()

        resp = client.post("/api/auth/google/unlink", headers=_headers(uid))
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Google is not linked"


class TestUnauthenticated:
    def test_unauthenticated_returns_401(self):
        missing = [
            ("GET", "/api/auth/webauthn/credentials"),
            ("DELETE", f"/api/auth/webauthn/credentials/{uuid.uuid4()}"),
            ("POST", "/api/auth/google/unlink"),
        ]
        for method, path in missing:
            resp = client.request(method, path)
            assert resp.status_code == 401, f"{method} {path} → {resp.status_code}"

        bad = {"Authorization": "Bearer not-a-jwt"}
        for method, path in missing:
            resp = client.request(method, path, headers=bad)
            assert resp.status_code == 401, f"{method} {path} bad token → {resp.status_code}"
