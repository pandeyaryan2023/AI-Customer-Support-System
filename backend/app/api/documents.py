from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import StringConstraints

from app.api.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.document import ChunkOut, DocumentOut, DocumentTextOut
from app.services import document_service, indexing_service

# The knowledge base is managed by admins only, like everything else under /admin.
router = APIRouter(
    prefix="/admin/documents",
    tags=["Knowledge base"],
    dependencies=[Depends(require_roles(Role.ADMIN))],
)

Admin = Annotated[User, Depends(require_roles(Role.ADMIN))]
DocTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    db: DbSession,
    admin: Admin,
    title: Annotated[DocTitle, Form()],
    file: Annotated[UploadFile, File(description="A PDF or UTF-8 text file")],
):
    """Upload a document. Sent as multipart/form-data with two parts: `title` and `file`.

    Its text is extracted straight away, then chunked and embedded. If either step fails
    the upload still succeeds: the document is kept, and `status` / `index_status` say
    FAILED with the reason in `extraction_error` / `index_error`.
    """
    document = document_service.save_document(db, admin, title, file)  # stored + extracted
    return indexing_service.refresh_index(db, document)                # chunked + embedded


@router.get("", response_model=list[DocumentOut])
def list_documents(db: DbSession):
    return document_service.list_documents(db)


@router.post("/{document_id}/extract", response_model=DocumentOut)
def extract_document(document_id: int, db: DbSession):
    """Extract (or re-extract) the text of a stored document.

    Used for documents uploaded before text extraction existed, and to retry a failure.
    The chunks are then rebuilt from the new text.
    """
    document = document_service.get_document(db, document_id)
    document = document_service.extract_document(db, document)
    return indexing_service.refresh_index(db, document)


@router.get("/{document_id}/text", response_model=DocumentTextOut)
def get_document_text(document_id: int, db: DbSession):
    """The extracted text of one document. 409 if it has none (PENDING or FAILED)."""
    return document_service.get_text(db, document_id)


@router.post("/{document_id}/index", response_model=DocumentOut)
def index_document(document_id: int, db: DbSession):
    """Chunk and embed the extracted text again, replacing any previous chunks.

    Used to retry after Ollama was unavailable. 409 if the text is not extracted.
    """
    return indexing_service.reindex(db, document_id)


@router.get("/{document_id}/chunks", response_model=list[ChunkOut])
def list_document_chunks(document_id: int, db: DbSession):
    """The stored chunks, in order, with each embedding's length and first numbers."""
    return indexing_service.list_chunks(db, document_id)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: DbSession):
    """Remove a document and its file, so an outdated policy can no longer be used."""
    document_service.delete_document(db, document_id)
