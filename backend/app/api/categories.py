from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.category import CategoryOut
from app.services import admin_service

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryOut])
def list_active_categories(db: DbSession, _user: CurrentUser):
    """Active categories, so customers can choose one when creating a complaint."""
    return admin_service.list_categories(db, only_active=True)
