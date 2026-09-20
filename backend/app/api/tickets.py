from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import CurrentUser, DbSession, require_roles
from app.models import Priority, Role, TicketStatus, User
from app.schemas.ticket import (
    AssignRequest,
    EscalateRequest,
    MessageCreate,
    MessageOut,
    TicketCreate,
    TicketDetail,
    TicketOut,
    TicketUpdate,
)
from app.services import ticket_service

router = APIRouter(prefix="/tickets", tags=["Tickets"])

Customer = Annotated[User, Depends(require_roles(Role.CUSTOMER))]
StaffUser = Annotated[User, Depends(require_roles(Role.AGENT, Role.ADMIN))]


@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_ticket(data: TicketCreate, db: DbSession, customer: Customer):
    return ticket_service.create_ticket(db, customer, data)


@router.get("", response_model=list[TicketOut])
def list_tickets(
    db: DbSession,
    user: CurrentUser,
    status_filter: Annotated[Optional[TicketStatus], Query(alias="status")] = None,
    priority: Optional[Priority] = None,
    unassigned: Optional[bool] = None,
):
    """Customers see their own tickets, agents their assigned tickets (or the unassigned queue
    with `unassigned=true`), admins see everything."""
    return ticket_service.list_tickets(db, user, status_filter, priority, unassigned)


@router.get("/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: int, db: DbSession, user: CurrentUser):
    return ticket_service.get_ticket_for_user(db, ticket_id, user)


@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
def add_message(ticket_id: int, data: MessageCreate, db: DbSession, user: CurrentUser):
    ticket = ticket_service.get_ticket_for_user(db, ticket_id, user)
    return ticket_service.add_message(db, user, ticket, data.message)


@router.patch("/{ticket_id}", response_model=TicketOut)
def update_ticket(ticket_id: int, data: TicketUpdate, db: DbSession, user: StaffUser):
    """Change status (e.g. RESOLVED), priority or category."""
    ticket = ticket_service.get_ticket_for_user(db, ticket_id, user)
    return ticket_service.update_ticket(db, user, ticket, data)


@router.post("/{ticket_id}/assign", response_model=TicketOut)
def assign_ticket(ticket_id: int, data: AssignRequest, db: DbSession, user: StaffUser):
    ticket = ticket_service.get_ticket_for_user(db, ticket_id, user)
    return ticket_service.assign_ticket(db, user, ticket, data.agent_id)


@router.post("/{ticket_id}/escalate", response_model=TicketOut)
def escalate_ticket(ticket_id: int, data: EscalateRequest, db: DbSession, user: StaffUser):
    ticket = ticket_service.get_ticket_for_user(db, ticket_id, user)
    return ticket_service.escalate_ticket(db, user, ticket, data)
