import uuid

import scheduler
from scheduler import _acquire_scheduler_lease, _has_scheduler_lease, scheduled_scan
from database import Base, SessionLocal, engine
from models import SchedulerLease, User, Vendor


def test_scheduled_scan_skips_reserved_vendors(monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(SchedulerLease).delete()
        db.query(Vendor).delete()
        db.query(User).delete()
        db.commit()
        user = User(email=f"scheduler-owner-{suffix}@company.com", password_hash="hash")
        db.add(user)
        db.commit()
        db.refresh(user)

        real_vendor = Vendor(
            user_id=user.id,
            name="Real Vendor",
            domain="company.com",
        )
        reserved_vendor = Vendor(
            user_id=user.id,
            name="Debug Vendor",
            domain="debug-a2a9f867.example",
        )
        db.add_all([real_vendor, reserved_vendor])
        db.commit()
        db.refresh(real_vendor)
    finally:
        db.close()

    scanned = []

    def fake_run_full_scan(vendor, db_session, force=False):
        scanned.append((vendor.name, vendor.domain, force))
        return 0.0

    monkeypatch.setattr("scheduler.run_full_scan", fake_run_full_scan)
    owner_id = str(uuid.uuid4())
    assert _acquire_scheduler_lease(owner_id) is True

    scheduled_scan(owner_id)

    assert scanned == [("Real Vendor", "company.com", True)]


def test_scheduler_lease_blocks_second_owner():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(SchedulerLease).delete()
        db.query(Vendor).delete()
        db.query(User).delete()
        db.commit()
    finally:
        db.close()

    owner_a = str(uuid.uuid4())
    owner_b = str(uuid.uuid4())

    assert _acquire_scheduler_lease(owner_a) is True
    assert _has_scheduler_lease(owner_a) is True
    assert _acquire_scheduler_lease(owner_b) is False


def test_start_scheduler_skips_daily_scan_when_legacy_disabled(monkeypatch):
    """ENABLE_LEGACY_NIGHTLY_SCAN=0 (moving to Modal Cron) must not register
    the daily_scan job, while keep_alive/token_cleanup still run as normal."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        db.query(SchedulerLease).delete()
        db.commit()
    finally:
        db.close()

    # _LEGACY_SCAN_ENABLED is read from the env once at module import time,
    # so patch the module attribute directly rather than the env var.
    monkeypatch.setattr(scheduler, "_LEGACY_SCAN_ENABLED", False)

    sched = scheduler.start_scheduler()
    try:
        assert sched is not None
        assert sched.get_job("daily_scan") is None
        assert sched.get_job("keep_alive") is not None
        assert sched.get_job("token_cleanup") is not None
    finally:
        sched.shutdown(wait=False)
