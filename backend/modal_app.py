"""
Modal Cron entrypoint for the nightly vendor scan — replaces the APScheduler
job in scheduler.py (see .claude/plans "Modal Cron migration" for the full
rollout plan). Deploy with `modal deploy backend/modal_app.py`; invoke
manually for verification with `modal run backend/modal_app.py::run
--vendor-id <id>`.

All backend/* imports are deferred into function bodies rather than done at
module scope — this file is executed locally to register the App, so only
`modal` needs to be installed on the machine running `modal deploy`/`modal
run`, not the full backend dependency set. Deliberately does not import
main.py — it runs migration DDL at module import time, which is safe for a
single always-on container but not for a second, independently-scheduled
process to also trigger.
"""
import modal

app = modal.App("venderscope-nightly-scan")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install_from_requirements("requirements.txt")
    .add_local_dir(
        ".",
        remote_path="/app",
        # add_local_dir does NOT read backend/.dockerignore (Modal has its own
        # ignore mechanism) — must exclude secrets/local db explicitly or they
        # get baked into the image.
        ignore=[
            ".env", ".env.*", "*.db", "vendorscope.db",
            "__pycache__", "*.pyc", ".pytest_cache",
            "tests/", ".git", ".github", "node_modules",
        ],
    )
)


def _run(vendor_id: str | None = None) -> None:
    import gc
    import sys
    sys.path.insert(0, "/app")

    from database import SessionLocal
    from models import Vendor
    from services.alerts import _is_reserved_test_domain
    from services.scanner import run_full_scan

    db = SessionLocal()
    try:
        q = db.query(Vendor.id).filter(Vendor.user_id.isnot(None))
        if vendor_id:
            q = q.filter(Vendor.id == vendor_id)
        vendor_ids = [v for (v,) in q.all()]
    finally:
        db.close()

    scanned, skipped = 0, 0
    for vid in vendor_ids:
        vendor_db = SessionLocal()
        vendor = None
        try:
            vendor = vendor_db.get(Vendor, vid)
            if not vendor or not vendor.user_id:
                skipped += 1
                continue
            if _is_reserved_test_domain(vendor.domain):
                print(f"[ModalScan] Skipping reserved/test vendor {vendor.name} ({vendor.domain})")
                skipped += 1
                continue
            run_full_scan(vendor, vendor_db, force=True)
            scanned += 1
        except Exception as e:
            vendor_label = vendor.name if vendor else vid
            print(f"[ModalScan] Error scanning {vendor_label}: {e}")
        finally:
            vendor_db.close()
            gc.collect()  # Release BeautifulSoup parse trees and HTML between vendors

    print(f"[ModalScan] Nightly scan complete — scanned {scanned}, skipped {skipped}")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("venderscope-scan-secrets")],
    # 01:15 UTC — after quota.py's UTC-midnight daily quota reset.
    schedule=modal.Cron("15 1 * * *"),
    timeout=3600,
    # A Modal-level retry would re-run run_full_scan and unconditionally
    # append another RiskScoreHistory row — same double-write hazard the
    # rollout plan avoids by not running two schedulers on the same night.
    retries=0,
    memory=1024,
)
def scheduled_scan() -> None:
    _run(vendor_id=None)


@app.local_entrypoint()
def run(vendor_id: str = None) -> None:
    """
    Manual invocation for rollout verification.
    `modal run backend/modal_app.py::run --vendor-id <id>` scopes to one
    vendor — safe to run against prod while the legacy APScheduler job is
    still active, since it can't produce the duplicate-RiskScoreHistory-row
    hazard a full-fleet run could. Omit --vendor-id only after the legacy
    scheduler has been disabled (ENABLE_LEGACY_NIGHTLY_SCAN=0).
    """
    scheduled_scan_for_vendor.remote(vendor_id) if vendor_id else scheduled_scan.remote()


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("venderscope-scan-secrets")],
    timeout=300,
)
def scheduled_scan_for_vendor(vendor_id: str) -> None:
    _run(vendor_id=vendor_id)
