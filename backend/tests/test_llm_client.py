"""Phase 5: the Ollama chat client. Ollama itself is always faked here."""
import httpx
import pytest

from app.services.llm_client import LLMError, chat

MESSAGES = [{"role": "system", "content": "rules"}, {"role": "user", "content": "question"}]


def ollama_replies(monkeypatch, status_code=200, body=None, content=None):
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


def test_reply_is_returned(fake_ollama):
    fake_ollama.chat_reply = "  Refunds are accepted within 30 days.  "
    reply = chat(MESSAGES)
    assert reply.text == "Refunds are accepted within 30 days."  # surrounding whitespace removed
    assert (reply.model, reply.prompt_tokens, reply.answer_tokens) == ("llama3.2:3b", 100, 10)


def test_request_sent_to_ollama(fake_ollama):
    chat(MESSAGES)
    [request] = fake_ollama.chats
    assert request == {
        "model": "llama3.2:3b",
        "messages": MESSAGES,
        "stream": False,
        "options": {"temperature": 0.0, "num_ctx": 4096, "num_predict": 200},
    }


def test_ollama_not_running(monkeypatch):
    ollama_raises(monkeypatch, httpx.ConnectError("connection refused"))
    with pytest.raises(LLMError, match="Cannot reach Ollama"):
        chat(MESSAGES)


def test_timeout(monkeypatch):
    ollama_raises(monkeypatch, httpx.ReadTimeout("timed out"))
    with pytest.raises(LLMError, match="did not answer within 180 seconds"):
        chat(MESSAGES)


def test_model_not_installed(monkeypatch):
    ollama_replies(monkeypatch, 404, {"error": "model 'llama3.2:3b' not found"})
    with pytest.raises(LLMError, match="not installed. Run: ollama pull llama3.2:3b"):
        chat(MESSAGES)


def test_other_ollama_error(monkeypatch):
    ollama_replies(monkeypatch, 500, {"error": "out of memory"})
    with pytest.raises(LLMError, match="Ollama error 500: out of memory"):
        chat(MESSAGES)


@pytest.mark.parametrize("reply", [
    {"content": b"<html>gateway error</html>"},
    {"body": {"model": "llama3.2:3b"}},                      # no message
    {"body": {"message": "just a string"}},                  # wrong shape
    {"body": {"message": {"role": "assistant"}}},            # no content
    {"body": {"message": {"content": 42}}},                  # content is not text
], ids=["not-json", "no-message", "message-not-object", "no-content", "content-not-text"])
def test_malformed_reply(monkeypatch, reply):
    ollama_replies(monkeypatch, **reply)
    with pytest.raises(LLMError, match="malformed"):
        chat(MESSAGES)


@pytest.mark.parametrize("content", ["", "   \n  "], ids=["empty", "whitespace"])
def test_empty_reply(monkeypatch, content):
    ollama_replies(monkeypatch, body={"message": {"role": "assistant", "content": content}})
    with pytest.raises(LLMError, match="empty answer"):
        chat(MESSAGES)
