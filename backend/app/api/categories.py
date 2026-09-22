from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.category import CategoryOut
from app.services import admin_service

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryOut])
def list_active_categories(db: DbSession, user: CurrentUser):
    """Active categories of the caller's business, to choose one when creating a complaint."""
    return admin_service.list_categories(db, user.business_id, only_active=True)
