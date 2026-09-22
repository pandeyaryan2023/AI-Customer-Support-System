from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import StringConstraints

from app.api.deps import DbSession, require_roles
from app.models import Role, User
from app.schemas.document import DocumentOut
from app.services import document_service

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
    """Upload a document. Sent as multipart/form-data with two parts: `title` and `file`."""
    return document_service.save_document(db, admin, title, file)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: DbSession):
    return document_service.list_documents(db)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: int, db: DbSession):
    """Remove a document and its file, so an outdated policy can no longer be used."""
    document_service.delete_document(db, document_id)
