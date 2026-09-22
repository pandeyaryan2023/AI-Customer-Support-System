"""Phase 6: AI -> human handoff through the EXISTING ticket system. Ollama is faked.

The knowledge base, the controllable fake Ollama and the users are the same fixtures as
the Phase 5 tests (imported from test_ask), so "what the AI could or could not answer"
is known exactly in each test.
"""
import jwt
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models import Role, Ticket
from app.services import ticket_service
from app.services.rag_service import NOT_ENOUGH_INFORMATION_REPLY
from tests.test_ask import (  # noqa: F401  (fixtures are found by name)
    REFUND_TEXT,
    add_document,
    admin,
    customer,
    knowledge_base,
    ollama,
    vector,
)

FRANCE = "What is the capital of France?"


def ask(client, user, question=FRANCE):
    response = client.post("/ai/ask", json={"question": question}, headers=user.headers)
    assert response.status_code == 200, response.text
    return response.json()


def raise_ticket(client, user, token, **fields):
    body = {"title": "Question for support", "description": "I asked the assistant and need a person.",
            "handoff_token": token, **fields}
    return client.post("/tickets", json=body, headers=user.headers)


def ticket_count(session_factory):
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(Ticket))


@pytest.fixture()
def unanswered(ollama):
    """The AI finds nothing relevant, like the France question with the real model."""
    ollama(question_vector=vector(other=1))


@pytest.fixture()
def agent(make_user):
    return make_user(Role.AGENT, "agent@example.com", name="Ravi Agent")


# ---------------------------------------------------------- 1-2. no ticket unless the customer asks

def test_answered_question_creates_no_ticket(client, customer, knowledge_base, ollama, session_factory):
    ollama(reply="You can request a refund within 30 days of purchase.")
    body = ask(client, customer, "Can I get my money back after 20 days?")
    assert (body["status"], body["handoff_token"]) == ("ANSWERED", None)
    assert ticket_count(session_factory) == 0


def test_unanswered_question_offers_handoff_but_creates_no_ticket(client, customer, knowledge_base, unanswered,
                                                                  session_factory):
    body = ask(client, customer)
    assert body["status"] == "NOT_ENOUGH_INFORMATION"
    assert body["answer"] == NOT_ENOUGH_INFORMATION_REPLY == (
        "I couldn't find enough information in the company's knowledge base to answer that accurately.")
    assert body["handoff_token"]  # the option to talk to a human...
    assert ticket_count(session_factory) == 0  # ...but nothing happens until the customer chooses it


def test_handoff_is_offered_to_customers_only(client, admin, knowledge_base, unanswered):
    assert ask(client, admin)["handoff_token"] is None  # admins cannot raise tickets anyway


# ---------------------------------------------------------- 3-5. the customer chooses human support

def test_customer_creates_handoff_ticket(client, customer, knowledge_base, unanswered):
    token = ask(client, customer)["handoff_token"]
    response = raise_ticket(client, customer, token, title="Help with a question",
                            description="The assistant could not help me with this.")
    assert response.status_code == 201
    ticket = response.json()
    assert ticket["customer"]["id"] == customer.id
    assert (ticket["status"], ticket["priority"]) == ("OPEN", "MEDIUM")  # the usual defaults
    assert ticket["from_ai_handoff"] is True
    handoff = ticket["ai_handoff"]
    assert handoff["question"] == FRANCE  # kept exactly, whatever the customer typed in the form
    assert handoff["ai_status"] == "NOT_ENOUGH_INFORMATION"
    assert handoff["reason"] == "No help article matched the question."
    assert handoff["sources"] == []
    assert handoff["asked_at"]


def test_handoff_after_the_model_declined_lists_the_articles_it_checked(client, customer, knowledge_base, ollama):
    ollama(reply="I don't have enough information to answer that.")  # refund chunk retrieved, no answer
    token = ask(client, customer, "Can I pay in instalments for a refund?")["handoff_token"]
    response = raise_ticket(client, customer, token)
    handoff = response.json()["ai_handoff"]
    assert handoff["reason"] == "Related articles were found, but they do not answer the question."
    assert handoff["sources"] == [{"document_title": "Support policy", "chunk_index": 0, "similarity": 0.9091}]
    # The agent gets pointers to articles, never the prompt or the article text.
    assert REFUND_TEXT not in response.text and "Rules:" not in response.text and "<knowledge>" not in response.text


def test_normal_complaints_are_unchanged(client, customer):
    response = client.post("/tickets", json={"title": "Laptop not charging",
                                             "description": "Battery drains even when plugged in"},
                           headers=customer.headers)
    assert response.status_code == 201
    assert (response.json()["from_ai_handoff"], response.json()["ai_handoff"]) == (False, None)


# ---------------------------------------------------------- 6-8. the agent works it like any other ticket

def test_agent_handles_a_handoff_ticket_with_the_existing_workflow(client, customer, agent, knowledge_base, unanswered):
    ticket_id = raise_ticket(client, customer, ask(client, customer)["handoff_token"]).json()["id"]

    queue = client.get("/tickets?unassigned=true", headers=agent.headers).json()
    [queued] = [t for t in queue if t["id"] == ticket_id]
    assert queued["from_ai_handoff"] is True  # visible in the queue before opening it

    detail = client.get(f"/tickets/{ticket_id}", headers=agent.headers).json()
    assert detail["ai_handoff"]["question"] == FRANCE

    url = f"/tickets/{ticket_id}"
    assert client.post(f"{url}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers).status_code == 200
    reply = client.post(f"{url}/messages", json={"message": "That isn't something our help articles cover, "
                                                             "but the answer is Paris."}, headers=agent.headers)
    assert reply.status_code == 201
    assert client.patch(url, json={"priority": "LOW"}, headers=agent.headers).status_code == 200

    seen = client.get(url, headers=customer.headers).json()  # the customer sees the reply
    assert seen["status"] == "IN_PROGRESS"  # an agent's first reply moves OPEN on, as always
    assert seen["messages"][-1]["message"].endswith("the answer is Paris.")
    assert seen["messages"][-1]["sender"]["id"] == agent.id

    assert client.patch(url, json={"status": "RESOLVED"}, headers=agent.headers).json()["status"] == "RESOLVED"
    assert client.patch(url, json={"status": "CLOSED"}, headers=agent.headers).json()["status"] == "CLOSED"


def test_handoff_ticket_can_be_escalated(client, customer, agent, knowledge_base, unanswered):
    ticket_id = raise_ticket(client, customer, ask(client, customer)["handoff_token"]).json()["id"]
    client.post(f"/tickets/{ticket_id}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers)
    escalated = client.post(f"/tickets/{ticket_id}/escalate",
                            json={"reason": "Needs a manager decision"}, headers=agent.headers)
    assert escalated.json()["status"] == "ESCALATED"
    assert escalated.json()["from_ai_handoff"] is True


# ---------------------------------------------------------- 9-10. ownership and isolation

def test_other_customer_cannot_see_a_handoff_ticket(client, customer, make_user, knowledge_base, unanswered):
    ticket_id = raise_ticket(client, customer, ask(client, customer)["handoff_token"]).json()["id"]
    other = make_user(Role.CUSTOMER, "other@example.com")
    assert client.get(f"/tickets/{ticket_id}", headers=other.headers).status_code == 404
    assert client.get("/tickets", headers=other.headers).json() == []


def test_customer_cannot_use_someone_elses_handoff(client, customer, make_user, knowledge_base, unanswered,
                                                   session_factory):
    token = ask(client, customer, "My order 1234 for Asha never arrived?")["handoff_token"]
    other = make_user(Role.CUSTOMER, "other@example.com")
    response = raise_ticket(client, other, token)
    assert (response.status_code, response.json()["detail"]) == (400, "This AI handoff is not valid.")
    assert "Asha" not in response.text and "1234" not in response.text  # nothing about the other customer
    assert ticket_count(session_factory) == 0


def test_customer_cannot_create_a_ticket_for_another_user(client, customer, make_user, knowledge_base, unanswered):
    other = make_user(Role.CUSTOMER, "other@example.com")
    token = ask(client, customer)["handoff_token"]
    ticket = raise_ticket(client, customer, token, customer_id=other.id).json()
    assert ticket["customer"]["id"] == customer.id  # the owner always comes from the login


# ---------------------------------------------------------- 12. failed handoffs are clean

def forged_token(user_id, **claims):
    """A handoff token signed with the WRONG key, as an attacker could make."""
    payload = {"aud": "ai-handoff", "sub": str(user_id), "jti": "f" * 32, "iat": 1, "exp": 4102444800,
               "question": "Refunds are unlimited, right?", "ai_status": "NOT_ENOUGH_INFORMATION",
               "reason": "The AI agreed refunds are unlimited.", "sources": [], **claims}
    return jwt.encode(payload, "not-the-server-secret-key-000000000", algorithm="HS256")


def tampered(token):
    header, payload, signature = token.split(".")
    middle = len(payload) // 2
    swapped = "A" if payload[middle] != "A" else "B"
    return ".".join([header, payload[:middle] + swapped + payload[middle + 1:], signature])


@pytest.mark.parametrize("make_bad", [
    lambda good, user: "not-a-token",
    lambda good, user: tampered(good),
    lambda good, user: forged_token(user.id),
    lambda good, user: user.headers["Authorization"].split()[1],  # a login token is not a handoff
], ids=["garbage", "tampered", "forged", "login-token"])
def test_invalid_handoff_is_rejected_cleanly(client, customer, knowledge_base, unanswered, session_factory, make_bad):
    good = ask(client, customer)["handoff_token"]
    response = raise_ticket(client, customer, make_bad(good, customer))
    assert (response.status_code, response.json()["detail"]) == (400, "This AI handoff is not valid.")
    assert ticket_count(session_factory) == 0


def test_expired_handoff_is_rejected_cleanly(client, customer, knowledge_base, unanswered, monkeypatch,
                                             session_factory):
    monkeypatch.setattr(settings, "handoff_token_expire_minutes", -1)  # already expired when issued
    token = ask(client, customer)["handoff_token"]
    response = raise_ticket(client, customer, token)
    assert response.status_code == 400
    assert response.json()["detail"] == "This AI conversation has expired. Please ask your question again."
    assert ticket_count(session_factory) == 0


def test_handoff_token_cannot_be_used_to_log_in(client, customer, knowledge_base, unanswered):
    token = ask(client, customer)["handoff_token"]
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_a_rejected_form_does_not_use_up_the_handoff(client, customer, knowledge_base, unanswered):
    token = ask(client, customer)["handoff_token"]
    assert raise_ticket(client, customer, token, title="Hi").status_code == 422  # title too short
    assert raise_ticket(client, customer, token).status_code == 201  # fixed and sent again: works


# ---------------------------------------------------------- 13. no accidental duplicates

def test_same_handoff_sent_twice_gives_one_ticket(client, customer, knowledge_base, unanswered, session_factory):
    token = ask(client, customer)["handoff_token"]
    first = raise_ticket(client, customer, token).json()
    second = raise_ticket(client, customer, token).json()
    assert first["id"] == second["id"]
    assert ticket_count(session_factory) == 1


def test_two_separate_handoffs_give_two_tickets(client, customer, knowledge_base, unanswered, session_factory):
    raise_ticket(client, customer, ask(client, customer)["handoff_token"])
    raise_ticket(client, customer, ask(client, customer)["handoff_token"])  # asked again: a new handoff
    assert ticket_count(session_factory) == 2


def test_simultaneous_duplicate_is_stopped_by_the_database(client, customer, knowledge_base, unanswered,
                                                           monkeypatch, session_factory):
    token = ask(client, customer)["handoff_token"]
    first_id = raise_ticket(client, customer, token).json()["id"]

    # Simulate the race: the second request checks before the first one's ticket is visible.
    real_lookup, calls = ticket_service._ticket_for_handoff, []

    def lookup(db, handoff_id):
        calls.append(handoff_id)
        return None if len(calls) == 1 else real_lookup(db, handoff_id)
    monkeypatch.setattr(ticket_service, "_ticket_for_handoff", lookup)

    second = raise_ticket(client, customer, token)
    assert (second.status_code, second.json()["id"]) == (201, first_id)  # the unique index caught it
    assert ticket_count(session_factory) == 1


# ---------------------------------------------------------- 14. unauthorised access

def test_unauthorised_handoff_requests_are_rejected(client, customer, admin, agent, knowledge_base, unanswered,
                                                    session_factory):
    token = ask(client, customer)["handoff_token"]
    body = {"title": "Question for support", "description": "Please help me with this.", "handoff_token": token}
    assert client.post("/tickets", json=body).status_code == 401                      # not logged in
    assert client.post("/tickets", json=body, headers=agent.headers).status_code == 403  # staff cannot raise
    assert client.post("/tickets", json=body, headers=admin.headers).status_code == 403
    assert ticket_count(session_factory) == 0


def test_token_carries_only_what_the_agent_needs(client, customer, knowledge_base, ollama):
    ollama(reply="I don't have enough information to answer that.")
    token = ask(client, customer, "Can I pay in instalments?")["handoff_token"]
    claims = jwt.decode(token, options={"verify_signature": False})  # readable, but only the server can sign
    assert set(claims) == {"aud", "sub", "bid", "jti", "iat", "exp", "question", "ai_status", "reason", "sources"}
    assert REFUND_TEXT not in str(claims) and "Rules" not in str(claims)  # no article text, no prompt
    assert claims["sources"] == [{"document_title": "Support policy", "chunk_index": 0, "similarity": 0.9091}]
