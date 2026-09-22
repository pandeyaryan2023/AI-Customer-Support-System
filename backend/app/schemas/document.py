from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models import DocumentStatus, IndexStatus
from app.schemas.user import UserBrief


class DocumentOut(BaseModel):
    """What the API returns about a document. The stored filename is internal and not exposed.

    The extracted text itself is left out on purpose: lists stay small.
    It has its own endpoint, GET /admin/documents/{id}/text.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by: UserBrief
    created_at: datetime
    status: DocumentStatus
    page_count: Optional[int]
    char_count: Optional[int]
    extraction_error: Optional[str]
    index_status: IndexStatus
    chunk_count: Optional[int]
    index_error: Optional[str]


class ChunkOut(BaseModel):
    """One chunk, for checking what was stored. The full vector is not sent: only its
    length and its first few numbers, which is enough to see that it exists and is sane."""

    model_config = ConfigDict(from_attributes=True)

    chunk_index: int
    text: str
    word_count: int
    embedding_model: str
    embedding: list[float] = Field(exclude=True)

    @computed_field
    @property
    def embedding_dimension(self) -> int:
        return len(self.embedding)

    @computed_field
    @property
    def embedding_preview(self) -> list[float]:
        return self.embedding[:8]


class DocumentTextOut(BaseModel):
    """One document's extracted text."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    page_count: Optional[int]
    char_count: int
    extracted_text: str
