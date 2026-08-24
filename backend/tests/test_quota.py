from database import Base, SessionLocal, engine
from models import SearchQuotaUsage
import services.quota as quota


def test_quota_consumption_persists_in_database():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        db.query(SearchQuotaUsage).delete()
        db.commit()
    finally:
        db.close()

    status_before = quota.get_quota_status()
    assert quota.consume_search_units(3) is True
    status_after = quota.get_quota_status()

    assert status_after["used"] == status_before["used"] + 3
    assert status_after["remaining"] == status_before["remaining"] - 3

    db = SessionLocal()
    try:
        row = db.get(SearchQuotaUsage, quota._this_period())
        assert row is not None
        assert row.used == status_after["used"]
    finally:
        db.close()


def test_quota_auto_resets_on_new_month():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        db.query(SearchQuotaUsage).delete()
        db.merge(SearchQuotaUsage(quota_date="1999-12", used=42))
        db.commit()
    finally:
        db.close()

    old_month = quota.get_quota_status()
    assert old_month["used"] != 42  # current month's row, untouched by the seeded 1999-12 row

    db = SessionLocal()
    try:
        old_row = db.get(SearchQuotaUsage, "1999-12")
        assert old_row is not None
        assert old_row.used == 42  # a different month is a distinct row, not reset in place
    finally:
        db.close()


def test_quota_refund_restores_units():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        db.query(SearchQuotaUsage).delete()
        db.commit()
    finally:
        db.close()

    assert quota.consume_search_units(5) is True
    assert quota.refund_search_units(2) is True

    status = quota.get_quota_status()
    assert status["used"] == 3
    assert status["remaining"] == quota.MONTHLY_LIMIT - 3
