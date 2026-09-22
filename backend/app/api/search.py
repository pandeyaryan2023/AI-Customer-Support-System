from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.search import SearchOut, SearchRequest
from app.services import search_service
from app.services.search_service import SearchUnavailable

# Admin-only for now: it is a tool for checking retrieval, not a customer-facing feature.
router = APIRouter(
    prefix="/admin/documents",
    tags=["Semantic search"],
    dependencies=[Depends(require_roles(Role.ADMIN))],
)

Admin = Annotated[User, Depends(require_roles(Role.ADMIN))]


@router.post("/search", response_model=SearchOut)
def search_knowledge_base(body: SearchRequest, db: DbSession, admin: Admin):
    """Find the knowledge-base chunks closest in meaning to a question.

    Retrieval only: no answer is generated. `outcome` is FOUND, NO_MATCH (nothing
    reached the threshold) or NO_INDEXED_DOCUMENTS. If Ollama or the database is
    unavailable the response is 503, never an empty result.
    """
    scope = search_service.scope_for(admin)  # decided by the server, not by the request
    try:
        return search_service.search(db, body.query, scope, top_k=body.top_k, threshold=body.threshold)
    except SearchUnavailable as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Search is unavailable: {error}")
