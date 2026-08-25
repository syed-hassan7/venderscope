"""Tests for auth factor invariants and helpers."""

import uuid

import pytest
from database import SessionLocal
from models import User, WebAuthnCredential, RecoveryCodeHash
from services.auth_factors import get_user_factors, count_login_factors
from services.auth_service import hash_password
from services.recovery_service import store_recovery_codes, generate_plain_codes


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
        assert count_login_factors(db, user) == 1
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
