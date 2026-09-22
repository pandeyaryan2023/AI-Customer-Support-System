from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, computed_field, model_validator

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
    # Set by "Talk to Human Support" after the AI assistant could not answer (POST /ai/ask).
    # The server checks it and takes the AI context from it, never from the form.
    handoff_token: Optional[str] = Field(default=None, max_length=8192)


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


class AIHandoffSource(BaseModel):
    document_title: str
    chunk_index: int
    similarity: float


class AIHandoffOut(BaseModel):
    """What the AI assistant knew when the customer asked for a human."""

    question: str                 # exactly what the customer asked the assistant
    ai_status: str                # e.g. NOT_ENOUGH_INFORMATION
    reason: str                   # why the assistant stopped, in plain words
    sources: list[AIHandoffSource]  # articles it looked at (no article text)
    asked_at: datetime


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
    ai_handoff: Optional[AIHandoffOut] = None  # null unless raised through "Talk to Human Support"

    @computed_field
    @property
    def from_ai_handoff(self) -> bool:
        return self.ai_handoff is not None


class TicketDetail(TicketOut):
    messages: list[MessageOut]
