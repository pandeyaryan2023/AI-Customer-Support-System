from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Agent, Category, Priority, Role, Ticket, TicketStatus, User
from app.schemas.admin import Stats
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.schemas.user import AgentCreate
from app.services import user_service


# Every function here works inside ONE business: an admin manages their own business only.


def list_users(db: Session, business_id: int, role: Role | None = None) -> list[User]:
    stmt = select(User).where(User.business_id == business_id).order_by(User.id)
    if role is not None:
        stmt = stmt.where(User.role == role)
    return list(db.scalars(stmt).all())


def set_user_active(db: Session, admin: User, user_id: int, is_active: bool) -> User:
    user = db.get(User, user_id)
    if user is None or user.business_id != admin.business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == admin.id and not is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot disable your own account")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def create_agent(db: Session, data: AgentCreate, business_id: int) -> Agent:
    # User row + Agent row are saved in ONE transaction: both succeed or neither does.
    user = user_service.create_user(db, data, Role.AGENT, business_id)
    agent = Agent(user_id=user.id, department=data.department)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def list_agents(db: Session, business_id: int) -> list[Agent]:
    stmt = select(Agent).join(User, Agent.user_id == User.id).where(User.business_id == business_id)
    return list(db.scalars(stmt.order_by(Agent.id)).all())


def list_categories(db: Session, business_id: int, only_active: bool = False) -> list[Category]:
    stmt = select(Category).where(Category.business_id == business_id).order_by(Category.name)
    if only_active:
        stmt = stmt.where(Category.is_active.is_(True))
    return list(db.scalars(stmt).all())


def _name_taken(db: Session, business_id: int, name: str, exclude_id: int | None = None) -> bool:
    stmt = select(Category).where(Category.business_id == business_id,
                                  func.lower(Category.name) == name.lower())
    if exclude_id is not None:
        stmt = stmt.where(Category.id != exclude_id)
    return db.scalar(stmt) is not None


def create_category(db: Session, data: CategoryCreate, business_id: int) -> Category:
    if _name_taken(db, business_id, data.name):
        raise HTTPException(status.HTTP_409_CONFLICT, "A category with this name already exists")
    category = Category(name=data.name, description=data.description, business_id=business_id)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, business_id: int, category_id: int, data: CategoryUpdate) -> Category:
    category = db.get(Category, category_id)
    if category is None or category.business_id != business_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Category not found")
    if data.name is not None:
        if _name_taken(db, business_id, data.name, exclude_id=category.id):
            raise HTTPException(status.HTTP_409_CONFLICT, "A category with this name already exists")
        category.name = data.name
    if data.description is not None:
        category.description = data.description
    if data.is_active is not None:
        category.is_active = data.is_active
    db.commit()
    db.refresh(category)
    return category


def get_stats(db: Session, business_id: int) -> Stats:
    mine = Ticket.business_id == business_id
    by_status = {s.value: 0 for s in TicketStatus}
    for value, count in db.execute(select(Ticket.status, func.count()).where(mine).group_by(Ticket.status)):
        by_status[value.value] = count

    by_priority = {p.value: 0 for p in Priority}
    for value, count in db.execute(select(Ticket.priority, func.count()).where(mine).group_by(Ticket.priority)):
        by_priority[value.value] = count

    users_by_role = {r.value: 0 for r in Role}
    for value, count in db.execute(select(User.role, func.count())
                                   .where(User.business_id == business_id).group_by(User.role)):
        users_by_role[value.value] = count

    unassigned = db.scalar(select(func.count()).select_from(Ticket)
                           .where(mine, Ticket.assigned_agent_id.is_(None)))
    return Stats(
        total_tickets=sum(by_status.values()),
        unassigned_tickets=unassigned or 0,
        tickets_by_status=by_status,
        tickets_by_priority=by_priority,
        users_by_role=users_by_role,
    )
