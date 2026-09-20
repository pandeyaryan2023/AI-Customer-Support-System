from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

from app.models.enums import Priority, TicketStatus
from app.schemas.category import CategoryOut
from app.schemas.user import AgentBrief, UserBrief

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=5000)]
MessageText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)]


class TicketCreate(BaseModel):
    title: Title
    description: Description
    category_id: Optional[int] = None


class TicketUpdate(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[Priority] = None
    category_id: Optional[int] = None

    @model_validator(mode="after")
    def at_least_one_field(self):
        if self.status is None and self.priority is None and self.category_id is None:
            raise ValueError("Provide at least one of: status, priority, category_id")
        return self


class MessageCreate(BaseModel):
    message: MessageText


class AssignRequest(BaseModel):
    agent_id: int


class EscalateRequest(BaseModel):
    reason: Reason


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sender: UserBrief
    message: str
    created_at: datetime


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: TicketStatus
    priority: Priority
    category: Optional[CategoryOut]
    customer: UserBrief
    assigned_agent: Optional[AgentBrief]
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketOut):
    messages: list[MessageOut]
