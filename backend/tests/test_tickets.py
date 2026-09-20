from app.models import Role
from tests.conftest import TICKET


def test_customer_creates_and_lists_only_own_tickets(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    bob = make_user(Role.CUSTOMER, "bob@example.com")
    new_ticket(alice)
    new_ticket(alice)
    new_ticket(bob)

    mine = client.get("/tickets", headers=alice.headers).json()
    assert len(mine) == 2
    assert all(t["customer"]["id"] == alice.id for t in mine)


def test_new_ticket_defaults(client, make_user):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    ticket = client.post("/tickets", json=TICKET, headers=alice.headers).json()
    assert ticket["status"] == "OPEN"
    assert ticket["priority"] == "MEDIUM"
    assert ticket["assigned_agent"] is None


def test_ticket_validation(client, make_user):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    assert client.post("/tickets", json={"title": "Hi", "description": "short"}, headers=alice.headers).status_code == 422
    bad_category = {**TICKET, "category_id": 999}
    assert client.post("/tickets", json=bad_category, headers=alice.headers).status_code == 400


def test_ticket_with_category(client, make_user, category_id):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    ticket = client.post("/tickets", json={**TICKET, "category_id": category_id}, headers=alice.headers).json()
    assert ticket["category"]["name"] == "Billing"


def test_customer_cannot_read_another_customers_ticket(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    bob = make_user(Role.CUSTOMER, "bob@example.com")
    ticket_id = new_ticket(alice)

    assert client.get(f"/tickets/{ticket_id}", headers=bob.headers).status_code == 404
    reply = client.post(f"/tickets/{ticket_id}/messages", json={"message": "hi"}, headers=bob.headers)
    assert reply.status_code == 404


def test_tickets_require_login(client):
    assert client.get("/tickets").status_code == 401
    assert client.post("/tickets", json=TICKET).status_code == 401


def test_only_customers_create_tickets(client, make_user):
    agent = make_user(Role.AGENT, "agent@example.com")
    assert client.post("/tickets", json=TICKET, headers=agent.headers).status_code == 403


def test_customer_cannot_change_status_priority_assign_or_escalate(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    tid = new_ticket(alice)

    assert client.patch(f"/tickets/{tid}", json={"status": "RESOLVED"}, headers=alice.headers).status_code == 403
    assert client.patch(f"/tickets/{tid}", json={"priority": "URGENT"}, headers=alice.headers).status_code == 403
    assign = client.post(f"/tickets/{tid}/assign", json={"agent_id": agent.agent_id}, headers=alice.headers)
    assert assign.status_code == 403
    esc = client.post(f"/tickets/{tid}/escalate", json={"reason": "please hurry"}, headers=alice.headers)
    assert esc.status_code == 403


def test_agent_sees_unassigned_queue_but_only_own_by_default(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    tid = new_ticket(alice)

    assert client.get("/tickets", headers=agent.headers).json() == []
    queue = client.get("/tickets?unassigned=true", headers=agent.headers).json()
    assert [t["id"] for t in queue] == [tid]

    claim = client.post(f"/tickets/{tid}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers)
    assert claim.status_code == 200
    assert [t["id"] for t in client.get("/tickets", headers=agent.headers).json()] == [tid]
    assert client.get("/tickets?unassigned=true", headers=agent.headers).json() == []


def test_agent_must_claim_before_replying_or_changing_status(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    tid = new_ticket(alice)

    assert client.post(f"/tickets/{tid}/messages", json={"message": "on it"}, headers=agent.headers).status_code == 403
    assert client.patch(f"/tickets/{tid}", json={"status": "IN_PROGRESS"}, headers=agent.headers).status_code == 403


def test_agent_cannot_touch_ticket_assigned_to_another_agent(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent1 = make_user(Role.AGENT, "a1@example.com")
    agent2 = make_user(Role.AGENT, "a2@example.com")
    tid = new_ticket(alice)
    client.post(f"/tickets/{tid}/assign", json={"agent_id": agent1.agent_id}, headers=agent1.headers)

    assert client.get(f"/tickets/{tid}", headers=agent2.headers).status_code == 404
    steal = client.post(f"/tickets/{tid}/assign", json={"agent_id": agent2.agent_id}, headers=agent2.headers)
    assert steal.status_code == 404


def test_agent_can_reassign_own_ticket_and_admin_can_assign_anything(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    admin = make_user(Role.ADMIN, "admin@example.com")
    agent1 = make_user(Role.AGENT, "a1@example.com")
    agent2 = make_user(Role.AGENT, "a2@example.com")
    tid = new_ticket(alice)

    r = client.post(f"/tickets/{tid}/assign", json={"agent_id": agent1.agent_id}, headers=admin.headers)
    assert r.json()["assigned_agent"]["id"] == agent1.agent_id
    r = client.post(f"/tickets/{tid}/assign", json={"agent_id": agent2.agent_id}, headers=agent1.headers)
    assert r.status_code == 200 and r.json()["assigned_agent"]["id"] == agent2.agent_id
    # agent1 no longer owns it
    assert client.get(f"/tickets/{tid}", headers=agent1.headers).status_code == 404
    assert client.post(f"/tickets/{tid}/assign", json={"agent_id": 999}, headers=admin.headers).status_code == 404


def test_conversation_and_automatic_status_changes(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    tid = new_ticket(alice)
    client.post(f"/tickets/{tid}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers)

    # Agent's first reply moves OPEN -> IN_PROGRESS
    client.post(f"/tickets/{tid}/messages", json={"message": "Looking into it"}, headers=agent.headers)
    assert client.get(f"/tickets/{tid}", headers=alice.headers).json()["status"] == "IN_PROGRESS"

    # Agent waits for customer; customer reply moves it back to IN_PROGRESS
    client.patch(f"/tickets/{tid}", json={"status": "WAITING_FOR_CUSTOMER"}, headers=agent.headers)
    client.post(f"/tickets/{tid}/messages", json={"message": "Here is my order id"}, headers=alice.headers)
    detail = client.get(f"/tickets/{tid}", headers=alice.headers).json()
    assert detail["status"] == "IN_PROGRESS"
    assert [m["message"] for m in detail["messages"]] == ["Looking into it", "Here is my order id"]
    assert detail["messages"][0]["sender"]["role"] == "AGENT"


def test_resolve_close_and_reopen_rules(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    tid = new_ticket(alice)
    client.post(f"/tickets/{tid}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers)

    # OPEN cannot jump straight to CLOSED
    assert client.patch(f"/tickets/{tid}", json={"status": "CLOSED"}, headers=agent.headers).status_code == 409
    assert client.patch(f"/tickets/{tid}", json={"status": "RESOLVED"}, headers=agent.headers).status_code == 200
    assert client.patch(f"/tickets/{tid}", json={"status": "CLOSED"}, headers=agent.headers).status_code == 200
    # CLOSED is final: no messages, no status changes, no reassignment
    assert client.post(f"/tickets/{tid}/messages", json={"message": "hello?"}, headers=alice.headers).status_code == 409
    assert client.patch(f"/tickets/{tid}", json={"status": "IN_PROGRESS"}, headers=agent.headers).status_code == 409
    assign = client.post(f"/tickets/{tid}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers)
    assert assign.status_code == 409


def test_priority_change_and_empty_update_rejected(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    tid = new_ticket(alice)
    client.post(f"/tickets/{tid}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers)

    r = client.patch(f"/tickets/{tid}", json={"priority": "URGENT"}, headers=agent.headers)
    assert r.status_code == 200 and r.json()["priority"] == "URGENT"
    assert client.patch(f"/tickets/{tid}", json={}, headers=agent.headers).status_code == 422
    assert client.patch(f"/tickets/{tid}", json={"priority": "SUPER"}, headers=agent.headers).status_code == 422


def test_escalation(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    tid = new_ticket(alice)
    client.post(f"/tickets/{tid}/assign", json={"agent_id": agent.agent_id}, headers=agent.headers)

    assert client.post(f"/tickets/{tid}/escalate", json={"reason": "no"}, headers=agent.headers).status_code == 422
    r = client.post(f"/tickets/{tid}/escalate", json={"reason": "Needs a manager decision"}, headers=agent.headers)
    assert r.status_code == 200 and r.json()["status"] == "ESCALATED"
    detail = client.get(f"/tickets/{tid}", headers=agent.headers).json()
    assert detail["messages"][-1]["message"].startswith("[Escalated]")
    # An escalated ticket can still be resolved
    assert client.patch(f"/tickets/{tid}", json={"status": "RESOLVED"}, headers=agent.headers).status_code == 200


def test_ticket_not_found(client, make_user):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    assert client.get("/tickets/12345", headers=alice.headers).status_code == 404


def test_list_filters(client, make_user, new_ticket):
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    admin = make_user(Role.ADMIN, "admin@example.com")
    agent = make_user(Role.AGENT, "agent@example.com")
    t1 = new_ticket(alice)
    new_ticket(alice)
    client.post(f"/tickets/{t1}/assign", json={"agent_id": agent.agent_id}, headers=admin.headers)
    client.patch(f"/tickets/{t1}", json={"status": "RESOLVED", "priority": "HIGH"}, headers=admin.headers)

    assert len(client.get("/tickets", headers=admin.headers).json()) == 2
    assert [t["id"] for t in client.get("/tickets?status=RESOLVED", headers=admin.headers).json()] == [t1]
    assert [t["id"] for t in client.get("/tickets?priority=HIGH", headers=admin.headers).json()] == [t1]
    assert len(client.get("/tickets?unassigned=true", headers=admin.headers).json()) == 1
    assert client.get("/tickets?status=BOGUS", headers=admin.headers).status_code == 422
