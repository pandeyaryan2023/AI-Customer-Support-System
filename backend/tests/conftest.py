import json as jsonlib
import os
import random
from types import SimpleNamespace

# Set BEFORE the app is imported, so tests can never touch the real PostgreSQL database.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET_KEY"] = "test-secret-key-only-for-automated-tests"
# A closed port: even if a call slipped past the fake below, it could not reach a real Ollama.
os.environ["OLLAMA_URL"] = "http://127.0.0.1:9"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.database.base import Base  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Agent, Business, Category, Role, User  # noqa: E402

PASSWORD = "password123"


class FakeOllama:
    """Stands in for the local Ollama server, so no test needs Ollama running.

    Answers POST /api/embed like the real one: one vector of embedding_dimension numbers
    per input. The numbers are derived from the text, so the same text always gets the
    same vector, and different texts get different vectors.

    Answers POST /api/chat with `chat_reply`, and records each conversation it was sent.

    An intent-classification request (the one carrying the intent router's JSON schema) is
    answered with `intent_reply` and recorded in `intents` instead, so tests of the answering
    paths see only the conversations meant for them.
    """

    def __init__(self):
        self.requests = []  # every embedding request "sent to Ollama", for tests to inspect
        self.chats = []     # every chat request, except classification
        self.intents = []   # every intent-classification request
        self.chat_reply = "This is a fake answer."
        self.intent_reply = jsonlib.dumps(
            {"intent": "COMPANY_KNOWLEDGE", "confidence": 0.9, "reason": "asks about the shop"})

    @staticmethod
    def vector(text: str) -> list[float]:
        rng = random.Random(text)
        return [rng.uniform(-1, 1) for _ in range(settings.embedding_dimension)]

    @staticmethod
    def is_classification(payload):
        return "intent" in payload.get("format", {}).get("properties", {})

    def post(self, url, json, timeout):
        if url.endswith("/api/chat"):
            classifying = self.is_classification(json)
            (self.intents if classifying else self.chats).append(json)
            content = self.intent_reply if classifying else self.chat_reply
            body = {"model": json["model"], "message": {"role": "assistant", "content": content},
                    "done": True, "done_reason": "stop", "prompt_eval_count": 100, "eval_count": 10}
        else:
            self.requests.append(json)
            body = {"model": json["model"], "embeddings": [self.vector(text) for text in json["input"]]}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))


@pytest.fixture(autouse=True)
def fake_ollama(monkeypatch):
    """Every test talks to the fake. A test can replace httpx.post again to simulate failures."""
    server = FakeOllama()
    monkeypatch.setattr(httpx, "post", server.post)
    return server


@pytest.fixture()
def session_factory():
    """A fresh in-memory database for every test."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False)
    engine.dispose()


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def default_business(session_factory):
    """The business every test user belongs to unless a test says otherwise (code "acme")."""
    with session_factory() as db:
        business = Business(name="Acme Store", slug="acme")
        db.add(business)
        db.commit()
        return SimpleNamespace(id=business.id, name=business.name, slug=business.slug)


@pytest.fixture()
def make_user(client, session_factory, default_business):
    """Create a user directly in the database, log in, and return their id + auth headers."""

    def _make(role: Role, email: str, name: str = "Test User", business_id: int | None = None):
        business_id = business_id or default_business.id
        with session_factory() as db:
            user = User(full_name=name, email=email, hashed_password=hash_password(PASSWORD), role=role,
                        business_id=business_id)
            db.add(user)
            db.flush()
            agent_id = None
            if role == Role.AGENT:
                agent = Agent(user_id=user.id, department="Support")
                db.add(agent)
                db.flush()
                agent_id = agent.id
            db.commit()
            user_id = user.id
        response = client.post("/auth/login", data={"username": email, "password": PASSWORD})
        assert response.status_code == 200, response.text
        headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
        return SimpleNamespace(id=user_id, agent_id=agent_id, headers=headers, business_id=business_id)

    return _make


@pytest.fixture()
def category_id(session_factory, default_business):
    with session_factory() as db:
        category = Category(name="Billing", business_id=default_business.id)
        db.add(category)
        db.commit()
        return category.id


TICKET = {"title": "Laptop not charging", "description": "Battery drains even when plugged in"}


@pytest.fixture()
def new_ticket(client):
    """Return a function that creates a ticket as the given customer and returns its id."""

    def _create(customer):
        response = client.post("/tickets", json=TICKET, headers=customer.headers)
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return _create
