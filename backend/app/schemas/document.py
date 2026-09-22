from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserBrief


class DocumentOut(BaseModel):
    """What the API returns about a document. The stored filename is internal and not exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    original_filename: str
    content_type: str
    size_bytes: int
    uploaded_by: UserBrief
    created_at: datetime
