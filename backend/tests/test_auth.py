import pytest

from app.models import Role
from app.services import user_service


def register(client, email="asha@example.com", password="password123", name="Asha Rao"):
    return client.post(
        "/auth/register", json={"full_name": name, "email": email, "password": password, "business": "acme"}
    )


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_register_creates_customer_without_leaking_password(client):
    response = register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "CUSTOMER"
    assert "password" not in body and "hashed_password" not in body


def test_register_duplicate_email_rejected_case_insensitively(client):
    register(client, email="asha@example.com")
    assert register(client, email="ASHA@example.com").status_code == 409


def test_register_validation(client):
    assert register(client, password="short").status_code == 422
    assert register(client, email="not-an-email").status_code == 422
    assert register(client, name="A").status_code == 422


def test_register_cannot_choose_role(client):
    response = client.post(
        "/auth/register",
        json={"full_name": "Sneaky", "email": "s@example.com", "password": "password123", "role": "ADMIN",
              "business": "acme"},
    )
    assert response.status_code == 201
    assert response.json()["role"] == "CUSTOMER"


def test_login_success_and_me(client):
    register(client)
    response = client.post("/auth/login", data={"username": "asha@example.com", "password": "password123"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "asha@example.com"


def test_login_wrong_password_and_unknown_user_look_identical(client):
    register(client)
    wrong = client.post("/auth/login", data={"username": "asha@example.com", "password": "wrongpass1"})
    unknown = client.post("/auth/login", data={"username": "nobody@example.com", "password": "password123"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_protected_endpoint_needs_valid_token(client):
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_disabled_user_cannot_log_in_or_use_old_token(client, make_user):
    admin = make_user(Role.ADMIN, "admin@example.com")
    customer = make_user(Role.CUSTOMER, "c@example.com")
    r = client.patch(f"/admin/users/{customer.id}", json={"is_active": False}, headers=admin.headers)
    assert r.status_code == 200
    assert client.get("/auth/me", headers=customer.headers).status_code == 401
    login = client.post("/auth/login", data={"username": "c@example.com", "password": "password123"})
    assert login.status_code == 403


# ---------------------------------------------------------------- password reset (reset_password.py)

def login(client, email, password):
    return client.post("/auth/login", data={"username": email, "password": password})


def test_reset_password_replaces_the_old_one(client, make_user, session_factory):
    make_user(Role.ADMIN, "boss@example.com")  # created with the fixture password "password123"
    with session_factory() as db:
        user = user_service.get_user_by_email(db, "boss@example.com")
        user_service.set_password(user, "Brand-New-Pass1")
        db.commit()
        assert user.hashed_password != "Brand-New-Pass1"  # only the bcrypt hash is stored

    assert login(client, "boss@example.com", "Brand-New-Pass1").status_code == 200
    assert login(client, "boss@example.com", "password123").status_code == 401  # the old one is gone


def test_reset_password_keeps_the_same_account(client, make_user, session_factory):
    make_user(Role.AGENT, "ravi@example.com", name="Ravi Kumar")
    with session_factory() as db:
        user = user_service.get_user_by_email(db, "ravi@example.com")
        before = (user.id, user.role, user.business_id, user.full_name)
        user_service.set_password(user, "Another-Pass9")
        db.commit()
        assert (user.id, user.role, user.business_id, user.full_name) == before  # only the password changed


def test_reset_password_refuses_a_short_password(make_user, session_factory):
    make_user(Role.CUSTOMER, "asha@example.com")
    with session_factory() as db:
        user = user_service.get_user_by_email(db, "asha@example.com")
        old_hash = user.hashed_password
        with pytest.raises(ValueError):
            user_service.set_password(user, "short")
        assert user.hashed_password == old_hash  # nothing changed
