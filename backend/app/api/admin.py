from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status

from app.api.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.admin import Stats
from app.schemas.category import CategoryCreate, CategoryOut, CategoryUpdate
from app.schemas.user import AgentCreate, AgentOut, UserActiveUpdate, UserOut
from app.services import admin_service

# Every route in this file requires an ADMIN.
router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_roles(Role.ADMIN))])

Admin = Annotated[User, Depends(require_roles(Role.ADMIN))]


@router.get("/users", response_model=list[UserOut])
def list_users(db: DbSession, admin: Admin, role: Optional[Role] = None):
    return admin_service.list_users(db, admin.business_id, role)


@router.patch("/users/{user_id}", response_model=UserOut)
def set_user_active(user_id: int, data: UserActiveUpdate, db: DbSession, admin: Admin):
    """Enable or disable an account."""
    return admin_service.set_user_active(db, admin, user_id, data.is_active)


@router.get("/agents", response_model=list[AgentOut])
def list_agents(db: DbSession, admin: Admin):
    return admin_service.list_agents(db, admin.business_id)


@router.post("/agents", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def create_agent(data: AgentCreate, db: DbSession, admin: Admin):
    return admin_service.create_agent(db, data, admin.business_id)


@router.get("/categories", response_model=list[CategoryOut])
def list_all_categories(db: DbSession, admin: Admin):
    return admin_service.list_categories(db, admin.business_id)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(data: CategoryCreate, db: DbSession, admin: Admin):
    return admin_service.create_category(db, data, admin.business_id)


@router.patch("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: DbSession, admin: Admin):
    return admin_service.update_category(db, admin.business_id, category_id, data)


@router.get("/stats", response_model=Stats)
def get_stats(db: DbSession, admin: Admin):
    return admin_service.get_stats(db, admin.business_id)
