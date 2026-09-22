from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.base import utcnow
from app.models import Agent, Category, Priority, Role, Ticket, TicketMessage, TicketStatus, User
from app.schemas.ticket import EscalateRequest, TicketCreate, TicketUpdate
from app.services import handoff_service
from app.services.handoff_service import HandoffError

# Which status changes are allowed from each status.
ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.ESCALATED,
        TicketStatus.RESOLVED,
    },
    TicketStatus.IN_PROGRESS: {
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.ESCALATED,
        TicketStatus.RESOLVED,
    },
    TicketStatus.WAITING_FOR_CUSTOMER: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.ESCALATED,
        TicketStatus.RESOLVED,
    },
    TicketStatus.ESCALATED: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.RESOLVED: {TicketStatus.IN_PROGRESS, TicketStatus.CLOSED},  # IN_PROGRESS = reopen
    TicketStatus.CLOSED: set(),
}


# ---------- access rules (authorization) ----------

def _agent_id(user: User) -> int | None:
    return user.agent_profile.id if user.agent_profile else None


def can_view(user: User, ticket: Ticket) -> bool:
    """Admin sees all. Customer sees own. Agent sees own assigned tickets and the unassigned queue."""
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.CUSTOMER:
        return ticket.customer_id == user.id
    if user.role == Role.AGENT:
        return ticket.assigned_agent_id is None or ticket.assigned_agent_id == _agent_id(user)
    return False


def can_manage(user: User, ticket: Ticket) -> bool:
    """Admin can manage any ticket. An agent can only manage tickets assigned to them."""
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.AGENT:
        return ticket.assigned_agent_id is not None and ticket.assigned_agent_id == _agent_id(user)
    return False


def get_ticket_for_user(db: Session, ticket_id: int, user: User) -> Ticket:
    """Load a ticket. Not-found and not-allowed both return 404 so ticket IDs can't be probed."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None or not can_view(user, ticket):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Ticket not found")
    return ticket


def _require_manage(user: User, ticket: Ticket) -> None:
    if not can_manage(user, ticket):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the assigned agent or an admin can do this. Assign the ticket to yourself first.",
        )


def _check_category(db: Session, category_id: int) -> None:
    category = db.get(Category, category_id)
    if category is None or not category.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Category does not exist or is inactive")


def _change_status(ticket: Ticket, new_status: TicketStatus) -> None:
    if new_status == ticket.status:
        return
    if new_status not in ALLOWED_TRANSITIONS[ticket.status]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Cannot change status from {ticket.status} to {new_status}",
        )
    ticket.status = new_status


# ---------- operations ----------

def create_ticket(db: Session, customer: User, data: TicketCreate) -> Ticket:
    # The owner is always the signed-in customer; the request never decides it.
    handoff = _read_handoff(data.handoff_token, customer) if data.handoff_token else None
    if handoff is not None:
        existing = _ticket_for_handoff(db, handoff.handoff_id)
        if existing is not None:
            return existing  # the same handoff sent twice (double click, retry): one ticket
    if data.category_id is not None:
        _check_category(db, data.category_id)
    ticket = Ticket(
        title=data.title,
        description=data.description,
        category_id=data.category_id,
        customer_id=customer.id,
        handoff_id=handoff.handoff_id if handoff else None,
        ai_handoff=handoff.ticket_context() if handoff else None,
    )
    db.add(ticket)
    try:
        db.commit()
    except IntegrityError:
        # Two copies of one handoff arrived at the same moment: the unique handoff_id let
        # only one in. Return that one instead of failing.
        db.rollback()
        existing = _ticket_for_handoff(db, handoff.handoff_id) if handoff else None
        if existing is None:
            raise
        return existing
    db.refresh(ticket)
    return ticket


def _read_handoff(token: str, customer: User) -> handoff_service.Handoff:
    try:
        return handoff_service.read_token(token, customer)
    except HandoffError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error


def _ticket_for_handoff(db: Session, handoff_id: str) -> Ticket | None:
    return db.scalar(select(Ticket).where(Ticket.handoff_id == handoff_id))


def list_tickets(
    db: Session,
    user: User,
    status_filter: TicketStatus | None = None,
    priority: Priority | None = None,
    unassigned: bool | None = None,
) -> list[Ticket]:
    stmt = select(Ticket)

    # The role decides which tickets are even candidates.
    if user.role == Role.CUSTOMER:
        stmt = stmt.where(Ticket.customer_id == user.id)
    elif user.role == Role.AGENT:
        if unassigned:
            stmt = stmt.where(Ticket.assigned_agent_id.is_(None))
        else:
            stmt = stmt.where(Ticket.assigned_agent_id == _agent_id(user))
    elif unassigned:  # admin
        stmt = stmt.where(Ticket.assigned_agent_id.is_(None))

    if status_filter is not None:
        stmt = stmt.where(Ticket.status == status_filter)
    if priority is not None:
        stmt = stmt.where(Ticket.priority == priority)

    stmt = stmt.order_by(Ticket.created_at.desc(), Ticket.id.desc())
    return list(db.scalars(stmt).all())


def add_message(db: Session, user: User, ticket: Ticket, text: str) -> TicketMessage:
    is_customer = user.role == Role.CUSTOMER
    if not is_customer:
        _require_manage(user, ticket)
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This ticket is closed")

    message = TicketMessage(ticket_id=ticket.id, sender_id=user.id, message=text)
    db.add(message)

    # Small workflow automation: keep the status in step with who is speaking.
    if is_customer and ticket.status == TicketStatus.WAITING_FOR_CUSTOMER:
        ticket.status = TicketStatus.IN_PROGRESS
    elif not is_customer and ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.IN_PROGRESS
    ticket.updated_at = utcnow()

    db.commit()
    db.refresh(message)
    return message


def update_ticket(db: Session, user: User, ticket: Ticket, data: TicketUpdate) -> Ticket:
    _require_manage(user, ticket)
    if data.category_id is not None:
        _check_category(db, data.category_id)
        ticket.category_id = data.category_id
    if data.priority is not None:
        ticket.priority = data.priority
    if data.status is not None:
        _change_status(ticket, data.status)
    db.commit()
    db.refresh(ticket)
    return ticket


def assign_ticket(db: Session, user: User, ticket: Ticket, agent_id: int) -> Ticket:
    """Admin can assign anywhere. An agent can claim an unassigned ticket, or hand over their own."""
    agent = db.get(Agent, agent_id)
    if agent is None or not agent.user.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "This ticket is closed")

    if user.role == Role.AGENT:
        claiming = ticket.assigned_agent_id is None and agent_id == _agent_id(user)
        handing_over = ticket.assigned_agent_id == _agent_id(user)
        if not (claiming or handing_over):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Agents can only claim unassigned tickets or reassign their own tickets",
            )

    ticket.assigned_agent_id = agent_id
    db.commit()
    db.refresh(ticket)
    return ticket


def escalate_ticket(db: Session, user: User, ticket: Ticket, data: EscalateRequest) -> Ticket:
    _require_manage(user, ticket)
    _change_status(ticket, TicketStatus.ESCALATED)
    db.add(TicketMessage(ticket_id=ticket.id, sender_id=user.id, message=f"[Escalated] {data.reason}"))
    ticket.updated_at = utcnow()
    db.commit()
    db.refresh(ticket)
    return ticket
