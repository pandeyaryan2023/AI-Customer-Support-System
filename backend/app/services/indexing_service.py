"""Phase 3: turn a document's extracted text into chunks with embeddings.

    extracted text -> clean -> chunks -> embeddings (Ollama) -> document_chunks rows

Rule kept at all times: a document has chunks if and only if it is INDEXED. So a later
search can trust every chunk it finds, and a failed or outdated document leaves none behind.
"""
import logging

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document, DocumentChunk, DocumentStatus, IndexStatus
from app.services import document_service, embedding_client
from app.services.chunking import Chunk, chunk_text
from app.services.embedding_client import EmbeddingError
from app.services.text_cleaning import normalize_text

logger = logging.getLogger(__name__)


class IndexingError(Exception):
    """The document cannot be indexed. The message is shown to the admin."""


def build_chunks(text: str) -> list[Chunk]:
    """Clean, then chunk. No database and no Ollama, so it is easy to test."""
    return chunk_text(normalize_text(text), settings.chunk_words, settings.chunk_overlap_words)


def refresh_index(db: Session, document: Document) -> Document:
    """Bring the chunks in line with the document's current text. Runs after every extraction."""
    if document.status == DocumentStatus.EXTRACTED:
        return index_document(db, document)
    return _replace_chunks(db, document, [], IndexStatus.NOT_INDEXED)  # no text, so no chunks


def reindex(db: Session, document_id: int) -> Document:
    """Run Phase 3 again for one document, e.g. after Ollama was not running."""
    document = document_service.get_document(db, document_id)
    if document.status != DocumentStatus.EXTRACTED:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "The document's text must be extracted before it can be indexed")
    return index_document(db, document)


def index_document(db: Session, document: Document) -> Document:
    # 1. All the slow, failure-prone work happens first, in memory. Nothing is written yet.
    try:
        rows = _build_rows(document)
    except (IndexingError, EmbeddingError) as error:
        return _replace_chunks(db, document, [], IndexStatus.FAILED, str(error))
    except Exception:
        # Anything unforeseen still ends as FAILED, never as a server error.
        logger.exception("Unexpected error indexing document %s", document.id)
        return _replace_chunks(db, document, [], IndexStatus.FAILED, "Unexpected error while indexing")

    # 2. Only when every chunk has a valid vector: swap old chunks for new in one transaction.
    return _replace_chunks(db, document, rows, IndexStatus.INDEXED)


def _build_rows(document: Document) -> list[DocumentChunk]:
    chunks = build_chunks(document.extracted_text or "")
    if not chunks:
        raise IndexingError("There is no text left to index after cleaning")
    vectors = embedding_client.embed_documents([chunk.text for chunk in chunks])
    return [
        DocumentChunk(
            document_id=document.id,
            chunk_index=chunk.index,
            text=chunk.text,
            word_count=chunk.word_count,
            embedding=vector,
            embedding_model=settings.embedding_model,
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]


def _replace_chunks(db: Session, document: Document, rows: list[DocumentChunk],
                    index_status: IndexStatus, error: str | None = None) -> Document:
    """Delete the document's old chunks, add the new ones and set its status: one commit.

    Re-running therefore replaces chunks instead of duplicating them. If the database
    fails half-way, the rollback leaves the previous chunks and status exactly as they were.
    """
    try:
        db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
        db.add_all(rows)
        document.index_status = index_status
        document.index_error = error[:300] if error else None
        document.chunk_count = len(rows) if index_status == IndexStatus.INDEXED else None
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(document)
    return document


def list_chunks(db: Session, document_id: int) -> list[DocumentChunk]:
    document_service.get_document(db, document_id)  # 404 if there is no such document
    stmt = (select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index))
    return list(db.scalars(stmt).all())
