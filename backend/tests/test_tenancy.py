"""Phase 8: multi-tenancy. Two businesses with realistic data; nothing may cross between them.

Business A is "Acme Store" (the default test business, code "acme").
Business B is "Globex Retail" (code "globex").
Both have a customer, an agent, an admin, a "Billing" category, a ticket and a refund policy.
The two policies point in exactly the same direction for the search, so if isolation failed
anywhere, the other business's chunk would score just as high and show up.
"""
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models import Business, Category, Document, DocumentChunk, DocumentStatus, IndexStatus, Role, Ticket
from tests.test_ask import ollama, vector  # noqa: F401  (a fixture, found by name)

A_POLICY = "Refund Policy. Refunds are available within 30 days of purchase."
B_POLICY = "Refund Policy. Refunds are available within 7 days of purchase."


def seed_document(session_factory, business_id, uploader_id, title, text):
    with session_factory() as db:
        document = Document(title=title, original_filename=f"{title}.txt", stored_filename=f"{uuid.uuid4().hex}.txt",
                            content_type="text/plain", size_bytes=len(text), uploaded_by_id=uploader_id,
                            business_id=business_id, status=DocumentStatus.EXTRACTED, extracted_text=text,
                            index_status=IndexStatus.INDEXED, chunk_count=1)
        db.add(document)
        db.flush()
        db.add(DocumentChunk(document_id=document.id, chunk_index=0, text=text, word_count=len(text.split()),
                             embedding=vector(refund=1), embedding_model="nomic-embed-text"))
        db.commit()
        return document.id


def seed_category(session_factory, business_id, name):
    with session_factory() as db:
        category = Category(name=name, business_id=business_id)
        db.add(category)
        db.commit()
        return category.id


@pytest.fixture()
def world(client, make_user, session_factory, default_business):
    """Two complete businesses."""
    with session_factory() as db:
        globex = Business(name="Globex Retail", slug="globex")
        db.add(globex)
        db.commit()
        b_id = globex.id
    a, b = SimpleNamespace(id=default_business.id), SimpleNamespace(id=b_id)
    for biz, tag in ((a, "a"), (b, "b")):
        biz.customer = make_user(Role.CUSTOMER, f"customer-{tag}@example.com", name=f"Customer {tag.upper()}",
                                 business_id=biz.id)
        biz.agent = make_user(Role.AGENT, f"agent-{tag}@example.com", name=f"Agent {tag.upper()}", business_id=biz.id)
        biz.admin = make_user(Role.ADMIN, f"admin-{tag}@example.com", name=f"Admin {tag.upper()}", business_id=biz.id)
        biz.category = seed_category(session_factory, biz.id, "Billing")  # the same name in both: allowed
        biz.ticket = client.post("/tickets", headers=biz.customer.headers, json={
            "title": f"Charged twice ({tag.upper()})", "description": f"I was charged twice at business {tag.upper()}."
        }).json()["id"]
        biz.document = seed_document(session_factory, biz.id, biz.admin.id, f"Refund policy {tag.upper()}",
                                     A_POLICY if tag == "a" else B_POLICY)
    return SimpleNamespace(a=a, b=b)


def as_(user):
    return {"headers": user.headers}


# ======================================================================== onboarding and login

def test_a_new_business_signs_up_with_its_first_admin(client):
    response = client.post("/businesses", json={"business_name": "Initech Support", "business_slug": "Initech",
                                                "full_name": "Peter Admin", "email": "peter@initech.example",
                                                "password": "password123"})
    assert response.status_code == 201
    body = response.json()
    assert (body["business"]["name"], body["business"]["slug"]) == ("Initech Support", "initech")
    assert body["admin"]["role"] == "ADMIN"
    login = client.post("/auth/login", data={"username": "peter@initech.example", "password": "password123"}).json()
    assert login["business_name"] == "Initech Support"
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {login['access_token']}"}).json()
    assert me["business"] == body["business"]
    claims = jwt.decode(login["access_token"], options={"verify_signature": False})
    assert claims["bid"] == body["business"]["id"]  # the token carries the business


def test_business_code_must_be_unique_and_valid(client):
    base = {"business_name": "Another Acme", "full_name": "Someone", "password": "password123"}
    assert client.post("/businesses", json={**base, "business_slug": "acme", "email": "x@example.com"}).status_code == 409
    for bad in ("no spaces", "ab", "under_score", "-dash"):
        assert client.post("/businesses", json={**base, "business_slug": bad, "email": "y@example.com"}).status_code == 422


def test_failed_signup_leaves_no_business_behind(client, make_user, session_factory):
    make_user(Role.CUSTOMER, "taken@example.com")
    response = client.post("/businesses", json={"business_name": "Umbrella", "business_slug": "umbrella",
                                                "full_name": "Admin", "email": "taken@example.com",
                                                "password": "password123"})
    assert response.status_code == 409  # the email is taken...
    with session_factory() as db:  # ...and the half-created business was rolled back
        assert db.scalar(select(Business).where(Business.slug == "umbrella")) is None


def test_public_lookup_shows_only_the_name(client, world):
    body = client.get("/businesses/GLOBEX").json()
    assert body == {"name": "Globex Retail", "slug": "globex"}
    assert client.get("/businesses/nope").status_code == 404


def test_customer_registers_on_a_business_portal(client, world):
    response = client.post("/auth/register", json={"full_name": "Nina", "email": "nina@example.com",
                                                   "password": "password123", "business": "globex"})
    assert response.status_code == 201
    token = client.post("/auth/login", data={"username": "nina@example.com", "password": "password123"}).json()
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token['access_token']}"}).json()
    assert (me["role"], me["business"]["slug"]) == ("CUSTOMER", "globex")


@pytest.mark.parametrize("business, code", [("does-not-exist", 404), (None, 422)])
def test_registration_needs_an_existing_business(client, business, code):
    body = {"full_name": "Nina", "email": "nina@example.com", "password": "password123"}
    if business:
        body["business"] = business
    assert client.post("/auth/register", json=body).status_code == code


def test_one_email_cannot_join_two_businesses(client, world):
    response = client.post("/auth/register", json={"full_name": "Dup", "email": "customer-a@example.com",
                                                   "password": "password123", "business": "globex"})
    assert response.status_code == 409  # emails are unique across all businesses


def sign(claims):
    payload = {"exp": datetime.now(timezone.utc) + timedelta(minutes=5), **claims}
    return {"Authorization": f"Bearer {jwt.encode(payload, settings.jwt_secret_key, algorithm='HS256')}"}


def test_token_business_must_match_the_users_business(client, world):
    user = world.a.customer
    assert client.get("/auth/me", headers=sign({"sub": str(user.id), "bid": world.a.id})).status_code == 200
    # A correctly signed token that claims a different business is refused.
    assert client.get("/auth/me", headers=sign({"sub": str(user.id), "bid": world.b.id})).status_code == 401
    # So is a token from before multi-tenancy, with no business in it.
    assert client.get("/auth/me", headers=sign({"sub": str(user.id)})).status_code == 401


def test_disabled_business_is_locked_out(client, world, session_factory):
    with session_factory() as db:
        db.get(Business, world.b.id).is_active = False
        db.commit()
    assert client.get("/tickets", **as_(world.b.customer)).status_code == 401  # existing tokens stop working
    login = client.post("/auth/login", data={"username": "customer-b@example.com", "password": "password123"})
    assert login.status_code == 403
    assert client.get("/tickets", **as_(world.a.customer)).status_code == 200  # A is unaffected
    assert client.get("/businesses/globex").status_code == 404


# ======================================================================== tickets

def test_1_customer_cannot_read_another_business_ticket(client, world):
    assert client.get(f"/tickets/{world.b.ticket}", **as_(world.a.customer)).status_code == 404
    assert [t["id"] for t in client.get("/tickets", **as_(world.a.customer)).json()] == [world.a.ticket]


def test_2_customer_cannot_modify_another_business_ticket(client, world):
    url = f"/tickets/{world.b.ticket}"
    assert client.post(f"{url}/messages", json={"message": "hello"}, **as_(world.a.customer)).status_code == 404
    assert client.get(url, **as_(world.b.customer)).json()["messages"] == []  # nothing arrived


def test_8_agent_cannot_access_another_business_ticket(client, world):
    agent, url = world.a.agent, f"/tickets/{world.b.ticket}"
    assert client.get(url, **as_(agent)).status_code == 404
    assert client.post(f"{url}/assign", json={"agent_id": agent.agent_id}, **as_(agent)).status_code == 404
    assert client.post(f"{url}/messages", json={"message": "hi"}, **as_(agent)).status_code == 404
    assert client.patch(url, json={"priority": "URGENT"}, **as_(agent)).status_code == 404
    assert client.post(f"{url}/escalate", json={"reason": "Because I can"}, **as_(agent)).status_code == 404
    # Business B's unassigned ticket is not in business A's queue.
    queue = [t["id"] for t in client.get("/tickets?unassigned=true", **as_(agent)).json()]
    assert queue == [world.a.ticket]
    b_ticket = client.get(url, **as_(world.b.admin)).json()
    assert (b_ticket["priority"], b_ticket["assigned_agent"], b_ticket["status"]) == ("MEDIUM", None, "OPEN")


def test_12_ticket_ai_cannot_analyse_another_business_ticket(client, world, fake_ollama):
    assert client.post(f"/tickets/{world.b.ticket}/ai-analysis", **as_(world.a.agent)).status_code == 404
    assert client.post(f"/tickets/{world.b.ticket}/ai-analysis", **as_(world.a.admin)).status_code == 404
    assert fake_ollama.chats == []  # the model never saw B's ticket


def test_ticket_ai_only_offers_the_tickets_own_categories(client, world, fake_ollama, session_factory):
    seed_category(session_factory, world.b.id, "Globex Secret Category")
    fake_ollama.chat_reply = '{"category": "Globex Secret Category", "priority": "HIGH", "sentiment": "negative",' \
                             ' "summary": "Charged twice.", "suggested_reply": "We are checking."}'
    body = client.post(f"/tickets/{world.a.ticket}/ai-analysis", **as_(world.a.agent)).json()
    [request] = fake_ollama.chats
    assert "Globex" not in str(request)  # B's category names never reach the model for A's ticket
    assert request["format"]["properties"]["category"]["enum"] == ["Billing", "none"]
    assert body["category"] is None  # and B's category cannot be suggested for A's ticket
    assert "Charged twice (B)" not in str(request) and "business B" not in str(request)


# ======================================================================== admin

def test_9_admin_cannot_reach_another_business(client, world):
    admin = world.a.admin
    assert client.get(f"/tickets/{world.b.ticket}", **as_(admin)).status_code == 404
    assert client.patch(f"/tickets/{world.b.ticket}", json={"status": "RESOLVED"}, **as_(admin)).status_code == 404
    emails = {u["email"] for u in client.get("/admin/users", **as_(admin)).json()}
    assert emails == {"customer-a@example.com", "agent-a@example.com", "admin-a@example.com"}
    assert client.patch(f"/admin/users/{world.b.customer.id}", json={"is_active": False},
                        **as_(admin)).status_code == 404
    assert [a["user"]["email"] for a in client.get("/admin/agents", **as_(admin)).json()] == ["agent-a@example.com"]
    assert [c["id"] for c in client.get("/admin/categories", **as_(admin)).json()] == [world.a.category]
    assert client.patch(f"/admin/categories/{world.b.category}", json={"name": "Hacked"},
                        **as_(admin)).status_code == 404
    assert [d["id"] for d in client.get("/admin/documents", **as_(admin)).json()] == [world.a.document]
    # B is untouched.
    assert client.post("/auth/login", data={"username": "customer-b@example.com",
                                            "password": "password123"}).status_code == 200
    assert client.get("/admin/categories", **as_(world.b.admin)).json()[0]["name"] == "Billing"


def test_15_statistics_only_count_the_current_business(client, world):
    client.post("/tickets", headers=world.b.customer.headers,
                json={"title": "Second B ticket", "description": "Another problem at business B."})
    a = client.get("/admin/stats", **as_(world.a.admin)).json()
    b = client.get("/admin/stats", **as_(world.b.admin)).json()
    assert (a["total_tickets"], b["total_tickets"]) == (1, 2)
    assert a["users_by_role"] == {"CUSTOMER": 1, "AGENT": 1, "ADMIN": 1}


def test_staff_lists_only_show_their_own_business(client, world):
    assert [a["user"]["full_name"] for a in client.get("/agents", **as_(world.a.agent)).json()] == ["Agent A"]
    assert [c["id"] for c in client.get("/categories", **as_(world.a.customer)).json()] == [world.a.category]


# ======================================================================== ids from another business

def test_10_ids_from_another_business_cannot_be_used(client, world):
    a = world.a
    # A category of B, on a new ticket or an existing one: treated as if it did not exist.
    response = client.post("/tickets", json={"title": "Wrong category", "description": "Using B's category id.",
                                             "category_id": world.b.category}, **as_(a.customer))
    assert response.status_code == 400
    assert client.patch(f"/tickets/{a.ticket}", json={"category_id": world.b.category},
                        **as_(a.admin)).status_code == 400
    # An agent of B cannot be given A's ticket.
    assert client.post(f"/tickets/{a.ticket}/assign", json={"agent_id": world.b.agent.agent_id},
                       **as_(a.admin)).status_code == 404


def test_11_business_id_sent_by_the_client_is_ignored_or_rejected(client, world, session_factory):
    a, b = world.a, world.b
    ticket = client.post("/tickets", json={"title": "Sneaky ticket", "description": "Trying to post into B.",
                                           "business_id": b.id}, **as_(a.customer)).json()
    with session_factory() as db:
        assert db.get(Ticket, ticket["id"]).business_id == a.id  # ignored: the login decides
    category = client.post("/admin/categories", json={"name": "Sneaky", "business_id": b.id}, **as_(a.admin)).json()
    with session_factory() as db:
        assert db.get(Category, category["id"]).business_id == a.id
    # Endpoints that forbid unknown fields reject it outright.
    assert client.post("/admin/documents/search", json={"query": "refund?", "business_id": b.id},
                       **as_(a.admin)).status_code == 422
    assert client.post("/ai/ask", json={"question": "refund?", "business_id": b.id},
                       **as_(a.customer)).status_code == 422


# ======================================================================== knowledge base

def test_3_4_documents_of_another_business_cannot_be_read_or_deleted(client, world, session_factory):
    doc, admin = world.b.document, world.a.admin
    for customer in (world.a.customer, world.b.customer):  # customers never reach document endpoints
        assert client.get("/admin/documents", **as_(customer)).status_code == 403
        assert client.delete(f"/admin/documents/{doc}", **as_(customer)).status_code == 403
    assert client.get(f"/admin/documents/{doc}/text", **as_(admin)).status_code == 404
    assert client.get(f"/admin/documents/{doc}/chunks", **as_(admin)).status_code == 404
    assert client.delete(f"/admin/documents/{doc}", **as_(admin)).status_code == 404
    with session_factory() as db:
        assert db.get(Document, doc) is not None  # still there


def test_13_indexing_stays_within_the_business(client, world, session_factory, fake_ollama):
    doc = world.b.document
    assert client.post(f"/admin/documents/{doc}/index", **as_(world.a.admin)).status_code == 404
    assert client.post(f"/admin/documents/{doc}/extract", **as_(world.a.admin)).status_code == 404
    assert fake_ollama.requests == []  # nothing of B's was embedded on A's request
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(DocumentChunk)
                         .where(DocumentChunk.document_id == doc)) == 1


def test_uploads_belong_to_the_uploaders_business(client, world, session_factory, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", tmp_path)
    doc = client.post("/admin/documents", data={"title": "Globex shipping", "business_id": str(world.a.id)},
                      files={"file": ("ship.txt", b"Globex ships in 2 days.")}, **as_(world.b.admin)).json()
    with session_factory() as db:
        assert db.get(Document, doc["id"]).business_id == world.b.id
    assert doc["id"] not in [d["id"] for d in client.get("/admin/documents", **as_(world.a.admin)).json()]


def test_14_semantic_search_never_returns_another_business_chunk(client, world, ollama):
    ollama(question_vector=vector(refund=1))  # equally close to BOTH businesses' policies
    a = client.post("/admin/documents/search", json={"query": "refund time limit?", "threshold": 0},
                    **as_(world.a.admin)).json()
    b = client.post("/admin/documents/search", json={"query": "refund time limit?", "threshold": 0},
                    **as_(world.b.admin)).json()
    assert [r["text"] for r in a["results"]] == [A_POLICY] and a["chunks_searched"] == 1
    assert [r["text"] for r in b["results"]] == [B_POLICY] and b["chunks_searched"] == 1


def test_5_customer_cannot_search_knowledge_directly(client, world):
    assert client.post("/admin/documents/search", json={"query": "refunds?"},
                       **as_(world.a.customer)).status_code == 403


def test_6_rag_only_uses_the_customers_own_business_knowledge(client, world, ollama):
    fake = ollama(question_vector=vector(refund=1), reply="Refunds are available within 30 days of purchase.")
    a = client.post("/ai/ask", json={"question": "How long do I have for a refund?"}, **as_(world.a.customer)).json()
    [a_prompt] = fake.chats
    assert "30 days" in a_prompt["messages"][1]["content"] and "7 days" not in a_prompt["messages"][1]["content"]
    assert [s["document_title"] for s in a["sources"]] == ["Refund policy A"]

    fake.chats.clear()
    fake.chat_reply = "Refunds are available within 7 days of purchase."
    b = client.post("/ai/ask", json={"question": "How long do I have for a refund?"}, **as_(world.b.customer)).json()
    [b_prompt] = fake.chats
    assert "7 days" in b_prompt["messages"][1]["content"] and "30 days" not in b_prompt["messages"][1]["content"]
    assert [s["document_title"] for s in b["sources"]] == ["Refund policy B"]


def test_empty_knowledge_base_in_one_business_is_not_filled_from_another(client, world, ollama, session_factory):
    with session_factory() as db:
        db.query(DocumentChunk).filter(DocumentChunk.document_id == world.b.document).delete()
        db.get(Document, world.b.document).index_status = IndexStatus.NOT_INDEXED
        db.commit()
    fake = ollama(question_vector=vector(refund=1))
    body = client.post("/ai/ask", json={"question": "Refund window?"}, **as_(world.b.customer)).json()
    assert body["status"] == "NOT_ENOUGH_INFORMATION" and fake.chats == []  # A's policy is never used for B


# ======================================================================== handoff

def test_7_customer_cannot_use_another_business_handoff(client, world, ollama, session_factory):
    ollama(question_vector=vector(other=1))  # nothing relevant: a handoff is offered
    token = client.post("/ai/ask", json={"question": "Do you sell gift cards?"},
                        **as_(world.b.customer)).json()["handoff_token"]
    assert jwt.decode(token, options={"verify_signature": False})["bid"] == world.b.id
    response = client.post("/tickets", json={"title": "Stolen handoff", "description": "Using B's handoff token.",
                                             "handoff_token": token}, **as_(world.a.customer))
    assert (response.status_code, response.json()["detail"]) == (400, "This AI handoff is not valid.")
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.handoff_id.is_not(None))) == 0


def test_handoff_with_a_mismatched_business_is_rejected(client, world):
    a = world.a
    claims = {"aud": "ai-handoff", "sub": str(a.customer.id), "bid": world.b.id, "jti": uuid.uuid4().hex,
              "iat": datetime.now(timezone.utc), "question": "q?", "ai_status": "NOT_ENOUGH_INFORMATION",
              "reason": "r", "sources": []}
    token = jwt.encode({**claims, "exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
                       settings.jwt_secret_key, algorithm="HS256")
    response = client.post("/tickets", json={"title": "Mismatched", "description": "A token for the wrong business.",
                                             "handoff_token": token}, **as_(a.customer))
    assert response.status_code == 400


def test_handoff_ticket_lands_in_the_customers_business(client, world, ollama, session_factory):
    ollama(question_vector=vector(other=1))
    token = client.post("/ai/ask", json={"question": "Do you sell gift cards?"},
                        **as_(world.b.customer)).json()["handoff_token"]
    ticket = client.post("/tickets", json={"title": "Gift cards?", "description": "Handed over from the AI.",
                                           "handoff_token": token}, **as_(world.b.customer)).json()
    with session_factory() as db:
        assert db.get(Ticket, ticket["id"]).business_id == world.b.id
    assert ticket["id"] in [t["id"] for t in client.get("/tickets?unassigned=true", **as_(world.b.agent)).json()]
    assert ticket["id"] not in [t["id"] for t in client.get("/tickets?unassigned=true", **as_(world.a.agent)).json()]


# ======================================================================== legitimate same-business work

def test_same_business_workflow_still_works(client, world):
    b = world.b
    ticket = client.post("/tickets", json={"title": "Wrong item sent", "description": "I got the wrong size.",
                                           "category_id": b.category}, **as_(b.customer)).json()
    url = f"/tickets/{ticket['id']}"
    assert client.post(f"{url}/assign", json={"agent_id": b.agent.agent_id}, **as_(b.agent)).status_code == 200
    assert client.post(f"{url}/messages", json={"message": "Sorry! A new one is on its way."},
                       **as_(b.agent)).status_code == 201
    assert client.patch(url, json={"status": "RESOLVED"}, **as_(b.agent)).json()["status"] == "RESOLVED"
    seen = client.get(url, **as_(b.customer)).json()
    assert seen["messages"][0]["message"] == "Sorry! A new one is on its way."
    assert client.get(url, **as_(b.admin)).status_code == 200


def test_category_names_are_unique_per_business_only(client, world):
    # Both businesses already have "Billing"; each may not have it twice.
    assert client.post("/admin/categories", json={"name": "billing"}, **as_(world.a.admin)).status_code == 409
    assert client.post("/admin/categories", json={"name": "Returns"}, **as_(world.a.admin)).status_code == 201
    assert client.post("/admin/categories", json={"name": "Returns"}, **as_(world.b.admin)).status_code == 201


def test_agent_created_by_an_admin_joins_that_business(client, world):
    created = client.post("/admin/agents", json={"full_name": "New Agent", "email": "new-agent@example.com",
                                                 "password": "password123"}, **as_(world.b.admin)).json()
    token = client.post("/auth/login", data={"username": "new-agent@example.com",
                                             "password": "password123"}).json()
    assert token["business_name"] == "Globex Retail"
    assert created["user"]["email"] not in [a["user"]["email"] for a in
                                            client.get("/admin/agents", **as_(world.a.admin)).json()]
