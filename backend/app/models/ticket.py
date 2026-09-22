from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import Priority, TicketStatus
from app.models.user import Agent, User


class Category(Base):
    """A complaint category such as Billing, Delivery or Technical Issue."""

    __tablename__ = "categories"
    # Names are unique within a business: two businesses can both have "Billing".
    __table_args__ = (UniqueConstraint("business_id", "name", name="uq_categories_business_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"))
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)


class Ticket(Base):
    """A customer complaint."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Always the customer's business. Stored on the ticket so every ticket query can filter on it.
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(
        Enum(TicketStatus, native_enum=False, length=30), default=TicketStatus.OPEN, index=True
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False, length=20), default=Priority.MEDIUM
    )
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"))
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    assigned_agent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("agents.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    # Set only when the customer chose human support after the AI assistant could not answer.
    # handoff_id is unique, so submitting the same handoff twice cannot create a second ticket.
    # ai_handoff is what the agent needs: the original question, why the AI stopped and which
    # articles it looked at. Never the prompt or the article text.
    handoff_id: Mapped[Optional[str]] = mapped_column(String(32), unique=True, index=True)
    ai_handoff: Mapped[Optional[dict]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))

    category: Mapped[Optional[Category]] = relationship()
    customer: Mapped[User] = relationship()
    assigned_agent: Mapped[Optional[Agent]] = relationship()
    messages: Mapped[list["TicketMessage"]] = relationship(
        back_populates="ticket", order_by="TicketMessage.id"
    )


class TicketMessage(Base):
    """One message in the conversation on a ticket."""

    __tablename__ = "ticket_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    ticket: Mapped[Ticket] = relationship(back_populates="messages")
    sender: Mapped[User] = relationship()
