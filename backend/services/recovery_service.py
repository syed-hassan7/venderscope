"""One-time recovery codes — hashed at rest, shown once at signup."""

import hashlib
import hmac
import os
import secrets
import string

from sqlalchemy.orm import Session

from models import RecoveryCodeHash
from services.auth_service import hash_password, verify_password

RECOVERY_CODE_COUNT = 10
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_GROUPS = 4
_CODE_GROUP_LEN = 4


def _pepper() -> str:
    pepper = os.getenv("RECOVERY_CODE_PEPPER")
    if not pepper:
        if os.getenv("ENV", "").lower() == "production":
            raise RuntimeError("RECOVERY_CODE_PEPPER is required in production.")
        return "dev-recovery-pepper-not-for-production"
    return pepper


def _normalize_code(code: str) -> str:
    return code.strip().upper().replace("-", "").replace(" ", "")


def generate_plain_codes(count: int = RECOVERY_CODE_COUNT) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_GROUPS * _CODE_GROUP_LEN))
        grouped = "-".join(raw[i:i + _CODE_GROUP_LEN] for i in range(0, len(raw), _CODE_GROUP_LEN))
        codes.append(grouped)
    return codes


def hash_recovery_code(code: str) -> str:
    normalized = _normalize_code(code)
    pepper = _pepper()
    # HMAC-SHA256 then bcrypt for slow verify
    digest = hmac.new(pepper.encode(), normalized.encode(), hashlib.sha256).hexdigest()
    return hash_password(digest)


def verify_recovery_code(code: str, code_hash: str) -> bool:
    normalized = _normalize_code(code)
    pepper = _pepper()
    digest = hmac.new(pepper.encode(), normalized.encode(), hashlib.sha256).hexdigest()
    return verify_password(digest, code_hash)


def store_recovery_codes(db: Session, user_id: str, plain_codes: list[str]) -> None:
    for plain in plain_codes:
        db.add(
            RecoveryCodeHash(
                user_id=user_id,
                code_hash=hash_recovery_code(plain),
            )
        )
    db.commit()


def replace_recovery_codes(db: Session, user_id: str) -> list[str]:
    db.query(RecoveryCodeHash).filter(RecoveryCodeHash.user_id == user_id).delete()
    db.commit()
    codes = generate_plain_codes()
    store_recovery_codes(db, user_id, codes)
    return codes


def consume_recovery_code(db: Session, user_id: str, code: str) -> bool:
    rows = (
        db.query(RecoveryCodeHash)
        .filter(RecoveryCodeHash.user_id == user_id, RecoveryCodeHash.used_at.is_(None))
        .all()
    )
    from datetime import datetime, timezone

    for row in rows:
        if verify_recovery_code(code, row.code_hash):
            row.used_at = datetime.now(timezone.utc)
            db.commit()
            return True
    return False
