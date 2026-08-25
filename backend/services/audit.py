"""
Audit log helper — append-only security event recording.

Usage:
    from services.audit import audit
    audit(db, "login.success", request, user_id=user.id)
    audit(db, "login.failed",  request, detail="unknown email")

Event naming convention:  <resource>.<outcome>
    login.success / login.failed
    register.success / register.failed
    logout
    token.refreshed / token.revoked
    account.deleted
    vendor.added / vendor.deleted
    vendor.scanned
    export.pdf
"""

from fastapi import Request
from sqlalchemy.orm import Session
from limiter import _real_ip
from models import AuditLog


def audit(
    db: Session,
    event: str,
    request: Request,
    user_id: str = None,
    detail: str = None,
) -> None:
    """Append a security event to the audit log. Never raises — failures are logged but swallowed."""
    try:
        ip = _get_ip(request)
        db.add(AuditLog(user_id=user_id, event=event, ip=ip, detail=detail))
        db.commit()
    except Exception as e:
        print(f"[Audit] Failed to write event '{event}': {e}")


def _get_ip(request: Request) -> str:
    """Same client IP as the rate limiter (HF first hop / Render last hop)."""
    return _real_ip(request)
