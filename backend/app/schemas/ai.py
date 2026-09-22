from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.services.rag_service import AnswerStatus


class AskRequest(BaseModel):
    # Only the question is accepted: a client cannot pass rules, context or a model name.
    model_config = ConfigDict(extra="forbid")

    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]


class SourceOut(BaseModel):
    """Where an answer came from. No file names, paths, chunk text or vectors."""

    model_config = ConfigDict(from_attributes=True)

    document_title: str
    chunk_index: int
    similarity: float


class AskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: AnswerStatus  # ANSWERED or NOT_ENOUGH_INFORMATION
    answer: str
    sources: list[SourceOut]  # empty unless ANSWERED
    model: Optional[str]      # the model that wrote the answer; null if none was asked
    # Only when NOT_ENOUGH_INFORMATION: send it with a new ticket (POST /tickets) to hand
    # the question to a human. Signed by the server, tied to this customer, short-lived.
    handoff_token: Optional[str] = None
