"""Turn text into embedding vectors with the local Ollama server.

The only module that talks to Ollama. Every reply is checked before it is returned,
so an invalid vector can never reach the database.
"""
import math

import httpx

from app.core.config import settings

# nomic-embed-text was trained with task prefixes. Stored text is embedded as a
# "search_document"; Phase 4 must embed questions as "search_query: ..." to match.
DOCUMENT_PREFIX = "search_document: "
BATCH_SIZE = 16  # texts per request, so one request never grows too large


class EmbeddingError(Exception):
    """Embeddings could not be produced. The message is shown to the admin."""


def embed_documents(texts: list[str]) -> list[list[float]]:
    """One vector per text, in the same order."""
    inputs = [DOCUMENT_PREFIX + text for text in texts]
    vectors: list[list[float]] = []
    for start in range(0, len(inputs), BATCH_SIZE):
        vectors.extend(_embed_batch(inputs[start:start + BATCH_SIZE]))
    return vectors


def _embed_batch(inputs: list[str]) -> list[list[float]]:
    url = f"{settings.ollama_url}/api/embed"
    payload = {
        "model": settings.embedding_model,
        "input": inputs,
        # Without this, Ollama silently cuts off text longer than the model's limit and
        # returns a vector for only part of it. We want an error instead.
        "truncate": False,
    }
    try:
        response = httpx.post(url, json=payload, timeout=settings.ollama_timeout_seconds)
    except httpx.TimeoutException as error:
        raise EmbeddingError(
            f"Ollama did not answer within {settings.ollama_timeout_seconds:g} seconds") from error
    except httpx.HTTPError as error:
        raise EmbeddingError(
            f"Cannot reach Ollama at {settings.ollama_url}. Is it running?") from error

    if response.status_code == 404:
        raise EmbeddingError(f"The model {settings.embedding_model} is not installed. "
                             f"Run: ollama pull {settings.embedding_model}")
    if response.status_code != 200:
        raise EmbeddingError(f"Ollama error {response.status_code}: {_error_text(response)}")
    return _parse(response, expected=len(inputs))


def _parse(response: httpx.Response, expected: int) -> list[list[float]]:
    try:
        vectors = response.json()["embeddings"]
    except (ValueError, KeyError, TypeError) as error:
        raise EmbeddingError("Ollama returned a malformed response") from error
    if not isinstance(vectors, list) or len(vectors) != expected:
        raise EmbeddingError(f"Ollama returned the wrong number of embeddings (expected {expected})")
    return [_check_vector(vector) for vector in vectors]


def _check_vector(vector) -> list[float]:
    if not isinstance(vector, list) or not vector:
        raise EmbeddingError("Ollama returned an empty embedding")
    if len(vector) != settings.embedding_dimension:
        raise EmbeddingError(f"Expected {settings.embedding_dimension} numbers per embedding, "
                             f"got {len(vector)}. Is embedding_model set correctly?")
    for value in vector:
        # bool is a subclass of int in Python, so it must be excluded explicitly.
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
            raise EmbeddingError("The embedding contains values that are not numbers")
    return [float(value) for value in vector]


def _error_text(response: httpx.Response) -> str:
    try:
        return str(response.json()["error"])[:200]
    except (ValueError, KeyError, TypeError):
        return response.text[:200] or "no details"
