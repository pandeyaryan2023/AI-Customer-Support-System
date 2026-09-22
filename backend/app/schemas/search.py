from typing import Annotated, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.services.search_service import SearchOutcome


class SearchRequest(BaseModel):
    """A search question. top_k and threshold are optional; the configured defaults apply."""

    # Only these three fields are accepted. Anything else (a business id, a list of
    # document ids...) is rejected, so a client can never choose what it searches.
    model_config = ConfigDict(extra="forbid")

    query: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=500)]
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    threshold: Optional[float] = Field(default=None, ge=0, le=1)


class SearchHitOut(BaseModel):
    """One matching chunk: enough for Phase 5 to quote it. No file names, paths or vectors."""

    model_config = ConfigDict(from_attributes=True)

    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    text: str
    similarity: float


class SearchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query: str
    outcome: SearchOutcome
    message: str
    embedding_model: str
    top_k: int
    threshold: float
    chunks_searched: int
    chunks_skipped: int
    best_similarity: Optional[float]
    results: list[SearchHitOut]  # highest similarity first; empty unless outcome is FOUND
