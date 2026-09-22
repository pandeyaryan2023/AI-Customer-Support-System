"""Ask the local language model (Llama 3.2 through Ollama) to write a reply.

The only module that calls Ollama's chat API. Every failure becomes an LLMError
with a readable reason, and a reply is checked before it is returned.
"""
from dataclasses import dataclass

import httpx

from app.core.config import settings
from app.services.embedding_client import _error_text


class LLMError(Exception):
    """The model could not produce a usable reply. The message says why (for logs)."""


@dataclass(frozen=True)
class LLMReply:
    text: str
    model: str
    prompt_tokens: int | None  # how much the model read
    answer_tokens: int | None  # how much it wrote


def chat(messages: list[dict], *, json_schema: dict | None = None,
         max_tokens: int | None = None) -> LLMReply:
    """Send a conversation (system + user messages) and return the model's reply.

    json_schema: make Ollama answer with JSON of exactly this shape (constrained decoding).
    max_tokens: a different cap on the reply length than the default.
    """
    url = f"{settings.ollama_url}/api/chat"
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": False,  # one complete reply, not word by word
        "options": {
            "temperature": settings.llm_temperature,
            "num_ctx": settings.llm_context_tokens,
            "num_predict": max_tokens or settings.llm_max_answer_tokens,
        },
    }
    if json_schema is not None:
        payload["format"] = json_schema
    try:
        response = httpx.post(url, json=payload, timeout=settings.llm_timeout_seconds)
    except httpx.TimeoutException as error:
        raise LLMError(f"The language model did not answer within {settings.llm_timeout_seconds:g} seconds") from error
    except httpx.HTTPError as error:
        raise LLMError(f"Cannot reach Ollama at {settings.ollama_url}. Is it running?") from error

    if response.status_code == 404:
        raise LLMError(f"The model {settings.llm_model} is not installed. Run: ollama pull {settings.llm_model}")
    if response.status_code != 200:
        raise LLMError(f"Ollama error {response.status_code}: {_error_text(response)}")

    try:
        body = response.json()
        content = body["message"]["content"]
    except (ValueError, KeyError, TypeError) as error:
        raise LLMError("Ollama returned a malformed response") from error
    if not isinstance(content, str):
        raise LLMError("Ollama returned a malformed response")
    if not content.strip():
        raise LLMError("The language model returned an empty answer")
    return LLMReply(
        text=content.strip(),
        model=str(body.get("model") or settings.llm_model),
        prompt_tokens=body.get("prompt_eval_count"),
        answer_tokens=body.get("eval_count"),
    )
