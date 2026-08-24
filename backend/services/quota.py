import os
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database import _is_sqlite
from database import SessionLocal
from models import SearchQuotaUsage

MONTHLY_LIMIT = 1000  # Tavily free tier — credits/month, not credits/day
ESTIMATED_SCAN_COST = 6  # Practical estimate after on-site discovery resolves many vendors


def _this_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _next_period_start() -> datetime:
    now = datetime.now(timezone.utc)
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    return now.replace(year=year, month=month, day=1, hour=0, minute=0, second=0, microsecond=0)


def _get_or_create_current_quota(db) -> SearchQuotaUsage:
    quota = db.get(SearchQuotaUsage, _this_period())
    if quota:
        return quota
    quota = SearchQuotaUsage(quota_date=_this_period(), used=0)
    db.add(quota)
    db.flush()
    return quota


def _build_status(used: int) -> dict:
    remaining = max(0, MONTHLY_LIMIT - used)
    resets_at = _next_period_start()
    return {
        "used": used,
        "remaining": remaining,
        "limit": MONTHLY_LIMIT,
        "resets_at": resets_at.isoformat(),
        "exhausted": remaining <= 0,
        "search_units_remaining": remaining,
        "full_scans_remaining": max(0, remaining) // ESTIMATED_SCAN_COST,
    }


def current_quota_period() -> str:
    """Public accessor so callers can pin one period across a reserve→refund pair,
    instead of each call re-deriving 'now' and risking a month-boundary mismatch."""
    return _this_period()


def _get_or_create_current_quota_for_update(db, period: str) -> SearchQuotaUsage:
    quota_date = period
    stmt = select(SearchQuotaUsage).where(SearchQuotaUsage.quota_date == quota_date)
    if not _is_sqlite:
        stmt = stmt.with_for_update()

    quota = db.execute(stmt).scalar_one_or_none()
    if quota:
        return quota

    quota = SearchQuotaUsage(quota_date=quota_date, used=0)
    db.add(quota)
    try:
        db.flush()
        return quota
    except IntegrityError:
        db.rollback()
        retry_stmt = select(SearchQuotaUsage).where(SearchQuotaUsage.quota_date == quota_date)
        if not _is_sqlite:
            retry_stmt = retry_stmt.with_for_update()
        return db.execute(retry_stmt).scalar_one()


def get_quota_status() -> dict:
    """Returns current quota state from the database-backed monthly usage row."""
    db = SessionLocal()
    try:
        quota = _get_or_create_current_quota(db)
        db.commit()
        return _build_status(quota.used)
    finally:
        db.close()


def consume_search_units(units: int = 1, period: str | None = None) -> bool:
    """Consume Tavily credits only when an external search is actually performed.

    `period` lets a caller pin the exact period string used at reservation time
    and pass the same value into refund_search_units — otherwise a request that
    straddles a month boundary could reserve against one month and refund
    against the next, silently losing a unit from the month that spent it.
    """
    if units <= 0:
        return True
    period = period or _this_period()

    db = SessionLocal()
    try:
        quota = _get_or_create_current_quota_for_update(db, period)
        if quota.used + units > MONTHLY_LIMIT:
            print(f"[Quota] Exhausted — {quota.used}/{MONTHLY_LIMIT} units used this month.")
            db.rollback()
            return False

        quota.used += units
        db.commit()

        remaining_scans = max(0, MONTHLY_LIMIT - quota.used) // ESTIMATED_SCAN_COST
        print(f"[Quota] Consumed {units} unit(s) — {quota.used}/{MONTHLY_LIMIT} used this month "
              f"({remaining_scans} estimated full scans remaining).")
        return True
    finally:
        db.close()


def refund_search_units(units: int = 1, period: str | None = None) -> bool:
    """Refund previously reserved search units after an external request failure.

    Pass the same `period` used at reservation time (see consume_search_units)
    so the refund lands on the row it was actually consumed from.
    """
    if units <= 0:
        return True
    period = period or _this_period()

    db = SessionLocal()
    try:
        quota = _get_or_create_current_quota_for_update(db, period)
        quota.used = max(0, quota.used - units)
        db.commit()
        print(f"[Quota] Refunded {units} unit(s) — {quota.used}/{MONTHLY_LIMIT} used this month.")
        return True
    finally:
        db.close()


def search_is_configured() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))


def get_remaining_full_scans(data: dict = None) -> int:
    """Estimated full scans remaining this month, based on average external search usage."""
    if data is not None:
        used = data["used"]
        return max(0, MONTHLY_LIMIT - used) // ESTIMATED_SCAN_COST
    return get_quota_status()["full_scans_remaining"]
