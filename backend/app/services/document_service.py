import logging
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document, DocumentChunk, DocumentStatus, User
from app.services import text_extraction
from app.services.text_extraction import ExtractionError

logger = logging.getLogger(__name__)

# The ONLY file types accepted. The extension decides the type we store,
# never the Content-Type header, which the uploader controls.
ALLOWED_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


def _storage_dir() -> Path:
    """Read at call time, so tests can point it at a temporary folder."""
    folder = Path(settings.storage_dir)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def storage_path(document: Document) -> Path:
    """Where this document's bytes live on disk. Extraction reads from here."""
    return Path(settings.storage_dir) / document.stored_filename


def _display_name(filename: str | None) -> str:
    """Keep only the last part of the uploader's filename, for showing to people.

    Some clients send a full path ("C:\\Users\\asha\\refund.pdf" or "../../x.pdf").
    Splitting on both slash types strips every directory part on any operating system.
    """
    name = re.split(r"[\\/]", filename or "")[-1].strip()
    return name[:255]


def _check_content(extension: str, data: bytes) -> None:
    """The extension is a claim. Check the bytes actually back it up."""
    if extension == ".pdf" and not data.startswith(b"%PDF-"):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "This file is not a valid PDF")
    if extension == ".txt":
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Text files must be UTF-8 encoded")
        if b"\x00" in data:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "This does not look like a text file")


def save_document(db: Session, admin: User, title: str, upload: UploadFile) -> Document:
    original = _display_name(upload.filename)
    extension = Path(original).suffix.lower()

    # 1. Type: is the extension on the allow-list?
    if extension not in ALLOWED_TYPES:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            f"Only {', '.join(sorted(ALLOWED_TYPES))} files can be uploaded",
        )

    # 2. Size: read one byte past the limit, so an oversized file is detected
    #    without ever reading all of it into memory.
    limit = settings.max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE,
            f"File is larger than the {settings.max_upload_mb} MB limit",
        )
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The file is empty")

    # 3. Content: do the bytes match the extension?
    _check_content(extension, data)

    # 4. Store under a name WE choose. The uploader's filename never reaches the path,
    #    so "../../anything" cannot escape the storage folder.
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    path = _storage_dir() / stored_filename
    path.write_bytes(data)

    document = Document(
        title=title,
        original_filename=original,
        stored_filename=stored_filename,
        content_type=ALLOWED_TYPES[extension],
        size_bytes=len(data),
        uploaded_by_id=admin.id,
    )
    db.add(document)
    try:
        db.commit()
    except Exception:
        # The row failed, so don't leave an orphaned file behind.
        db.rollback()
        path.unlink(missing_ok=True)
        raise
    db.refresh(document)

    # The document is saved (status PENDING) BEFORE extraction runs. Whatever happens
    # next, the original is kept and can be extracted again later.
    return extract_document(db, document)


def extract_document(db: Session, document: Document) -> Document:
    """Extract a stored document's text and record the result.

    A bad file never raises: it ends as FAILED with a reason, and the file itself is
    left untouched. Running it again (a retry) simply overwrites the previous result.
    """
    try:
        result = text_extraction.extract_text(storage_path(document))
    except ExtractionError as error:
        _record_failure(document, str(error))
    except Exception:
        # Anything the extractor did not foresee. One strange file must not turn
        # into a server error; the full traceback goes to the server log instead.
        logger.exception("Unexpected error extracting text from document %s", document.id)
        _record_failure(document, "Unexpected error while reading the file")
    else:
        document.status = DocumentStatus.EXTRACTED
        document.extracted_text = result.text
        document.page_count = result.page_count
        document.char_count = len(result.text)
        document.extraction_error = None
    db.commit()
    db.refresh(document)
    return document


def _record_failure(document: Document, reason: str) -> None:
    document.status = DocumentStatus.FAILED
    document.extracted_text = None
    document.page_count = None
    document.char_count = None
    document.extraction_error = reason[:300]


def get_document(db: Session, document_id: int) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document


def get_text(db: Session, document_id: int) -> Document:
    document = get_document(db, document_id)
    if document.status != DocumentStatus.EXTRACTED:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"This document has no extracted text (status {document.status})",
        )
    return document


def list_documents(db: Session) -> list[Document]:
    stmt = select(Document).order_by(Document.created_at.desc(), Document.id.desc())
    return list(db.scalars(stmt).all())


def delete_document(db: Session, document_id: int) -> None:
    document = get_document(db, document_id)
    path = storage_path(document)
    db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))
    db.delete(document)
    db.commit()
    # Remove the file only after the row is gone. If this step failed we'd be left
    # with a stray file, which is harmless — a row pointing at a missing file is not.
    path.unlink(missing_ok=True)
