"""Phase 3: the Ollama embedding client. Ollama itself is always faked here."""
import httpx
import pytest

from app.core.config import settings
from app.services.embedding_client import BATCH_SIZE, EmbeddingError, embed_documents
from tests.conftest import FakeOllama

DIM = settings.embedding_dimension


def ollama_replies(monkeypatch, status_code=200, body=None, content=None):
    """Make every call to Ollama get this reply."""
    def post(url, json, timeout):
        request = httpx.Request("POST", url)
        if content is not None:
            return httpx.Response(status_code, content=content, request=request)
        return httpx.Response(status_code, json=body, request=request)
    monkeypatch.setattr(httpx, "post", post)


def ollama_raises(monkeypatch, error):
    def post(url, json, timeout):
        raise error
    monkeypatch.setattr(httpx, "post", post)


# ---------------------------------------------------------- success

def test_one_vector_per_text_in_order(fake_ollama):
    vectors = embed_documents(["Refund policy", "Shipping policy"])
    assert vectors == [FakeOllama.vector("search_document: Refund policy"),
                       FakeOllama.vector("search_document: Shipping policy")]
    assert all(len(v) == DIM for v in vectors)


def test_request_sent_to_ollama(fake_ollama):
    embed_documents(["Refund policy"])
    [request] = fake_ollama.requests
    assert request == {"model": "nomic-embed-text",
                       "input": ["search_document: Refund policy"],  # nomic's document prefix
                       "truncate": False}  # too-long text must fail, not be silently cut


def test_many_texts_are_sent_in_batches(fake_ollama):
    texts = [f"chunk {i}" for i in range(BATCH_SIZE + 4)]
    vectors = embed_documents(texts)
    assert [len(r["input"]) for r in fake_ollama.requests] == [BATCH_SIZE, 4]
    assert vectors == [FakeOllama.vector(f"search_document: {t}") for t in texts]  # order kept


# ---------------------------------------------------------- Ollama not usable

def test_ollama_not_running(monkeypatch):
    ollama_raises(monkeypatch, httpx.ConnectError("connection refused"))
    with pytest.raises(EmbeddingError, match="Cannot reach Ollama.*Is it running"):
        embed_documents(["text"])


def test_ollama_timeout(monkeypatch):
    ollama_raises(monkeypatch, httpx.ReadTimeout("timed out"))
    with pytest.raises(EmbeddingError, match="did not answer within 120 seconds"):
        embed_documents(["text"])


def test_model_not_installed(monkeypatch):
    ollama_replies(monkeypatch, 404, {"error": 'model "nomic-embed-text" not found, try pulling it first'})
    with pytest.raises(EmbeddingError, match="not installed. Run: ollama pull nomic-embed-text"):
        embed_documents(["text"])


def test_other_ollama_error_is_reported(monkeypatch):
    ollama_replies(monkeypatch, 400, {"error": "the input length exceeds the context length"})
    with pytest.raises(EmbeddingError, match="400: the input length exceeds the context length"):
        embed_documents(["text"])


# ---------------------------------------------------------- invalid replies are never returned

@pytest.mark.parametrize("reply", [
    {"content": b"<html>not json</html>"},
    {"body": {"model": "nomic-embed-text"}},       # no "embeddings" key
    {"body": ["not", "an", "object"]},
], ids=["not-json", "missing-key", "wrong-shape"])
def test_malformed_response(monkeypatch, reply):
    ollama_replies(monkeypatch, **reply)
    with pytest.raises(EmbeddingError, match="malformed"):
        embed_documents(["text"])


def test_wrong_number_of_embeddings(monkeypatch):
    ollama_replies(monkeypatch, body={"embeddings": [[0.1] * DIM]})
    with pytest.raises(EmbeddingError, match="wrong number of embeddings"):
        embed_documents(["first", "second"])


@pytest.mark.parametrize("embeddings", [[[]], [None]], ids=["empty-list", "null"])
def test_empty_embedding(monkeypatch, embeddings):
    ollama_replies(monkeypatch, body={"embeddings": embeddings})
    with pytest.raises(EmbeddingError, match="empty embedding"):
        embed_documents(["text"])


def test_unexpected_dimension(monkeypatch):
    ollama_replies(monkeypatch, body={"embeddings": [[0.1] * 384]})  # e.g. a different model
    with pytest.raises(EmbeddingError, match="Expected 768 numbers per embedding, got 384"):
        embed_documents(["text"])


@pytest.mark.parametrize("bad", [
    b'"0.1"',   # a string
    b"true",    # a boolean (Python treats True as 1, so it needs its own check)
    b"NaN",     # not a real number
    b"null",
], ids=["string", "boolean", "nan", "null"])
def test_non_numeric_values(monkeypatch, bad):
    values = b",".join([b"0.1"] * (DIM - 1) + [bad])
    ollama_replies(monkeypatch, content=b'{"embeddings": [[' + values + b"]]}")
    with pytest.raises(EmbeddingError, match="not numbers"):
        embed_documents(["text"])
