import json
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional
from datetime import datetime, timezone
from database import SessionLocal, get_db
from models import Vendor, RiskEvent, RiskScoreHistory, User, VendorNote
from services.auth_service import get_current_user
from services.audit import audit
from services.risk_context import compute_effective_score, VALID_SENSITIVITIES
from services.untrusted_text import normalize_untrusted_text
from services.vendor_profile import discover_vendor_profile
from limiter import limiter

router = APIRouter()


def _enrich_vendor_profile(vendor_id: str) -> None:
    db = SessionLocal()
    try:
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            return
        profile_data = discover_vendor_profile(vendor.domain)
        if profile_data.get("description"):
            vendor.description = profile_data["description"]
        if profile_data.get("logo_url"):
            vendor.logo_url = profile_data["logo_url"]
        if profile_data.get("auth_method"):
            vendor.auth_method = profile_data["auth_method"]
        if profile_data.get("two_factor"):
            vendor.two_factor = profile_data["two_factor"]
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# --- Schemas ---

class VendorCreate(BaseModel):
    name:           str
    domain:         str
    company_number: Optional[str] = None

    @field_validator('name')
    @classmethod
    def name_length(cls, v):
        if len(v.strip()) == 0:
            raise ValueError('Name cannot be empty')
        if len(v) > 100:
            raise ValueError('Name must be under 100 characters')
        return v.strip()

    @field_validator('domain')
    @classmethod
    def domain_length(cls, v):
        if len(v.strip()) == 0:
            raise ValueError('Domain cannot be empty')
        if len(v) > 253:
            raise ValueError('Domain must be under 253 characters')
        return v.strip().lower().replace('https://', '').replace('http://', '').rstrip('/')


class VendorOut(BaseModel):
    id:               str
    name:             str
    domain:           str
    company_number:   Optional[str]
    risk_score:       float
    effective_score:  float            = 0.0
    data_sensitivity: Optional[str]   = None
    last_scanned:     Optional[datetime] = None
    score_delta:      Optional[float]  = None
    compliance:       Optional[dict]   = None
    description:      Optional[str]    = None
    logo_url:         Optional[str]    = None
    auth_method:          Optional[str]      = None
    two_factor:           Optional[str]      = None
    review_interval_days: Optional[int]      = None
    last_reviewed_at:     Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ContextUpdate(BaseModel):
    data_sensitivity: str

    @field_validator('data_sensitivity')
    @classmethod
    def validate_sensitivity(cls, v):
        if v not in VALID_SENSITIVITIES:
            raise ValueError(f"Must be one of: {', '.join(sorted(VALID_SENSITIVITIES))}")
        return v


class NoteCreate(BaseModel):
    content: str

    @field_validator('content')
    @classmethod
    def content_length(cls, v):
        # Notes are stored as plain untrusted text and may be exported later.
        # Never pass raw note content into AI prompts, SQL, shell commands, or tool inputs.
        v = normalize_untrusted_text(v)
        if not v:
            raise ValueError('Note cannot be empty')
        if len(v) > 1000:
            raise ValueError('Note must be under 1000 characters')
        return v


class ReviewUpdate(BaseModel):
    interval_days: Optional[int] = None
    mark_reviewed: bool = False

    @field_validator('interval_days')
    @classmethod
    def validate_interval(cls, v):
        if v is not None and v not in (30, 60, 90, 180, 365):
            raise ValueError('interval_days must be one of: 30, 60, 90, 180, 365, or null')
        return v


# --- Routes ---

@router.get("", response_model=list[VendorOut])
@router.get("/", response_model=list[VendorOut], include_in_schema=False)
def list_vendors(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vendors = db.query(Vendor).filter(Vendor.user_id == current_user.id).all()
    result = []
    for v in vendors:
        if isinstance(v.compliance, str):
            try:
                v.compliance = json.loads(v.compliance)
            except Exception:
                v.compliance = None
        # Compute score delta: current score minus the previous scan's score
        history = (
            db.query(RiskScoreHistory)
            .filter(RiskScoreHistory.vendor_id == v.id)
            .order_by(RiskScoreHistory.recorded_at.desc())
            .limit(2)
            .all()
        )
        delta = None
        if len(history) >= 2:
            delta = round(history[0].score - history[1].score, 1)
        out = VendorOut.model_validate(v)
        out.score_delta = delta
        out.effective_score = compute_effective_score(v.risk_score, v.data_sensitivity)
        result.append(out)
    return result


@router.post("", response_model=VendorOut)
@router.post("/", response_model=VendorOut, include_in_schema=False)
@limiter.limit("10/minute")
def add_vendor(
    request: Request,
    background_tasks: BackgroundTasks,
    payload: VendorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Vendor).filter(
        Vendor.domain == payload.domain,
        Vendor.user_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Vendor domain already exists")
    vendor = Vendor(**payload.model_dump(), user_id=current_user.id)
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    background_tasks.add_task(_enrich_vendor_profile, vendor.id)
    audit(db, "vendor.added", request, user_id=str(current_user.id), detail=vendor.domain)
    return vendor


@router.delete("/{vendor_id}")
@limiter.limit("10/minute")
def delete_vendor(
    request: Request,
    vendor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Always 404 — never reveal whether a vendor exists but belongs to another user
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    name = vendor.name
    db.delete(vendor)
    db.commit()
    audit(db, "vendor.deleted", request, user_id=str(current_user.id), detail=vendor_id)
    return {"message": f"Vendor '{name}' deleted"}


@router.patch("/{vendor_id}/context")
@limiter.limit("10/minute")
def update_vendor_context(
    request: Request,
    vendor_id: str,
    payload: ContextUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    vendor.data_sensitivity = payload.data_sensitivity
    db.commit()
    audit(db, "vendor.context_updated", request, user_id=str(current_user.id),
          detail=f"{vendor_id}:{payload.data_sensitivity}")
    return {"data_sensitivity": vendor.data_sensitivity}


@router.get("/{vendor_id}/events")
def get_vendor_events(
    vendor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    events = db.query(RiskEvent).filter(RiskEvent.vendor_id == vendor_id)\
               .order_by(RiskEvent.detected_at.desc()).all()
    return events


@router.get("/{vendor_id}/history")
def get_score_history(
    vendor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Ownership check before returning history
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    history = db.query(RiskScoreHistory)\
                .filter(RiskScoreHistory.vendor_id == vendor_id)\
                .order_by(RiskScoreHistory.recorded_at.asc()).all()
    return history


# --- Notes ---

@router.get("/{vendor_id}/notes")
def get_vendor_notes(
    vendor_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    notes = (
        db.query(VendorNote)
        .filter(VendorNote.vendor_id == vendor_id)
        .order_by(VendorNote.created_at.desc())
        .all()
    )
    return notes


@router.post("/{vendor_id}/notes")
@limiter.limit("20/minute")
def add_vendor_note(
    request: Request,
    vendor_id: str,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    note = VendorNote(
        vendor_id=vendor_id,
        user_id=str(current_user.id),
        content=payload.content,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    audit(db, "vendor.note_added", request, user_id=str(current_user.id), detail=vendor_id)
    return note


@router.delete("/{vendor_id}/notes/{note_id}")
@limiter.limit("20/minute")
def delete_vendor_note(
    request: Request,
    vendor_id: str,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    note = db.query(VendorNote).filter(
        VendorNote.id == note_id,
        VendorNote.vendor_id == vendor_id,
        VendorNote.user_id == str(current_user.id),
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
    audit(db, "vendor.note_deleted", request, user_id=str(current_user.id),
          detail=f"{vendor_id}:{note_id}")
    return {"message": "Note deleted"}


# --- Review scheduling ---

@router.patch("/{vendor_id}/review")
@limiter.limit("10/minute")
def update_vendor_review(
    request: Request,
    vendor_id: str,
    payload: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vendor = db.query(Vendor).filter(
        Vendor.id == vendor_id,
        Vendor.user_id == current_user.id,
    ).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    if 'interval_days' in payload.model_fields_set:
        vendor.review_interval_days = payload.interval_days
    if payload.mark_reviewed:
        vendor.last_reviewed_at = datetime.now(timezone.utc)
    db.commit()
    audit(db, "vendor.review_updated", request, user_id=str(current_user.id), detail=vendor_id)
    return {
        "review_interval_days": vendor.review_interval_days,
        "last_reviewed_at":     vendor.last_reviewed_at,
    }
