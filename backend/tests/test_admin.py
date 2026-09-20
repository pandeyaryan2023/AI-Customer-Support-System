from app.models import Role


def test_admin_endpoints_forbidden_for_customers_and_agents(client, make_user):
    customer = make_user(Role.CUSTOMER, "c@example.com")
    agent = make_user(Role.AGENT, "a@example.com")
    for headers in (customer.headers, agent.headers):
        assert client.get("/admin/users", headers=headers).status_code == 403
        assert client.get("/admin/stats", headers=headers).status_code == 403
        assert client.post("/admin/categories", json={"name": "Billing"}, headers=headers).status_code == 403
        agent_body = {"full_name": "New Agent", "email": "n@example.com", "password": "password123"}
        assert client.post("/admin/agents", json=agent_body, headers=headers).status_code == 403
    assert client.get("/admin/users").status_code == 401


def test_admin_creates_agent_who_can_log_in(client, make_user):
    admin = make_user(Role.ADMIN, "admin@example.com")
    body = {"full_name": "Ravi Kumar", "email": "ravi@example.com", "password": "password123", "department": "Billing"}
    r = client.post("/admin/agents", json=body, headers=admin.headers)
    assert r.status_code == 201
    assert r.json()["department"] == "Billing" and r.json()["user"]["role"] == "AGENT"

    login = client.post("/auth/login", data={"username": "ravi@example.com", "password": "password123"})
    assert login.status_code == 200 and login.json()["role"] == "AGENT"
    assert len(client.get("/admin/agents", headers=admin.headers).json()) == 1
    assert client.post("/admin/agents", json=body, headers=admin.headers).status_code == 409


def test_admin_lists_users_and_filters_by_role(client, make_user):
    admin = make_user(Role.ADMIN, "admin@example.com")
    make_user(Role.CUSTOMER, "c1@example.com")
    make_user(Role.CUSTOMER, "c2@example.com")
    assert len(client.get("/admin/users", headers=admin.headers).json()) == 3
    customers = client.get("/admin/users?role=CUSTOMER", headers=admin.headers).json()
    assert len(customers) == 2


def test_admin_cannot_disable_self(client, make_user):
    admin = make_user(Role.ADMIN, "admin@example.com")
    r = client.patch(f"/admin/users/{admin.id}", json={"is_active": False}, headers=admin.headers)
    assert r.status_code == 400
    assert client.patch("/admin/users/999", json={"is_active": False}, headers=admin.headers).status_code == 404


def test_category_management_and_customer_sees_only_active(client, make_user):
    admin = make_user(Role.ADMIN, "admin@example.com")
    customer = make_user(Role.CUSTOMER, "c@example.com")

    billing = client.post("/admin/categories", json={"name": "Billing"}, headers=admin.headers)
    assert billing.status_code == 201
    delivery = client.post("/admin/categories", json={"name": "Delivery"}, headers=admin.headers).json()
    assert client.post("/admin/categories", json={"name": "billing"}, headers=admin.headers).status_code == 409

    client.patch(f"/admin/categories/{delivery['id']}", json={"is_active": False}, headers=admin.headers)
    visible = client.get("/categories", headers=customer.headers).json()
    assert [c["name"] for c in visible] == ["Billing"]
    assert len(client.get("/admin/categories", headers=admin.headers).json()) == 2
    assert client.patch("/admin/categories/999", json={"name": "X Y"}, headers=admin.headers).status_code == 404

    # A deactivated category can no longer be chosen for a new complaint
    ticket = {"title": "Late parcel", "description": "It has not arrived yet", "category_id": delivery["id"]}
    assert client.post("/tickets", json=ticket, headers=customer.headers).status_code == 400


def test_stats(client, make_user, new_ticket):
    admin = make_user(Role.ADMIN, "admin@example.com")
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    new_ticket(alice)
    new_ticket(alice)
    stats = client.get("/admin/stats", headers=admin.headers).json()
    assert stats["total_tickets"] == 2
    assert stats["unassigned_tickets"] == 2
    assert stats["tickets_by_status"]["OPEN"] == 2 and stats["tickets_by_status"]["CLOSED"] == 0
    assert stats["users_by_role"] == {"CUSTOMER": 1, "AGENT": 0, "ADMIN": 1}


def test_staff_can_list_active_agents_without_emails(client, make_user):
    admin = make_user(Role.ADMIN, "admin@example.com")
    agent = make_user(Role.AGENT, "a1@example.com", name="Active Agent")
    gone = make_user(Role.AGENT, "a2@example.com", name="Gone Agent")
    customer = make_user(Role.CUSTOMER, "c@example.com")
    client.patch(f"/admin/users/{gone.id}", json={"is_active": False}, headers=admin.headers)

    for headers in (agent.headers, admin.headers):
        agents = client.get("/agents", headers=headers).json()
        assert [a["user"]["full_name"] for a in agents] == ["Active Agent"]
        assert "email" not in agents[0]["user"]
    assert client.get("/agents", headers=customer.headers).status_code == 403
    assert client.get("/agents").status_code == 401


def test_admin_sees_any_ticket(client, make_user, new_ticket):
    admin = make_user(Role.ADMIN, "admin@example.com")
    alice = make_user(Role.CUSTOMER, "alice@example.com")
    tid = new_ticket(alice)
    assert client.get(f"/tickets/{tid}", headers=admin.headers).status_code == 200
