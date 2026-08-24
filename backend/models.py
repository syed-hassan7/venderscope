from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base
import uuid as _uuid


def _utcnow():
    return datetime.now(timezone.utc)


def _new_uuid():
    return str(_uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id            = Column(String(36), primary_key=True, default=_new_uuid, index=True)
    email         = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at    = Column(DateTime, default=_utcnow)

    vendors = relationship("Vendor", back_populates="owner", cascade="all, delete")


class Vendor(Base):
    __tablename__ = "vendors"

    id             = Column(String(36), primary_key=True, default=_new_uuid)
    user_id        = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name           = Column(String, nullable=False)
    domain         = Column(String, nullable=False)  # unique per user, not globally
    company_number = Column(String, nullable=True)
    risk_score     = Column(Float, default=0.0)
    added_at       = Column(DateTime, default=_utcnow)
    last_scanned   = Column(DateTime, nullable=True)
    compliance       = Column(Text, nullable=True)  # JSON stored as string
    description      = Column(Text,   nullable=True)
    logo_url         = Column(String, nullable=True)
    auth_method      = Column(String, nullable=True)
    two_factor       = Column(String, nullable=True)
    data_sensitivity = Column(String(20), nullable=True, default='standard')

    owner       = relationship("User", back_populates="vendors")
    events      = relationship("RiskEvent",        back_populates="vendor", cascade="all, delete")
    scores      = relationship("RiskScoreHistory", back_populates="vendor", cascade="all, delete")
    notes       = relationship("VendorNote",     back_populates="vendor", cascade="all, delete")
    acceptances = relationship("RiskAcceptance", back_populates="vendor", cascade="all, delete")
    review_interval_days = Column(Integer,   nullable=True)
    last_reviewed_at     = Column(DateTime,  nullable=True)


class RiskEvent(Base):
    __tablename__ = "risk_events"

    id          = Column(Integer, primary_key=True, index=True)
    vendor_id   = Column(String(36), ForeignKey("vendors.id"))
    source      = Column(String)        # e.g. "HIBP", "NVD", "CompaniesHouse", "News"
    severity    = Column(String)        # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    title       = Column(String)
    description = Column(Text)
    detected_at = Column(DateTime, default=_utcnow)

    vendor = relationship("Vendor", back_populates="events")


class RiskScoreHistory(Base):
    __tablename__ = "risk_score_history"

    id          = Column(Integer, primary_key=True, index=True)
    vendor_id   = Column(String(36), ForeignKey("vendors.id"))
    score       = Column(Float)
    recorded_at = Column(DateTime, default=_utcnow)

    vendor = relationship("Vendor", back_populates="scores")


class RevokedToken(Base):
    """JTI blacklist — refresh tokens added here on logout or rotation."""
    __tablename__ = "revoked_tokens"

    jti        = Column(String(36), primary_key=True)   # UUID from JWT jti claim
    expires_at = Column(DateTime, nullable=False, index=True)  # used for cleanup


class SearchQuotaUsage(Base):
    """Authoritative monthly Tavily search-quota usage, persisted in the database."""
    __tablename__ = "search_quota_usage"

    quota_date = Column(String(10), primary_key=True)  # YYYY-MM in UTC (column name kept for zero-migration compat)
    used       = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class SchedulerLease(Base):
    """Cross-process lease so only one app instance runs background jobs."""
    __tablename__ = "scheduler_leases"

    name         = Column(String(32), primary_key=True)
    owner_id     = Column(String(36), nullable=False, index=True)
    refreshed_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)


class VendorNote(Base):
    __tablename__ = "vendor_notes"

    id         = Column(Integer, primary_key=True, index=True)
    vendor_id  = Column(String(36), ForeignKey("vendors.id"), nullable=False)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    content    = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)

    vendor = relationship("Vendor", back_populates="notes")


class RiskAcceptance(Base):
    __tablename__ = "risk_acceptances"

    id            = Column(String(36), primary_key=True, default=_new_uuid)
    vendor_id     = Column(String(36), ForeignKey("vendors.id"), nullable=False)
    user_id       = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    event_id      = Column(Integer, ForeignKey("risk_events.id"), nullable=True)
    finding_ref   = Column(String(150), nullable=False)
    finding_type  = Column(String(20),  nullable=False)
    justification = Column(Text, nullable=False)
    reviewer      = Column(String(100), nullable=False)
    expires_at    = Column(DateTime, nullable=False)
    created_at    = Column(DateTime, default=_utcnow)

    vendor = relationship("Vendor", back_populates="acceptances")


class AuditLog(Base):
    """Immutable security event log — never updated, only appended."""
    __tablename__ = "audit_log"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(String(36), nullable=True, index=True)  # None for failed logins
    event      = Column(String(64), nullable=False)             # e.g. "login.success"
    ip         = Column(String(45), nullable=True)              # IPv4 or IPv6
    detail     = Column(String(255), nullable=True)             # optional context
    created_at = Column(DateTime, default=_utcnow, index=True)
