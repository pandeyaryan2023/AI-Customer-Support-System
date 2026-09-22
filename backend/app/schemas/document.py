from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.models import DocumentStatus
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


class DocumentTextOut(BaseModel):
    """One document's extracted text."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    page_count: Optional[int]
    char_count: int
    extracted_text: str
