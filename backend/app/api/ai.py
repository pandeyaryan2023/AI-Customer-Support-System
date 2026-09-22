import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.ai import AskOut, AskRequest
from app.services import rag_service, search_service
from app.services.rag_service import AssistantUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI assistant"])

# Customers ask questions; admins may too, to check what customers will be told.
Asker = Annotated[User, Depends(require_roles(Role.CUSTOMER, Role.ADMIN))]


@router.post("/ask", response_model=AskOut)
def ask(body: AskRequest, db: DbSession, user: Asker):
    """Answer a question from the company knowledge base only.

    `status` is ANSWERED (with the sources the answer is based on) or
    NOT_ENOUGH_INFORMATION (no sources; the model was not trusted to answer).
    503 if the assistant is unavailable; the detail never includes internal errors.
    """
    scope = search_service.scope_for(user)  # decided by the server, not by the request
    try:
        return rag_service.answer_question(db, body.question, scope)
    except AssistantUnavailable as error:
        logger.error("AI assistant unavailable: %s", error)  # the real reason stays in the log
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            "The AI assistant is unavailable right now. Please try again later.")
