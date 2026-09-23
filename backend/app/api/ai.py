import logging
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.ai import AskOut, AskRequest
from app.services import assistant_service, handoff_service, search_service
from app.services.rag_service import AssistantUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI assistant"])

# Customers ask questions; admins may too, to check what customers will be told.
Asker = Annotated[User, Depends(require_roles(Role.CUSTOMER, Role.ADMIN))]


@router.post("/ask", response_model=AskOut)
def ask(body: AskRequest, db: DbSession, user: Asker):
    """Answer a customer's message.

    The message is first sorted into an `intent`: COMPANY_KNOWLEDGE is answered from the
    knowledge base as before (grounded, with its sources), GENERAL gets a general answer with
    no company facts and no sources, COMPLAINT gets an acknowledgement, and HUMAN_HANDOFF a
    pointer to a person. No ticket is ever created here.

    `status` is ANSWERED (with the sources the answer is based on) or
    NOT_ENOUGH_INFORMATION (the assistant is not answering). The second comes with a
    `handoff_token`: no ticket is created unless the customer chooses one.
    503 if the assistant is unavailable; the detail never includes internal errors.
    """
    scope = search_service.scope_for(user)  # decided by the server, not by the request
    try:
        answer = assistant_service.answer(db, body.question, scope)
    except AssistantUnavailable as error:
        logger.error("AI assistant unavailable: %s", error)  # the real reason stays in the log
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The AI assistant is unavailable right now. Please try again later.")
    return AskOut(
        intent=answer.intent,
        status=answer.status,
        answer=answer.answer,
        sources=[asdict(source) for source in answer.sources],
        model=answer.model,
        # Only customers raise tickets, so only they are offered a handoff.
        handoff_token=handoff_service.issue_token(user, body.question, answer)
        if user.role == Role.CUSTOMER else None,
    )
