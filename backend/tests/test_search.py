"""Phase 4: the search service and API, with vectors whose similarities are known exactly.

Each seeded chunk points along its own axis (refund = axis 0, shipping = axis 1,
hours = axis 2), and each test chooses the question's vector. So the right ranking
is known in advance, independent of any real model.
"""
import math
import uuid

import httpx
import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document, DocumentChunk, DocumentStatus, IndexStatus, Role

URL = "/admin/documents/search"
DIM = settings.embedding_dimension
REFUND, SHIPPING, HOURS = 0, 1, 2


def vector(**weights) -> list[float]:
    """A 768-number vector with the given weights on the named axes, zero elsewhere."""
    axes = {"refund": REFUND, "shipping": SHIPPING, "hours": HOURS, "other": 10}
    values = [0.0] * DIM
    for name, weight in weights.items():
        values[axes[name]] = weight
    return values


@pytest.fixture()
def admin(make_user):
    return make_user(Role.ADMIN, "admin@example.com")


@pytest.fixture()
def add_document(session_factory, admin):
    def _add(title, chunks, index_status=IndexStatus.INDEXED, status=DocumentStatus.EXTRACTED,
             model="nomic-embed-text"):
        with session_factory() as db:
            document = Document(title=title, original_filename=f"{title}.txt",
                                stored_filename=f"{uuid.uuid4().hex}.txt", content_type="text/plain",
                                size_bytes=100, uploaded_by_id=admin.id, business_id=admin.business_id,
                                status=status,
                                index_status=index_status, chunk_count=len(chunks))
            db.add(document)
            db.flush()
            for index, (text, embedding) in enumerate(chunks):
                db.add(DocumentChunk(document_id=document.id, chunk_index=index, text=text,
                                     word_count=len(text.split()), embedding=embedding,
                                     embedding_model=model))
            db.commit()
            return document.id
    return _add


@pytest.fixture()
def knowledge_base(add_document):
    return add_document("Support policy", [
        ("Refund Policy. Customers can request a refund within 30 days.", vector(refund=1)),
        ("Shipping Policy. Delivery takes 3 to 5 business days.", vector(shipping=1)),
        ("Support Hours. Monday to Friday, 9 AM to 6 PM.", vector(hours=1)),
    ])


def question_embeds_as(monkeypatch, embedding):
    """Make Ollama return `embedding` for the question; returns the requests it received."""
    sent = []

    def post(url, json, timeout):
        sent.append(json)
        return httpx.Response(200, json={"embeddings": [embedding]}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    return sent


def search(client, admin, **body):
    body.setdefault("query", "Can I get my money back?")
    return client.post(URL, json=body, headers=admin.headers)


# The question leans mostly towards refunds, a little towards shipping.
# Its cosine with each axis: refund 0.9/|q| = 0.9091, shipping 0.4041, hours 0.1010.
MOSTLY_REFUND = vector(refund=0.9, shipping=0.4, hours=0.1)
NORM = math.sqrt(0.9**2 + 0.4**2 + 0.1**2)


# ---------------------------------------------------------- successful search

def test_search_returns_the_best_chunk(client, admin, knowledge_base, monkeypatch):
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    response = search(client, admin)
    assert response.status_code == 200
    body = response.json()
    assert (body["outcome"], body["message"]) == ("FOUND", "Relevant knowledge found")
    assert (body["top_k"], body["threshold"], body["chunks_searched"]) == (3, 0.55, 3)
    assert body["embedding_model"] == "nomic-embed-text"
    [hit] = body["results"]  # only refund (0.909) reaches the default threshold of 0.55
    assert hit["document_id"] == knowledge_base
    assert hit["document_title"] == "Support policy"
    assert hit["chunk_index"] == 0
    assert hit["text"].startswith("Refund Policy.")
    assert hit["similarity"] == pytest.approx(0.9 / NORM, abs=1e-4)
    assert set(hit) == {"chunk_id", "document_id", "document_title", "chunk_index", "text", "similarity"}
    # No vectors, file names or paths anywhere in the response.
    assert "embedding\"" not in response.text and "stored_filename" not in response.text


def test_results_are_sorted_highest_first(client, admin, knowledge_base, monkeypatch):
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    results = search(client, admin, threshold=0).json()["results"]
    assert [r["chunk_index"] for r in results] == [REFUND, SHIPPING, HOURS]
    scores = [r["similarity"] for r in results]
    assert scores == sorted(scores, reverse=True)
    assert scores == pytest.approx([0.9 / NORM, 0.4 / NORM, 0.1 / NORM], abs=1e-4)


def test_question_is_embedded_as_a_search_query(client, admin, knowledge_base, monkeypatch):
    sent = question_embeds_as(monkeypatch, MOSTLY_REFUND)
    search(client, admin, query="  When are you open?  ")
    # nomic-embed-text's question prefix, not the document one; the query is trimmed first.
    assert sent == [{"model": "nomic-embed-text", "input": ["search_query: When are you open?"],
                     "truncate": False}]


def test_results_can_come_from_several_documents(client, admin, knowledge_base, add_document, monkeypatch):
    add_document("Returns FAQ", [("Returned items are refunded in 5 days.", vector(refund=1, shipping=0.2))])
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    titles = [r["document_title"] for r in search(client, admin, threshold=0.5).json()["results"]]
    assert titles == ["Returns FAQ", "Support policy"]  # 0.970 beats 0.909


# ---------------------------------------------------------- threshold and top_k

def test_threshold_parameter_changes_what_is_accepted(client, admin, knowledge_base, monkeypatch):
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    count = lambda t: len(search(client, admin, threshold=t).json()["results"])  # noqa: E731
    assert count(0.95) == 0   # stricter than the best score
    assert count(0.55) == 1   # the default
    assert count(0.3) == 2    # now shipping (0.404) passes too
    assert count(0.0) == 3


def test_top_k_parameter_limits_results(client, admin, knowledge_base, monkeypatch):
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    assert [r["chunk_index"] for r in search(client, admin, threshold=0, top_k=2).json()["results"]] == [0, 1]
    assert [r["chunk_index"] for r in search(client, admin, threshold=0, top_k=1).json()["results"]] == [0]


def test_defaults_come_from_the_settings(client, admin, knowledge_base, monkeypatch):
    monkeypatch.setattr(settings, "search_top_k", 2)
    monkeypatch.setattr(settings, "search_similarity_threshold", 0.1)
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    body = search(client, admin).json()
    assert (body["top_k"], body["threshold"], len(body["results"])) == (2, 0.1, 2)


@pytest.mark.parametrize("field, value", [
    ("top_k", 0), ("top_k", 21), ("threshold", -0.1), ("threshold", 1.5), ("top_k", "many"),
])
def test_invalid_parameters_are_rejected(client, admin, field, value):
    assert search(client, admin, **{field: value}).status_code == 422


# ---------------------------------------------------------- no results

def test_no_relevant_knowledge(client, admin, knowledge_base, monkeypatch):
    question_embeds_as(monkeypatch, vector(other=1))  # unrelated to every chunk
    body = search(client, admin, query="What is the capital of France?").json()
    assert (body["outcome"], body["message"]) == ("NO_MATCH", "No relevant knowledge found")
    assert body["results"] == []  # no low-similarity fallback
    assert body["best_similarity"] == 0.0
    assert body["chunks_searched"] == 3


def test_no_indexed_documents(client, admin, fake_ollama):
    body = search(client, admin).json()
    assert (body["outcome"], body["results"]) == ("NO_INDEXED_DOCUMENTS", [])
    assert body["message"] == "The knowledge base has no indexed documents"
    assert fake_ollama.requests == []  # nothing to compare with, so Ollama is not asked


def test_only_indexed_documents_are_searched(client, admin, knowledge_base, add_document, monkeypatch):
    # Each of these points exactly along the question (similarity 1.0) and must still be ignored.
    add_document("Failed to index", [("stale", vector(refund=1))], index_status=IndexStatus.FAILED)
    add_document("Not indexed yet", [("pending", vector(refund=1))], index_status=IndexStatus.NOT_INDEXED)
    add_document("Extraction failed", [("broken", vector(refund=1))], status=DocumentStatus.FAILED,
                 index_status=IndexStatus.NOT_INDEXED)
    add_document("Other model", [("old vectors", vector(refund=1))], model="another-embedding-model")
    question_embeds_as(monkeypatch, vector(refund=1))

    body = search(client, admin, threshold=0).json()
    assert body["chunks_searched"] == 3
    assert {r["document_title"] for r in body["results"]} == {"Support policy"}


def test_only_unindexed_documents_means_nothing_to_search(client, admin, add_document, fake_ollama):
    add_document("Failed to index", [("stale", vector(refund=1))], index_status=IndexStatus.FAILED)
    assert search(client, admin).json()["outcome"] == "NO_INDEXED_DOCUMENTS"


# ---------------------------------------------------------- the query

@pytest.mark.parametrize("query", ["", "   ", "a", "x" * 501])
def test_bad_query_is_rejected(client, admin, query):
    assert search(client, admin, query=query).status_code == 422


def test_missing_query_is_rejected(client, admin):
    assert client.post(URL, json={}, headers=admin.headers).status_code == 422


@pytest.mark.parametrize("extra", [{"business_id": 2}, {"document_ids": [1]}, {"scope": "all"}])
def test_client_cannot_choose_what_is_searched(client, admin, extra):
    assert search(client, admin, **extra).status_code == 422


# ---------------------------------------------------------- failures are reported, never hidden

def test_ollama_unavailable(client, admin, knowledge_base, monkeypatch):
    def post(url, json, timeout):
        raise httpx.ConnectError("connection refused")
    monkeypatch.setattr(httpx, "post", post)
    response = search(client, admin)
    assert response.status_code == 503
    assert "Search is unavailable: Cannot reach Ollama" in response.json()["detail"]


@pytest.mark.parametrize("embedding, reason", [
    ([0.5] * 384, "Expected 768 numbers"),  # wrong dimension
    ([], "empty embedding"),
    ([0.0] * DIM, "all-zero vector"),       # no direction, so no similarity
], ids=["wrong-dimension", "empty", "zero"])
def test_unusable_question_vector(client, admin, knowledge_base, monkeypatch, embedding, reason):
    question_embeds_as(monkeypatch, embedding)
    response = search(client, admin)
    assert response.status_code == 503
    assert reason in response.json()["detail"]


def test_damaged_stored_vectors_are_skipped_and_counted(client, admin, knowledge_base, add_document, monkeypatch):
    add_document("Damaged", [("short", [0.1] * 10), ("zero", [0.0] * DIM), ("text", ["x"] * DIM)])
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    body = search(client, admin, threshold=0).json()
    assert (body["chunks_searched"], body["chunks_skipped"]) == (3, 3)
    assert {r["document_title"] for r in body["results"]} == {"Support policy"}


def test_every_stored_vector_damaged(client, admin, add_document, monkeypatch):
    add_document("Damaged", [("short", [0.1] * 10)])
    question_embeds_as(monkeypatch, MOSTLY_REFUND)
    response = search(client, admin)
    assert response.status_code == 503
    assert "Re-index the documents" in response.json()["detail"]


def test_database_failure(client, admin, knowledge_base, monkeypatch):
    real_execute = Session.execute

    def execute(self, statement, *args, **kwargs):
        if "document_chunks" in str(statement):  # only the search query fails, not the login
            raise OperationalError("SELECT", {}, Exception("connection lost"))
        return real_execute(self, statement, *args, **kwargs)
    monkeypatch.setattr(Session, "execute", execute)
    response = search(client, admin)
    assert response.status_code == 503
    assert response.json()["detail"] == "Search is unavailable: The knowledge base could not be read"


# ---------------------------------------------------------- access control

def test_search_is_admin_only(client, make_user):
    for role, email in ((Role.CUSTOMER, "c@example.com"), (Role.AGENT, "a@example.com")):
        headers = make_user(role, email).headers
        assert client.post(URL, json={"query": "refund?"}, headers=headers).status_code == 403
    assert client.post(URL, json={"query": "refund?"}).status_code == 401
