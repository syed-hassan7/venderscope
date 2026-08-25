"""Tests for auth factor invariants and helpers."""

import uuid

import pytest
from database import SessionLocal, engine, Base
from models import User, WebAuthnCredential
from services.auth_factors import (
    get_user_factors,
    count_login_factors,
    can_remove_passkey,
    can_unlink_google,
)
from services.auth_service import hash_password
from services.recovery_service import store_recovery_codes, generate_plain_codes


@pytest.fixture(autouse=True)
def _fresh_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def _user(db, email_suffix: str, password: str | None = "SecureP@ss123!") -> User:
    user = User(
        id=str(uuid.uuid4()),
        email=f"factors_{email_suffix}_{uuid.uuid4().hex[:6]}@example.com",
        password_hash=hash_password(password) if password else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestAuthFactors:
    def test_password_only_factors(self):
        db = SessionLocal()
        user = _user(db, "pw")
        factors = get_user_factors(db, user)
        assert factors["password"] is True
        assert factors["passkey_count"] == 0
        assert factors["google"] is False
        assert factors["recovery_codes_remaining"] == 0
        assert count_login_factors(db, user) == 0
        db.close()

    def test_passkey_user_null_password(self):
        db = SessionLocal()
        user = _user(db, "pk", password=None)
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id="cred-" + uuid.uuid4().hex,
                public_key="dGVzdA==",
                sign_count=0,
            )
        )
        store_recovery_codes(db, user.id, generate_plain_codes(2))
        db.commit()

        factors = get_user_factors(db, user)
        assert factors["password"] is False
        assert factors["passkey_count"] == 1
        assert factors["recovery_codes_remaining"] == 2
        assert count_login_factors(db, user) >= 2
        db.close()

    def test_google_sub_without_password(self):
        db = SessionLocal()
        user = _user(db, "google", password=None)
        user.google_sub = "google-sub-" + uuid.uuid4().hex
        db.commit()
        factors = get_user_factors(db, user)
        assert factors["google"] is True
        assert factors["password"] is False
        db.close()

    def test_can_unlink_google_false_when_not_linked(self):
        db = SessionLocal()
        user = _user(db, "no-google")
        assert can_unlink_google(db, user) is False
        db.close()

    def test_can_unlink_google_false_when_only_password_hash_remains(self):
        db = SessionLocal()
        user = _user(db, "g-pw")
        user.google_sub = "google-sub-" + uuid.uuid4().hex
        db.commit()
        assert can_unlink_google(db, user) is False
        db.close()

    def test_can_unlink_google_true_when_passkey_remains(self):
        db = SessionLocal()
        user = _user(db, "g-pk", password=None)
        user.google_sub = "google-sub-" + uuid.uuid4().hex
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id="cred-" + uuid.uuid4().hex,
                public_key="dGVzdA==",
                sign_count=0,
            )
        )
        db.commit()
        assert can_unlink_google(db, user) is True
        db.close()

    def test_can_unlink_google_false_when_only_unused_recovery_remains(self):
        db = SessionLocal()
        user = _user(db, "g-rc", password=None)
        user.google_sub = "google-sub-" + uuid.uuid4().hex
        store_recovery_codes(db, user.id, generate_plain_codes(2))
        db.commit()
        assert can_unlink_google(db, user) is False
        db.close()

    def test_can_unlink_google_false_when_last_factor(self):
        db = SessionLocal()
        user = _user(db, "g-only", password=None)
        user.google_sub = "google-sub-" + uuid.uuid4().hex
        db.commit()
        assert can_unlink_google(db, user) is False
        db.close()

    def test_can_remove_passkey_false_when_only_recovery_remains(self):
        db = SessionLocal()
        user = _user(db, "pk-rc", password=None)
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id="cred-" + uuid.uuid4().hex,
                public_key="dGVzdA==",
                sign_count=0,
            )
        )
        store_recovery_codes(db, user.id, generate_plain_codes(2))
        db.commit()
        assert can_remove_passkey(db, user) is False
        db.close()

    def test_can_remove_passkey_false_when_last_factor(self):
        db = SessionLocal()
        user = _user(db, "pk-only", password=None)
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id="cred-" + uuid.uuid4().hex,
                public_key="dGVzdA==",
                sign_count=0,
            )
        )
        db.commit()
        assert can_remove_passkey(db, user) is False
        db.close()

    def test_can_remove_passkey_false_when_only_password_hash_remains(self):
        db = SessionLocal()
        user = _user(db, "pk-pw")
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id="cred-" + uuid.uuid4().hex,
                public_key="dGVzdA==",
                sign_count=0,
            )
        )
        db.commit()
        assert can_remove_passkey(db, user) is False
        db.close()

    def test_can_remove_passkey_true_when_google_remains(self):
        db = SessionLocal()
        user = _user(db, "pk-g", password=None)
        user.google_sub = "google-sub-" + uuid.uuid4().hex
        db.add(
            WebAuthnCredential(
                user_id=user.id,
                credential_id="cred-" + uuid.uuid4().hex,
                public_key="dGVzdA==",
                sign_count=0,
            )
        )
        db.commit()
        assert can_remove_passkey(db, user) is True
        db.close()
