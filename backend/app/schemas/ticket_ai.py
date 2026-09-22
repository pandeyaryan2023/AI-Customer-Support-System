from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.models import Priority


class CategorySuggestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int  # an existing, active category: the agent can apply it with PATCH /tickets/{id}
    name: str


class TicketAnalysisOut(BaseModel):
    """AI suggestions for the agent. Nothing here has been applied to the ticket or sent.

    Each field is null when the model gave no usable value for it.
    """

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    category: Optional[CategorySuggestionOut]
    priority: Optional[Priority]
    sentiment: Optional[Literal["positive", "neutral", "negative"]]
    summary: Optional[Annotated[str, StringConstraints(min_length=1, max_length=600)]]
    suggested_reply: Optional[Annotated[str, StringConstraints(min_length=1, max_length=2000)]]
    model: str
    # True when the ticket contained text addressed to the AI ("ignore your instructions..."),
    # which was left out of the analysis. The agent should read the ticket itself.
    ignored_instructions: bool
