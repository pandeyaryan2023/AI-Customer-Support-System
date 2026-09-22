"""Phase 5: answer a customer's question from the knowledge base (RAG).

    question -> Phase 4 search -> nothing relevant?  -> "not enough information" (no model call)
                               -> relevant chunks    -> cleaned context -> Llama 3.2
                               -> reply checked      -> grounded answer + its sources

The model only ever writes from retrieved company text. Whenever that is not possible
(nothing found, the model declines, or its reply cannot be trusted) the customer gets
the same honest "not enough information" reply and no sources.
"""
import logging
from dataclasses import dataclass, field
from enum import StrEnum

from sqlalchemy.orm import Session

from app.services import llm_client, rag_prompt, search_service
from app.services.llm_client import LLMError
from app.services.search_service import SearchOutcome, SearchScope, SearchUnavailable

logger = logging.getLogger(__name__)

NOT_ENOUGH_INFORMATION_REPLY = (
    "I couldn't find enough information in the company's knowledge base to answer that accurately."
)


class AssistantUnavailable(Exception):
    """Search or the model is down. The message is for logs, not for customers."""


class AnswerStatus(StrEnum):
    ANSWERED = "ANSWERED"
    NOT_ENOUGH_INFORMATION = "NOT_ENOUGH_INFORMATION"


@dataclass(frozen=True)
class Source:
    document_title: str
    chunk_index: int
    similarity: float


@dataclass(frozen=True)
class Answer:
    status: AnswerStatus
    answer: str
    sources: list[Source]
    model: str | None  # None when the model was not asked at all
    reason: str        # why this outcome; for logs and tests, not shown to customers
    # Articles the model read but could not answer from. For a human agent after a
    # handoff; never shown to the customer as the source of an answer.
    considered_sources: list[Source] = field(default_factory=list)


def answer_question(db: Session, question: str, scope: SearchScope) -> Answer:
    # 1. Retrieval, reused from Phase 4 unchanged.
    try:
        found = search_service.search(db, question, scope)
    except SearchUnavailable as error:
        raise AssistantUnavailable(f"search failed: {error}") from error
    if found.outcome != SearchOutcome.FOUND:
        return _not_enough(found.outcome.value)  # nothing relevant: the model is NOT called

    # 2. The context the model will read (instruction-like sentences removed).
    context = rag_prompt.select_context(found.results)
    if not context:
        return _not_enough("NO_USABLE_CONTEXT")
    messages = rag_prompt.build_messages(question, context)

    # 3. Generation.
    try:
        reply = llm_client.chat(messages)
    except LLMError as error:
        raise AssistantUnavailable(f"model failed: {error}") from error

    # 4. Only a reply that stays within the given text is passed on.
    sources = [Source(c.document_title, c.chunk_index, c.similarity) for c in context]
    if rag_prompt.is_refusal(reply.text):
        return _not_enough("MODEL_DECLINED", reply.model, sources)
    unsupported = rag_prompt.unsupported_numbers(reply.text, messages[1]["content"])
    if unsupported:
        logger.warning("Answer rejected: numbers %s are not in the knowledge or question", unsupported)
        return _not_enough("UNSUPPORTED_NUMBERS", reply.model, sources)

    return Answer(AnswerStatus.ANSWERED, reply.text, sources, reply.model, "ANSWERED")


def _not_enough(reason: str, model: str | None = None, considered: list[Source] | None = None) -> Answer:
    logger.info("No answer given (%s)", reason)
    return Answer(AnswerStatus.NOT_ENOUGH_INFORMATION, NOT_ENOUGH_INFORMATION_REPLY, [], model, reason,
                  considered or [])
