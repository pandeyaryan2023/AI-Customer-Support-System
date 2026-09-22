"""Phase 2: turning stored documents into text."""
import io

import pytest
from pypdf import PdfWriter

from app.core.config import settings
from app.models import Document, Role
from app.services import text_extraction
from app.services.text_extraction import ExtractionError, clean_text, extract_text

URL = "/admin/documents"
REFUND = "Customers can request a refund within 30 days of purchase."
CORRUPT_PDF = b"%PDF-1.7\nthis is not really a pdf at all"  # right header, broken body


def make_pdf(*pages: str) -> bytes:
    """A small, valid PDF built by hand: one line of plain ASCII text per page."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", "",
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {len(objects)} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"

    # The cross-reference table records where each object starts, in bytes.
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n{body}\nendobj\n".encode()
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    pdf += "".join(f"{offset:010d} 00000 n \n" for offset in offsets).encode()
    pdf += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(pdf)


def blank_pdf(pages: int = 1, password: str | None = None) -> bytes:
    """A valid PDF with empty pages, like a scan: no text layer at all."""
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    if password:
        writer.encrypt(password, algorithm="RC4-128")
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    """Every test gets its own empty storage folder, never the real one."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    return tmp_path


@pytest.fixture()
def admin(make_user):
    return make_user(Role.ADMIN, "admin@example.com")


def upload(client, admin, filename, content, title="Refund policy"):
    return client.post(URL, data={"title": title}, files={"file": (filename, content)}, headers=admin.headers)


def write(folder, name, data):
    path = folder / name
    path.write_bytes(data)
    return path


# ---------------------------------------------------------- the extractor on its own

def test_pdf_text_extracted_page_by_page(tmp_path):
    result = extract_text(write(tmp_path, "policy.pdf", make_pdf("Refund Policy", REFUND)))
    assert result.page_count == 2
    assert result.text == f"Refund Policy\n\n{REFUND}"  # pages separated by a blank line


def test_utf8_text_file(tmp_path):
    data = "﻿Delivery takes 3–5 days.\r\nPrice: ₹499\r\n\r\n\r\n\r\nThanks".encode("utf-8")
    result = extract_text(write(tmp_path, "faq.txt", data))
    # BOM removed, Windows line endings normalised, runs of blank lines squeezed to one.
    assert result.text == "Delivery takes 3–5 days.\nPrice: ₹499\n\nThanks"
    assert result.page_count is None


@pytest.mark.parametrize("name, data, reason", [
    ("broken.pdf", CORRUPT_PDF, "damaged"),
    ("nopages.pdf", blank_pdf(pages=0), "no pages"),
    ("scan.pdf", blank_pdf(), "No text found"),
    ("locked.pdf", blank_pdf(password="secret"), "password-protected"),
    ("latin1.txt", "Café".encode("latin-1"), "not valid UTF-8"),
    ("utf16.txt", "Hello".encode("utf-16-le"), "does not look like a text file"),
    ("blank.txt", b"  \n\n \t ", "contains no text"),
], ids=["corrupted-pdf", "zero-pages", "scanned-no-text", "password", "not-utf8", "utf16-binary", "empty-txt"])
def test_extraction_failures_give_a_reason(tmp_path, name, data, reason):
    with pytest.raises(ExtractionError, match=reason):
        extract_text(write(tmp_path, name, data))


def test_missing_file(tmp_path):
    with pytest.raises(ExtractionError, match="missing"):
        extract_text(tmp_path / "gone.pdf")


def test_clean_text_removes_nul_characters():
    # Some PDFs produce NUL characters, and PostgreSQL refuses to store them.
    assert clean_text("Refund\x00 policy  \n\n\n\nApplies") == "Refund policy\n\nApplies"


# ---------------------------------------------------------- through the API

def test_upload_pdf_extracts_text(client, admin):
    body = upload(client, admin, "policy.pdf", make_pdf("Refund Policy", REFUND)).json()
    assert body["status"] == "EXTRACTED"
    assert body["page_count"] == 2
    assert body["extraction_error"] is None
    assert "extracted_text" not in body  # the text is not sent with every document

    response = client.get(f"{URL}/{body['id']}/text", headers=admin.headers)
    assert response.status_code == 200
    text = response.json()
    assert REFUND in text["extracted_text"]
    assert text["char_count"] == body["char_count"] == len(text["extracted_text"])


def test_upload_txt_extracts_text(client, admin):
    body = upload(client, admin, "faq.txt", "Delivery takes 3–5 days.".encode()).json()
    assert (body["status"], body["page_count"]) == ("EXTRACTED", None)
    text = client.get(f"{URL}/{body['id']}/text", headers=admin.headers).json()
    assert text["extracted_text"] == "Delivery takes 3–5 days."


@pytest.mark.parametrize("name, data, reason", [
    ("broken.pdf", CORRUPT_PDF, "damaged"),
    ("scan.pdf", blank_pdf(), "No text found"),
    ("blank.txt", b"   \n\n  ", "contains no text"),
], ids=["corrupted-pdf", "scanned-no-text", "empty-txt"])
def test_bad_document_kept_as_failed(client, admin, storage, name, data, reason):
    response = upload(client, admin, name, data)
    assert response.status_code == 201  # the upload itself still succeeds
    body = response.json()
    assert body["status"] == "FAILED"
    assert reason in body["extraction_error"]
    assert (body["page_count"], body["char_count"]) == (None, None)

    [stored] = storage.iterdir()
    assert stored.read_bytes() == data  # the original is preserved, byte for byte
    assert client.get(f"{URL}/{body['id']}/text", headers=admin.headers).status_code == 409
    assert client.get(URL, headers=admin.headers).status_code == 200  # the app carries on


def test_unexpected_library_error_does_not_crash_the_app(client, admin, storage, monkeypatch):
    # pypdf can also raise ordinary errors (KeyError, ValueError...) on strange files.
    def broken_reader(path):
        raise KeyError("/Root")

    monkeypatch.setattr(text_extraction, "PdfReader", broken_reader)
    response = upload(client, admin, "policy.pdf", make_pdf(REFUND))
    assert response.status_code == 201
    assert response.json()["status"] == "FAILED"
    assert response.json()["extraction_error"] == "Unexpected error while reading the file"
    assert len(list(storage.iterdir())) == 1


def test_document_stored_before_phase_2_can_be_extracted(client, admin, storage, session_factory):
    # A Phase 1 upload: the row and the file exist, but extraction never ran.
    pdf = make_pdf(REFUND)
    write(storage, "0123abcd.pdf", pdf)
    with session_factory() as db:
        db.add(Document(title="Old refund policy", original_filename="refund.pdf",
                        stored_filename="0123abcd.pdf", content_type="application/pdf",
                        size_bytes=len(pdf), uploaded_by_id=admin.id))
        db.commit()

    [doc] = client.get(URL, headers=admin.headers).json()
    assert doc["status"] == "PENDING"
    assert client.get(f"{URL}/{doc['id']}/text", headers=admin.headers).status_code == 409

    response = client.post(f"{URL}/{doc['id']}/extract", headers=admin.headers)
    assert response.status_code == 200
    assert response.json()["status"] == "EXTRACTED"
    text = client.get(f"{URL}/{doc['id']}/text", headers=admin.headers).json()
    assert REFUND in text["extracted_text"]


def test_retry_after_failure(client, admin, storage):
    doc = upload(client, admin, "policy.pdf", make_pdf(REFUND)).json()
    [stored] = storage.iterdir()
    stored.unlink()  # the file goes missing

    failed = client.post(f"{URL}/{doc['id']}/extract", headers=admin.headers).json()
    assert failed["status"] == "FAILED" and "missing" in failed["extraction_error"]
    assert client.get(f"{URL}/{doc['id']}/text", headers=admin.headers).status_code == 409

    stored.write_bytes(make_pdf(REFUND))  # put it back and try again
    fixed = client.post(f"{URL}/{doc['id']}/extract", headers=admin.headers).json()
    assert (fixed["status"], fixed["extraction_error"]) == ("EXTRACTED", None)


def test_extract_and_text_are_admin_only(client, admin, make_user):
    doc_id = upload(client, admin, "hours.txt", b"Support is open 9 to 6.").json()["id"]
    for role, email in ((Role.CUSTOMER, "c@example.com"), (Role.AGENT, "a@example.com")):
        headers = make_user(role, email).headers
        assert client.post(f"{URL}/{doc_id}/extract", headers=headers).status_code == 403
        assert client.get(f"{URL}/{doc_id}/text", headers=headers).status_code == 403
    assert client.get(f"{URL}/{doc_id}/text").status_code == 401


def test_unknown_document(client, admin):
    assert client.post(f"{URL}/999/extract", headers=admin.headers).status_code == 404
    assert client.get(f"{URL}/999/text", headers=admin.headers).status_code == 404
