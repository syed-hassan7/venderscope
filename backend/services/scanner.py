import re
import json
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy.orm import Session
from models import Vendor, RiskEvent, RiskScoreHistory
from services.hibp import check_domain_breaches
from services.nvd import check_vendor_cves
from services.companies_house import check_company_health
from services.shodan_service import check_shodan_exposure
from services.alerts import ALERT_THRESHOLD, send_alert_email
from services.compliance_discovery import run_compliance_discovery
from services.vendor_profile import discover_vendor_profile
from services.quota import get_quota_status

# Severity weights for scoring
SEVERITY_WEIGHTS = {"CRITICAL": 25, "HIGH": 15, "MEDIUM": 7, "LOW": 2}
CACHE_TTL_HOURS  = 24

def _is_cached(vendor: Vendor) -> bool:
    if not vendor.last_scanned:
        return False
    return (datetime.now(timezone.utc) - vendor.last_scanned) < timedelta(hours=CACHE_TTL_HOURS)

def _compute_score(events: list) -> float:
    """
    Weighted average of top 5 events + count multiplier.
    Prevents everything hitting 100 with many low-severity events.
    """
    if not events:
        return 0.0
    sev_map   = {"CRITICAL": 100, "HIGH": 70, "MEDIUM": 40, "LOW": 15}
    raw       = sorted([sev_map.get(e.get("severity", "LOW"), 15) for e in events], reverse=True)
    top5_avg  = sum(raw[:5]) / min(len(raw), 5)
    count_mul = min(1.0 + (len(events) - 1) * 0.04, 1.4)
    return min(round(top5_avg * count_mul, 1), 100.0)

def run_full_scan(vendor: Vendor, db: Session, force: bool = False) -> float:
    # Cache hit — return instantly
    if not force and _is_cached(vendor):
        print(f"[Scanner] {vendor.name} — cache hit ({vendor.risk_score})")
        return vendor.risk_score

    print(f"[Scanner] Scanning {vendor.name}...")
    start = datetime.now(timezone.utc)
    previous_score = vendor.risk_score or 0.0

    quota_status = get_quota_status()
    if quota_status["exhausted"]:
        print(f"[Scanner] Search quota exhausted — {vendor.name} will skip external compliance search.")

    # Run all intelligence sources concurrently
    tasks = {
        "hibp":    (check_domain_breaches,   vendor.domain),
        "nvd":     (check_vendor_cves,       vendor.name),
        "shodan":  (check_shodan_exposure,   vendor.domain),
        "profile": (discover_vendor_profile, vendor.domain),
    }
    if vendor.company_number:
        tasks["ch"] = (check_company_health, vendor.company_number)

    raw = {}
    # Not a `with` block: ThreadPoolExecutor.__exit__ calls shutdown(wait=True),
    # which would block this request on any straggler past the 60s budget anyway.
    # shutdown(wait=False) below lets the response return promptly; orphaned
    # workers only touch plain domain/name strings (no db/vendor object), so
    # letting them finish in the background is harmless.
    ex = ThreadPoolExecutor(max_workers=5)
    try:
        futures = {ex.submit(fn, arg): key for key, (fn, arg) in tasks.items()}

        # Compliance submitted separately — needs two args + quota flag
        compliance_future = ex.submit(
            run_compliance_discovery, vendor.domain, vendor.name, not quota_status["exhausted"]
        )
        futures[compliance_future] = "compliance"

        # as_completed(timeout=...) bounds the whole batch, not each future — if it
        # trips, everything not yet done is still "pending" and gets an empty
        # fallback below, but whatever DID finish in time is kept and still commits.
        # (No forced result loss on a single slow source anymore.)
        # profile/compliance return dicts; every other source returns a list —
        # downstream code (e.g. profile_data.get("description")) assumes that
        # shape, so the empty fallback must match it or it crashes on .get().
        _DICT_SHAPED = ("compliance", "profile")

        pending = set(futures)
        failed_sources = 0
        try:
            for f in as_completed(pending, timeout=60):
                key = futures[f]
                pending.discard(f)
                try:
                    raw[key] = f.result()
                except Exception as e:
                    print(f"[Scanner] {key} failed: {e}")
                    raw[key] = {} if key in _DICT_SHAPED else []
                    failed_sources += 1
        except TimeoutError:
            for f in pending:
                key = futures[f]
                print(f"[Scanner] {key} exceeded 60s scan budget — using empty result")
                raw[key] = {} if key in _DICT_SHAPED else []
                failed_sources += 1
    finally:
        ex.shutdown(wait=False)

    # If every single source failed/timed out, "no events" means "nothing was
    # actually checked" — not "checked and clean". Don't cache a false score/
    # last_scanned over the vendor's real last-known state.
    if failed_sources >= len(futures):
        print(f"[Scanner] {vendor.name} — all {len(futures)} sources failed; "
              f"keeping previous score ({previous_score}) instead of caching a false result")
        return previous_score

    # Assemble all events
    all_events = []
    for b in raw.get("hibp",   []): all_events.append({**b, "source": "HIBP"})
    for c in raw.get("nvd",    []): all_events.append({**c, "source": "NVD"})
    for s in raw.get("shodan", []): all_events.append({**s, "source": "Shodan"})
    for e in raw.get("ch",     []): all_events.append({**e, "source": "CompaniesHouse"})

    # Deduplicate against DB — match on (source, exact title). NVD titles are bare
    # CVE IDs (no spaces) so this preserves the old CVE-matching behaviour; it also
    # stops false collisions on multi-word titles from HIBP/Shodan/CompaniesHouse,
    # which used to share a first word (e.g. every CompaniesHouse title starts with
    # the vendor name) and silently swallowed real new events on rescan.
    stored = {
        (source, title)
        for (source, title) in db.query(RiskEvent.source, RiskEvent.title)
            .filter(RiskEvent.vendor_id == vendor.id).all()
    }
    new_events = [e for e in all_events if (e.get("source", "Unknown"), e["title"]) not in stored]

    for evt in new_events:
        db.add(RiskEvent(
            vendor_id   = vendor.id,
            source      = evt.get("source", "Unknown"),
            severity    = evt.get("severity", "LOW"),
            title       = evt["title"],
            description = evt.get("description", ""),
        ))

    # Save compliance as JSON string
    compliance_data = raw.get("compliance", {})
    if compliance_data:
        vendor.compliance = json.dumps(compliance_data)

    # Save vendor profile fields — only overwrite if new value was discovered
    profile_data = raw.get("profile", {})
    if profile_data.get("description"):
        vendor.description = profile_data["description"]
    if profile_data.get("logo_url"):
        vendor.logo_url = profile_data["logo_url"]
    if profile_data.get("auth_method"):
        vendor.auth_method = profile_data["auth_method"]
    if profile_data.get("two_factor"):
        vendor.two_factor = profile_data["two_factor"]

    score               = _compute_score(all_events)
    vendor.risk_score   = score
    vendor.last_scanned = datetime.now(timezone.utc)
    db.add(RiskScoreHistory(vendor_id=vendor.id, score=score))
    db.commit()

    owner_email = vendor.owner.email if vendor.owner else None
    if previous_score < score and previous_score < ALERT_THRESHOLD <= score:
        send_alert_email(
            vendor.name,
            vendor.domain,
            score,
            all_events,
            vendor_id=vendor.id,
            recipient_email=owner_email,
        )

    scan_type = "Full Intelligence" if compliance_data.get("search_units_used", 0) > 0 else "Standard"
    elapsed   = (datetime.now(timezone.utc) - start).seconds
    print(f"[Scanner] {vendor.name} → {score} ({scan_type} Scan) | "
          f"+{len(new_events)} new events | {elapsed}s")
    return score


def scan_ephemeral(domain: str, name: str) -> dict:
    """
    Guest scan — CVE check only, zero DB writes, no side effects.
    Returns: {events: list[dict], score: float}
    Deliberately excludes HIBP, Shodan, Companies House, compliance, and profile
    — those signals are reserved for authenticated full scans.
    """
    print(f"[Scanner] Ephemeral scan: {name} ({domain})")
    events = []
    try:
        cves = check_vendor_cves(name)
        for c in cves:
            events.append({**c, "source": "NVD"})
    except Exception as e:
        print(f"[Scanner] Ephemeral NVD failed: {e}")
    score = _compute_score(events)
    print(f"[Scanner] Ephemeral done: {name} → {score} ({len(events)} CVEs)")
    return {"events": events, "score": score}
