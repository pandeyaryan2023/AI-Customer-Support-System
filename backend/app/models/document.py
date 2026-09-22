from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, utcnow
from app.models.enums import DocumentStatus, IndexStatus
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

    # Chunking and embeddings (Phase 3).
    index_status: Mapped[IndexStatus] = mapped_column(
        Enum(IndexStatus, native_enum=False, length=20),
        default=IndexStatus.NOT_INDEXED,
        server_default=IndexStatus.NOT_INDEXED.value,
    )
    index_error: Mapped[Optional[str]] = mapped_column(String(300))
    chunk_count: Mapped[Optional[int]]

    uploaded_by: Mapped[User] = relationship()


class DocumentChunk(Base):
    """One piece of a document's text, with the embedding vector that describes its meaning."""

    __tablename__ = "document_chunks"
    # No document can have two "chunk 0"s: the database itself refuses duplicates.
    # The same constraint also indexes document_id, which every chunk query filters on.
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int]  # 0, 1, 2 ... in reading order
    text: Mapped[str] = mapped_column(Text)
    word_count: Mapped[int]
    # The vector: a JSON list of numbers (JSONB in PostgreSQL, plain JSON in the tests' SQLite).
    embedding: Mapped[list[float]] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    # Vectors from different models cannot be compared, so record which model made this one.
    embedding_model: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
