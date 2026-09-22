"""Turn a stored PDF or text file into plain text.

Only file work happens here, no database: given a path, return the text or raise
ExtractionError with a reason an admin can understand.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError


class ExtractionError(Exception):
    """The file's text cannot be extracted. The message is shown to the admin."""


@dataclass
class ExtractedText:
    text: str
    page_count: int | None  # None for text files, which have no pages


def extract_text(path: Path) -> ExtractedText:
    if not path.is_file():
        raise ExtractionError("The stored file is missing")
    extension = path.suffix.lower()
    if extension == ".pdf":
        return _from_pdf(path)
    if extension == ".txt":
        return ExtractedText(_from_txt(path), page_count=None)
    raise ExtractionError(f"Text cannot be extracted from {extension or 'this'} files")


def _from_pdf(path: Path) -> ExtractedText:
    # pypdf fails at different moments for different damage: some files fail on opening,
    # others only when a page is read. So both steps sit inside the same try.
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ExtractionError("The PDF is password-protected")
        pages = [page.extract_text() or "" for page in reader.pages]
    except PyPdfError as error:
        raise ExtractionError("The PDF is damaged and could not be read") from error

    # These two open without any error, so they must be checked for explicitly.
    if not pages:
        raise ExtractionError("The PDF has no pages")
    text = clean_text("\n\n".join(pages))
    if not text:
        raise ExtractionError(
            "No text found. The PDF may be a scanned image, which needs OCR (not supported)"
        )
    return ExtractedText(text, page_count=len(pages))


def _from_txt(path: Path) -> str:
    data = path.read_bytes()
    try:
        text = data.decode("utf-8-sig")  # "-sig" drops the invisible BOM some editors add
    except UnicodeDecodeError as error:
        raise ExtractionError("The text file is not valid UTF-8") from error
    if "\x00" in text:
        raise ExtractionError("This does not look like a text file")
    text = clean_text(text)
    if not text:
        raise ExtractionError("The text file contains no text")
    return text


def clean_text(text: str) -> str:
    """Tidy extracted text without changing what it says."""
    text = text.replace("\x00", "")  # PostgreSQL cannot store NUL characters in text
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)  # at most one blank line in a row
    return text.strip()
