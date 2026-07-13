from fastapi import APIRouter, Depends
from services.quota import get_quota_status
from services.auth_service import get_current_user
from models import User

router = APIRouter()

@router.get("")
@router.get("/", include_in_schema=False)
def quota_status(current_user: User = Depends(get_current_user)):
    return get_quota_status()