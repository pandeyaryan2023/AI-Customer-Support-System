"""Phase 3: the full pipeline - upload, extract, chunk, embed, store."""
import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.config import settings
from app.models import Document, DocumentChunk, Role
from app.services import chunking, indexing_service
from tests.conftest import FakeOllama
from tests.test_chunking import KB_TEXT
from tests.test_text_extraction import REFUND, make_pdf

URL = "/admin/documents"


@pytest.fixture(autouse=True)
def storage(tmp_path, monkeypatch):
    """Every test gets its own empty storage folder, never the real one."""
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    return tmp_path


@pytest.fixture()
def admin(make_user):
    return make_user(Role.ADMIN, "admin@example.com")


def upload(client, admin, filename="policy.txt", content=KB_TEXT.encode(), title="Support policy"):
    response = client.post(URL, data={"title": title}, files={"file": (filename, content)},
                           headers=admin.headers)
    assert response.status_code == 201, response.text
    return response.json()


def stored_chunks(session_factory, document_id=None):
    with session_factory() as db:
        stmt = select(DocumentChunk).order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
        if document_id is not None:
            stmt = stmt.where(DocumentChunk.document_id == document_id)
        return list(db.scalars(stmt).all())


def ollama_down(monkeypatch):
    def post(url, json, timeout):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "post", post)


def ollama_replies(monkeypatch, body):
    def post(url, json, timeout):
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)


# ---------------------------------------------------------- the happy path

def test_upload_is_chunked_and_embedded(client, admin):
    doc = upload(client, admin)
    assert (doc["status"], doc["index_status"]) == ("EXTRACTED", "INDEXED")
    assert (doc["chunk_count"], doc["index_error"]) == (1, None)  # 81 words: one chunk

    [chunk] = client.get(f"{URL}/{doc['id']}/chunks", headers=admin.headers).json()
    assert chunk["chunk_index"] == 0
    assert REFUND in chunk["text"]
    assert chunk["word_count"] == 81
    assert chunk["embedding_model"] == "nomic-embed-text"
    assert chunk["embedding_dimension"] == 768
    assert len(chunk["embedding_preview"]) == 8
    assert "embedding" not in chunk  # the full vector is not sent


def test_pdf_upload_is_indexed(client, admin):
    doc = upload(client, admin, "policy.pdf", make_pdf("Refund Policy", REFUND))
    assert (doc["status"], doc["index_status"], doc["chunk_count"]) == ("EXTRACTED", "INDEXED", 1)


def test_embedding_is_stored_exactly(client, admin, session_factory):
    doc = upload(client, admin)
    [row] = stored_chunks(session_factory, doc["id"])
    # The numbers read back from the database are exactly the ones Ollama returned.
    assert row.embedding == FakeOllama.vector("search_document: " + row.text)
    assert all(isinstance(x, float) for x in row.embedding)
    assert row.created_at is not None


def test_long_document_gives_ordered_chunks(client, admin, monkeypatch, fake_ollama, session_factory):
    monkeypatch.setattr(settings, "chunk_words", 20)
    monkeypatch.setattr(settings, "chunk_overlap_words", 5)
    text = " ".join(f"Sentence {i} has exactly six words." for i in range(12))  # 72 words
    doc = upload(client, admin, content=text.encode())

    chunks = client.get(f"{URL}/{doc['id']}/chunks", headers=admin.headers).json()
    assert doc["chunk_count"] == len(chunks) > 1
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))
    assert all(c["word_count"] <= 20 for c in chunks)
    # Ollama was asked for the chunks in the same order they were stored.
    sent = [text for request in fake_ollama.requests for text in request["input"]]
    assert sent == ["search_document: " + c["text"] for c in chunks]
    # And each stored vector belongs to its own chunk.
    for row in stored_chunks(session_factory, doc["id"]):
        assert row.embedding == FakeOllama.vector("search_document: " + row.text)


# ---------------------------------------------------------- reprocessing

def test_reindexing_replaces_chunks_instead_of_duplicating(client, admin, session_factory):
    doc = upload(client, admin)
    for _ in range(2):
        again = client.post(f"{URL}/{doc['id']}/index", headers=admin.headers)
        assert again.status_code == 200
        assert (again.json()["index_status"], again.json()["chunk_count"]) == ("INDEXED", 1)
    rows = stored_chunks(session_factory, doc["id"])
    assert [row.chunk_index for row in rows] == [0]  # still one chunk 0, not three


def test_reindexing_with_new_settings_replaces_every_old_chunk(client, admin, monkeypatch, session_factory):
    doc = upload(client, admin)
    [old] = stored_chunks(session_factory, doc["id"])  # 500-word setting: one 81-word chunk

    monkeypatch.setattr(settings, "chunk_words", 30)
    monkeypatch.setattr(settings, "chunk_overlap_words", 0)
    for _ in range(2):
        client.post(f"{URL}/{doc['id']}/index", headers=admin.headers)

    rows = stored_chunks(session_factory, doc["id"])
    assert [row.chunk_index for row in rows] == [0, 1, 2]  # exactly the new set, once
    assert old.text not in [row.text for row in rows]  # the old 81-word chunk is gone


def test_reindexing_one_document_leaves_others_alone(client, admin, session_factory):
    first = upload(client, admin, title="First policy")
    second = upload(client, admin, title="Second policy")
    client.post(f"{URL}/{first['id']}/index", headers=admin.headers)
    assert len(stored_chunks(session_factory, second["id"])) == 1
    assert len(stored_chunks(session_factory)) == 2


def test_re_extraction_rebuilds_the_chunks(client, admin, storage, session_factory):
    doc = upload(client, admin)
    [stored] = storage.iterdir()
    stored.unlink()  # file missing: extraction fails, so the old chunks must go
    failed = client.post(f"{URL}/{doc['id']}/extract", headers=admin.headers).json()
    assert (failed["status"], failed["index_status"], failed["chunk_count"]) == ("FAILED", "NOT_INDEXED", None)
    assert stored_chunks(session_factory, doc["id"]) == []

    stored.write_bytes(KB_TEXT.encode())  # file back: extracted and indexed again
    fixed = client.post(f"{URL}/{doc['id']}/extract", headers=admin.headers).json()
    assert (fixed["status"], fixed["index_status"], fixed["chunk_count"]) == ("EXTRACTED", "INDEXED", 1)


# ---------------------------------------------------------- Ollama failures

def test_ollama_unavailable_at_upload(client, admin, monkeypatch, storage, session_factory):
    ollama_down(monkeypatch)
    doc = upload(client, admin)  # the upload itself still succeeds
    assert doc["status"] == "EXTRACTED"  # Phase 2's result is kept
    assert doc["index_status"] == "FAILED"
    assert "Cannot reach Ollama" in doc["index_error"]
    assert doc["chunk_count"] is None
    assert stored_chunks(session_factory) == []  # nothing half-saved
    assert len(list(storage.iterdir())) == 1  # original file kept
    assert client.get(f"{URL}/{doc['id']}/text", headers=admin.headers).status_code == 200


def test_retry_after_ollama_comes_back(client, admin, monkeypatch, fake_ollama):
    ollama_down(monkeypatch)
    doc = upload(client, admin)
    assert doc["index_status"] == "FAILED"

    monkeypatch.setattr(httpx, "post", fake_ollama.post)  # Ollama is running again
    retried = client.post(f"{URL}/{doc['id']}/index", headers=admin.headers).json()
    assert (retried["index_status"], retried["index_error"], retried["chunk_count"]) == ("INDEXED", None, 1)


def test_failed_reindex_removes_old_chunks(client, admin, monkeypatch, session_factory):
    doc = upload(client, admin)
    assert len(stored_chunks(session_factory, doc["id"])) == 1

    ollama_down(monkeypatch)
    failed = client.post(f"{URL}/{doc['id']}/index", headers=admin.headers).json()
    # Rule: chunks exist only for INDEXED documents, so a search never uses stale ones.
    assert failed["index_status"] == "FAILED"
    assert stored_chunks(session_factory, doc["id"]) == []


@pytest.mark.parametrize("body, reason", [
    ({"unexpected": "shape"}, "malformed"),
    ({"embeddings": [[]]}, "empty embedding"),
    ({"embeddings": [[0.5] * 384]}, "Expected 768"),
], ids=["malformed", "empty", "wrong-dimension"])
def test_invalid_embeddings_are_never_saved(client, admin, monkeypatch, session_factory, body, reason):
    ollama_replies(monkeypatch, body)
    doc = upload(client, admin)
    assert doc["index_status"] == "FAILED"
    assert reason in doc["index_error"]
    assert stored_chunks(session_factory) == []


def test_unexpected_error_does_not_crash_the_app(client, admin, monkeypatch):
    def broken(text, max_words, overlap_words):
        raise RuntimeError("bug in chunking")
    monkeypatch.setattr(indexing_service, "chunk_text", broken)
    doc = upload(client, admin)
    assert (doc["index_status"], doc["index_error"]) == ("FAILED", "Unexpected error while indexing")
    assert client.get(URL, headers=admin.headers).status_code == 200


# ---------------------------------------------------------- nothing to index

def test_document_with_extraction_failure_is_not_indexed(client, admin, fake_ollama, session_factory):
    doc = upload(client, admin, "broken.pdf", b"%PDF-1.7\nthis is not really a pdf at all")
    assert (doc["status"], doc["index_status"], doc["chunk_count"]) == ("FAILED", "NOT_INDEXED", None)
    assert fake_ollama.requests == []  # Ollama is never asked about a document with no text
    assert client.get(f"{URL}/{doc['id']}/chunks", headers=admin.headers).json() == []
    response = client.post(f"{URL}/{doc['id']}/index", headers=admin.headers)
    assert response.status_code == 409
    assert stored_chunks(session_factory) == []


def test_text_that_is_empty_after_cleaning(client, admin, fake_ollama):
    doc = upload(client, admin, content="​​​".encode())  # only invisible characters
    assert doc["status"] == "EXTRACTED"
    assert (doc["index_status"], doc["index_error"]) == ("FAILED", "There is no text left to index after cleaning")
    assert fake_ollama.requests == []  # no embedding is requested for an empty chunk


# ---------------------------------------------------------- deleting

def test_delete_removes_the_chunks(client, admin, session_factory):
    doc = upload(client, admin)
    assert client.delete(f"{URL}/{doc['id']}", headers=admin.headers).status_code == 204
    assert stored_chunks(session_factory) == []


# ---------------------------------------------------------- database failure

def test_database_failure_keeps_the_previous_chunks(client, admin, monkeypatch, session_factory):
    doc = upload(client, admin)
    [before] = stored_chunks(session_factory, doc["id"])

    with session_factory() as db:
        document = db.get(Document, doc["id"])

        def commit_fails():
            raise OperationalError("COMMIT", {}, Exception("database went away"))
        monkeypatch.setattr(db, "commit", commit_fails)
        with pytest.raises(OperationalError):
            indexing_service.index_document(db, document)
        # Straight after the failure, this same session already sees the old state again.
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 1
        assert document.index_status == "INDEXED"

    # The delete of the old chunk was rolled back with everything else: no loss, no duplicates.
    [after] = stored_chunks(session_factory, doc["id"])
    assert (after.id, after.embedding) == (before.id, before.embedding)
    with session_factory() as db:
        assert db.get(Document, doc["id"]).index_status == "INDEXED"
        assert db.scalar(select(func.count()).select_from(DocumentChunk)) == 1


# ---------------------------------------------------------- access control

def test_index_and_chunks_are_admin_only(client, admin, make_user):
    doc_id = upload(client, admin)["id"]
    for role, email in ((Role.CUSTOMER, "c@example.com"), (Role.AGENT, "a@example.com")):
        headers = make_user(role, email).headers
        assert client.post(f"{URL}/{doc_id}/index", headers=headers).status_code == 403
        assert client.get(f"{URL}/{doc_id}/chunks", headers=headers).status_code == 403
    assert client.get(f"{URL}/{doc_id}/chunks").status_code == 401
    assert client.post(f"{URL}/{doc_id}/index").status_code == 401


def test_unknown_document(client, admin):
    assert client.post(f"{URL}/999/index", headers=admin.headers).status_code == 404
    assert client.get(f"{URL}/999/chunks", headers=admin.headers).status_code == 404


def test_chunking_module_is_used_with_the_configured_sizes(monkeypatch):
    seen = {}

    def spy(text, max_words, overlap_words):
        seen.update(max_words=max_words, overlap_words=overlap_words)
        return chunking.chunk_text(text, max_words, overlap_words)
    monkeypatch.setattr(indexing_service, "chunk_text", spy)
    indexing_service.build_chunks(KB_TEXT)
    assert seen == {"max_words": 500, "overlap_words": 75}
