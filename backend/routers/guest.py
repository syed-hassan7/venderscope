from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from database import get_db
from limiter import limiter
from services.scanner import scan_ephemeral
from services.compliance_discovery import _is_safe_domain
from services.audit import audit
from services.guest_scan_token import create_guest_scan_token, decode_guest_scan_token

router = APIRouter()


class GuestScanRequest(BaseModel):
    domain: str
    name: str

    @field_validator("domain")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        v = v.strip().lower()
        v = v.replace("https://", "").replace("http://", "").rstrip("/")
        if not v:
            raise ValueError("Domain cannot be empty")
        if len(v) > 253:
            raise ValueError("Domain must be under 253 characters")
        return v

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be empty")
        if len(v) > 100:
            raise ValueError("Name must be under 100 characters")
        return v


class GuestReportRequest(BaseModel):
    """PDF export bound to a server-issued scan_token (not client-invented score/events)."""
    scan_token: str = Field(..., min_length=20, max_length=20000)


@router.post("/scan")
@limiter.limit("3/hour")
def guest_scan(request: Request, payload: GuestScanRequest, db: Session = Depends(get_db)):
    """
    Unauthenticated CVE-only scan. Rate limited 3/hour per real IP.
    Domain validated against SSRF blocklist before any external call is made.
    Zero DB writes — results returned with a signed scan_token for PDF export.
    """
    if not _is_safe_domain(payload.domain):
        raise HTTPException(status_code=400, detail="Invalid or unsafe domain")
    audit(db, "guest.scan", request, detail=payload.domain)
    result = scan_ephemeral(payload.domain, payload.name)
    scan_token = create_guest_scan_token(
        name=payload.name,
        domain=payload.domain,
        score=result["score"],
        events=result["events"],
    )
    return {
        "events": result["events"],
        "score": result["score"],
        "name": payload.name,
        "domain": payload.domain,
        "scan_token": scan_token,
    }


@router.post("/report")
@limiter.limit("5/hour")
def guest_report(request: Request, payload: GuestReportRequest, db: Session = Depends(get_db)):
    """
    Generate a guest PDF from a prior server-side scan (scan_token).
    Rate limited 5/hour per real IP. Client cannot supply arbitrary score/events.
    """
    try:
        scan = decode_guest_scan_token(payload.scan_token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    audit(db, "guest.report", request, detail=scan["domain"])
    from services.pdf_export import generate_guest_pdf

    pdf_bytes = generate_guest_pdf(
        name=scan["name"],
        domain=scan["domain"],
        score=scan["score"],
        events=scan["events"],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="venderscope-guest-report.pdf"'
        },
    )
