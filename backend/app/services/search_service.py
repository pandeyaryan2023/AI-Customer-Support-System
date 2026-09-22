"""Phase 4: semantic search over the knowledge base. Retrieval only: no answer is generated.

    question -> query vector (Ollama) -> cosine similarity with every searchable chunk
             -> rank, highest first -> keep scores >= threshold -> at most top_k results

Three different "nothing" outcomes are kept apart, because Phase 5 must treat them
differently: an empty knowledge base, no relevant chunk, and search being broken
(SearchUnavailable). A broken search is never reported as "no results".
"""
import logging
from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document, DocumentChunk, IndexStatus, User
from app.services import embedding_client
from app.services.embedding_client import EmbeddingError
from app.services.vector_math import cosine_similarities, rank, valid_rows

logger = logging.getLogger(__name__)


class SearchUnavailable(Exception):
    """Search could not run: Ollama or the database failed. The message says why."""


class SearchOutcome(StrEnum):
    FOUND = "FOUND"
    NO_MATCH = "NO_MATCH"                          # nothing reached the threshold
    NO_INDEXED_DOCUMENTS = "NO_INDEXED_DOCUMENTS"  # there is nothing to search yet


MESSAGES = {
    SearchOutcome.FOUND: "Relevant knowledge found",
    SearchOutcome.NO_MATCH: "No relevant knowledge found",
    SearchOutcome.NO_INDEXED_DOCUMENTS: "The knowledge base has no indexed documents",
}


@dataclass(frozen=True)
class SearchScope:
    """Which knowledge base a search may read: one business's.

    Always built on the server from the signed-in user (see scope_for), never from
    request data, so no request can make a search read another business's chunks.
    """

    business_id: int


def scope_for(user: User) -> SearchScope:
    return SearchScope(business_id=user.business_id)


@dataclass(frozen=True)
class SearchHit:
    chunk_id: int
    document_id: int
    document_title: str
    chunk_index: int
    text: str
    similarity: float


@dataclass(frozen=True)
class SearchResult:
    query: str
    outcome: SearchOutcome
    results: list[SearchHit]
    top_k: int
    threshold: float
    chunks_searched: int = 0
    chunks_skipped: int = 0
    best_similarity: float | None = None  # the highest score seen, even below the threshold
    embedding_model: str = field(default_factory=lambda: settings.embedding_model)

    @property
    def message(self) -> str:
        return MESSAGES[self.outcome]


def search(db: Session, question: str, scope: SearchScope,
           top_k: int | None = None, threshold: float | None = None) -> SearchResult:
    top_k = settings.search_top_k if top_k is None else top_k
    threshold = settings.search_similarity_threshold if threshold is None else threshold

    # 1. The chunks that may be searched. Nothing indexed: no need to ask Ollama at all.
    candidates = _load_candidates(db, scope)
    if not candidates:
        return SearchResult(question, SearchOutcome.NO_INDEXED_DOCUMENTS, [], top_k, threshold)

    # 2. Their vectors as one matrix. A damaged vector is left out and counted, not hidden.
    matrix, kept = valid_rows([c.embedding for c in candidates], settings.embedding_dimension)
    skipped = len(candidates) - len(kept)
    if skipped:
        logger.warning("Search skipped %d chunk(s) with an unusable embedding", skipped)
    if not kept:
        raise SearchUnavailable("None of the stored embeddings can be used. Re-index the documents")

    # 3. Compare the question with every chunk, then rank and apply the threshold.
    scores = cosine_similarities(_embed_question(question), matrix)
    hits = [_hit(candidates[kept[p]], scores[p]) for p in rank(scores, top_k, threshold)]
    return SearchResult(
        query=question,
        outcome=SearchOutcome.FOUND if hits else SearchOutcome.NO_MATCH,
        results=hits,
        top_k=top_k,
        threshold=threshold,
        chunks_searched=len(kept),
        chunks_skipped=skipped,
        best_similarity=round(float(scores.max()), 4),
    )


def _load_candidates(db: Session, scope: SearchScope) -> list:
    """Every searchable chunk, with only the columns search needs, in one query.

    Only INDEXED documents count, and only vectors made by the current model: vectors
    from another model live on a different "map of meaning" and cannot be compared.
    The documents' full extracted text is never loaded.
    """
    stmt = (
        select(DocumentChunk.id, DocumentChunk.document_id, DocumentChunk.chunk_index,
               DocumentChunk.text, DocumentChunk.embedding, Document.title)
        .join(Document, Document.id == DocumentChunk.document_id)
        .where(Document.business_id == scope.business_id)  # this business's knowledge only
        .where(Document.index_status == IndexStatus.INDEXED)
        .where(DocumentChunk.embedding_model == settings.embedding_model)
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    )
    try:
        return list(db.execute(stmt).all())
    except SQLAlchemyError as error:
        logger.exception("Could not load chunks for search")
        raise SearchUnavailable("The knowledge base could not be read") from error


def _embed_question(question: str) -> np.ndarray:
    try:
        vector = np.asarray(embedding_client.embed_query(question), dtype=np.float64)
    except EmbeddingError as error:
        raise SearchUnavailable(str(error)) from error
    if not np.any(vector):
        raise SearchUnavailable("The embedding model returned an all-zero vector for the question")
    return vector


def _hit(row, score: float) -> SearchHit:
    return SearchHit(
        chunk_id=row.id,
        document_id=row.document_id,
        document_title=row.title,
        chunk_index=row.chunk_index,
        text=row.text,
        similarity=round(float(score), 4),
    )
