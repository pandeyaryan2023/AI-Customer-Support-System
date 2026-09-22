from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import DocumentStatus
from app.models.user import User


class Document(Base):
    """A file in the knowledge base. The bytes live on disk; this row describes them."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    # What the uploader called the file. Shown to people, NEVER used to build a path.
    original_filename: Mapped[str] = mapped_column(String(255))
    # The name WE generated (random hex + extension). This is the file on disk.
    stored_filename: Mapped[str] = mapped_column(String(64), unique=True)
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Text extraction (Phase 2).
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, native_enum=False, length=20),
        default=DocumentStatus.PENDING,
        server_default=DocumentStatus.PENDING.value,
    )
    # deferred: loaded only when the code actually reads it, so listing documents
    # never pulls every document's full text out of the database.
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, deferred=True)
    page_count: Mapped[Optional[int]]  # PDFs only
    char_count: Mapped[Optional[int]]
    extraction_error: Mapped[Optional[str]] = mapped_column(String(300))

    uploaded_by: Mapped[User] = relationship()
