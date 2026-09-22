import pytest

from app.core.config import settings
from app.models import Role

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
URL = "/admin/documents"


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    """Every test gets its own empty storage folder, never the real one."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    return tmp_path


@pytest.fixture()
def admin(make_user):
    return make_user(Role.ADMIN, "admin@example.com")


def upload(client, headers, filename="refund.pdf", content=PDF, title="Refund policy"):
    return client.post(URL, data={"title": title}, files={"file": (filename, content)}, headers=headers)


def stored_files(folder):
    return sorted(p.name for p in folder.iterdir())


# ---------------------------------------------------------- happy paths

def test_admin_uploads_pdf(client, admin, storage):
    response = upload(client, admin.headers)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Refund policy"
    assert body["original_filename"] == "refund.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert body["uploaded_by"]["id"] == admin.id
    assert "stored_filename" not in body  # the disk name is never exposed

    [name] = stored_files(storage)
    assert name.endswith(".pdf") and name != "refund.pdf"  # our name, not theirs
    assert (storage / name).read_bytes() == PDF


def test_text_file_upload(client, admin):
    response = upload(client, admin.headers, "faq.txt", "Delivery takes 3–5 days.".encode(), "Shipping FAQ")
    assert response.status_code == 201
    assert response.json()["content_type"] == "text/plain"


def test_list_newest_first(client, admin):
    upload(client, admin.headers, title="First document")
    upload(client, admin.headers, title="Second document")
    titles = [d["title"] for d in client.get(URL, headers=admin.headers).json()]
    assert titles == ["Second document", "First document"]


# ---------------------------------------------------------- hostile filenames

@pytest.mark.parametrize("filename, shown_as", [
    ("../../../etc/evil.pdf", "evil.pdf"),
    ("..\\..\\windows\\evil.pdf", "evil.pdf"),
    ("C:\\Users\\asha\\Documents\\refund.pdf", "refund.pdf"),
])
def test_path_traversal_cannot_escape_storage(client, admin, storage, filename, shown_as):
    response = upload(client, admin.headers, filename)
    assert response.status_code == 201
    assert response.json()["original_filename"] == shown_as
    # Exactly one file, sitting directly inside the storage folder — nowhere else.
    [name] = stored_files(storage)
    assert (storage / name).is_file()
    assert ".." not in name and "/" not in name and "\\" not in name


# ---------------------------------------------------------- rejected uploads

@pytest.mark.parametrize("filename, content, code", [
    ("virus.exe", b"MZ\x90\x00", 415),                  # not on the allow-list
    ("invoice.pdf.exe", PDF, 415),                       # double extension: the real one is .exe
    ("fake.pdf", b"just some text, not a PDF", 415),     # extension lies about the content
    ("binary.txt", b"hello\x00\x01\x02", 415),           # binary pretending to be text
    ("empty.pdf", b"", 400),
])
def test_bad_files_rejected_and_nothing_saved(client, admin, storage, filename, content, code):
    response = upload(client, admin.headers, filename, content)
    assert response.status_code == code, response.text
    assert stored_files(storage) == []
    assert client.get(URL, headers=admin.headers).json() == []


def test_file_over_size_limit(client, admin, storage, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    too_big = PDF + b"0" * (1024 * 1024)
    response = upload(client, admin.headers, "huge.pdf", too_big)
    assert response.status_code == 413
    assert stored_files(storage) == []


@pytest.mark.parametrize("title", ["", "   ", "A", "x" * 201])
def test_title_validation(client, admin, title):
    assert upload(client, admin.headers, title=title).status_code == 422


# ---------------------------------------------------------- access control

def test_only_admins(client, make_user):
    customer = make_user(Role.CUSTOMER, "c@example.com")
    agent = make_user(Role.AGENT, "a@example.com")
    for headers in (customer.headers, agent.headers):
        assert upload(client, headers).status_code == 403
        assert client.get(URL, headers=headers).status_code == 403
        assert client.delete(f"{URL}/1", headers=headers).status_code == 403
    assert client.get(URL).status_code == 401


# ---------------------------------------------------------- delete

def test_delete_removes_row_and_file(client, admin, storage):
    document_id = upload(client, admin.headers).json()["id"]
    assert len(stored_files(storage)) == 1

    assert client.delete(f"{URL}/{document_id}", headers=admin.headers).status_code == 204
    assert stored_files(storage) == []
    assert client.get(URL, headers=admin.headers).json() == []
    assert client.delete(f"{URL}/{document_id}", headers=admin.headers).status_code == 404
