from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.user import AgentBrief
from app.services import admin_service

router = APIRouter(prefix="/agents", tags=["Agents"])

StaffUser = Annotated[User, Depends(require_roles(Role.AGENT, Role.ADMIN))]


@router.get("", response_model=list[AgentBrief])
def list_active_agents(db: DbSession, user: StaffUser):
    """Active agents of the caller's business (name and department only), for assigning tickets."""
    return [agent for agent in admin_service.list_agents(db, user.business_id) if agent.user.is_active]
