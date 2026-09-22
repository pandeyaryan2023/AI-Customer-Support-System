from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.business import Business
from app.models.enums import Role


class User(Base):
    """Everyone who can log in: customers, agents and admins."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The business this person belongs to. It decides everything they can ever see.
    business_id: Mapped[int] = mapped_column(ForeignKey("businesses.id"), index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    # Unique across all businesses, so an email alone identifies the account (and its business).
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20), default=Role.CUSTOMER)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    business: Mapped[Business] = relationship()
    # Only users whose role is AGENT have an agent profile.
    agent_profile: Mapped[Optional["Agent"]] = relationship(back_populates="user", uselist=False)


class Agent(Base):
    """Extra information about a support agent (1-to-1 with a User)."""

    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    department: Mapped[Optional[str]] = mapped_column(String(100))

    user: Mapped["User"] = relationship(back_populates="agent_profile")
