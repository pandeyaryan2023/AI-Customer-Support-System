"""Retrieval quality with the REAL nomic-embed-text model. Opt-in, because it needs Ollama:

    set RUN_OLLAMA_TESTS=1   (PowerShell: $env:RUN_OLLAMA_TESTS = "1")
    pytest tests/test_retrieval_quality.py

Skipped in the normal run, so the main suite never depends on Ollama. The knowledge
base is the exact text Phase 2 extracts from Customer_Support_Knowledge_Base_Test.pdf.
"""
import os

import httpx
import pytest

from app.core.config import settings
from app.models import Role
from tests.test_chunking import KB_TEXT

REAL_POST = httpx.post  # captured at import, before conftest swaps in the fake for each test

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_OLLAMA_TESTS") != "1",
    reason="needs a running Ollama with nomic-embed-text (set RUN_OLLAMA_TESTS=1)",
)

SIZES = {
    "default-chunks": (settings.chunk_words, settings.chunk_overlap_words),  # 1 chunk: whole document
    "section-chunks": (30, 0),                                               # 3 chunks: one per section
}
ANSWERED = [
    ("Can I get my money back after 20 days?", "Refund Policy"),
    ("What is the company's refund time limit?", "Refund Policy"),
    ("How long does delivery usually take?", "Shipping Policy"),
    ("How long does delivery take?", "Shipping Policy"),
    ("When can I contact customer support?", "Support Hours"),
    ("When is customer support available?", "Support Hours"),
]
UNRELATED = [
    "What is the capital of France?",
    "How do I bake a chocolate cake?",
    "Who won the 2018 football World Cup?",
]


@pytest.fixture(autouse=True)
def real_ollama(fake_ollama, monkeypatch, tmp_path):
    """Undo the fake: these tests talk to the real local Ollama."""
    monkeypatch.setattr(httpx, "post", REAL_POST)
    monkeypatch.setattr(settings, "ollama_url", os.environ.get("OLLAMA_TEST_URL", "http://127.0.0.1:11434"))
    monkeypatch.setattr(settings, "storage_dir", tmp_path)


@pytest.fixture(params=list(SIZES))
def admin(request, client, make_user, monkeypatch):
    """An admin whose knowledge base holds the test document, indexed at one chunk size."""
    words, overlap = SIZES[request.param]
    monkeypatch.setattr(settings, "chunk_words", words)
    monkeypatch.setattr(settings, "chunk_overlap_words", overlap)
    admin = make_user(Role.ADMIN, "admin@example.com")
    doc = client.post("/admin/documents", data={"title": "Customer support knowledge base"},
                      files={"file": ("kb.txt", KB_TEXT.encode())}, headers=admin.headers).json()
    assert doc["index_status"] == "INDEXED", doc["index_error"]
    admin.sections = request.param == "section-chunks"
    return admin


def search(client, admin, query, **extra):
    response = client.post("/admin/documents/search", json={"query": query, **extra}, headers=admin.headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("question, section", ANSWERED)
def test_answered_question_finds_its_section(client, admin, question, section):
    body = search(client, admin, question)
    assert body["outcome"] == "FOUND"
    top = body["results"][0]
    assert top["similarity"] >= settings.search_similarity_threshold
    assert section in top["text"]
    if admin.sections:  # with one chunk per section, the right section must rank first
        others = {"Refund Policy", "Shipping Policy", "Support Hours"} - {section}
        assert not any(other in top["text"] for other in others)


@pytest.mark.parametrize("question", UNRELATED)
def test_unrelated_question_finds_nothing(client, admin, question):
    body = search(client, admin, question)
    assert (body["outcome"], body["results"]) == ("NO_MATCH", [])
    assert body["best_similarity"] < settings.search_similarity_threshold


def test_raising_the_threshold_rejects_a_real_match(client, admin):
    question = "Can I get my money back after 20 days?"
    assert search(client, admin, question)["outcome"] == "FOUND"
    assert search(client, admin, question, threshold=0.9)["outcome"] == "NO_MATCH"
