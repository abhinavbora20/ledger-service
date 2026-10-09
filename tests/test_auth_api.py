from datetime import timedelta

import pytest

from app.security import create_access_token

PASSWORD = "a-long-password-1"


def register(client, email="bob@example.com", password=PASSWORD):
    return client.post("/auth/register", json={"email": email, "password": password})


def login(client, email="bob@example.com", password=PASSWORD):
    return client.post("/auth/login", json={"email": email, "password": password})


def test_register_normalizes_email_and_leaks_no_password_data(anon_client):
    response = register(anon_client, "Bob@Example.com")
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "bob@example.com"
    assert set(body) == {"id", "email"}


def test_duplicate_email_is_rejected_case_insensitively(anon_client):
    assert register(anon_client, "bob@example.com").status_code == 201
    response = register(anon_client, "BOB@example.com")
    assert response.status_code == 409
    assert response.json()["code"] == "email_already_registered"


def test_short_password_is_rejected(anon_client):
    assert register(anon_client, password="short").status_code == 422


def test_login_returns_a_token_that_works(anon_client):
    register(anon_client)
    response = login(anon_client)
    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    created = anon_client.post(
        "/accounts", json={"name": "Main", "currency": "INR"}, headers=headers
    )
    assert created.status_code == 201


def test_wrong_password_and_unknown_email_look_identical(anon_client):
    register(anon_client)
    wrong_password = login(anon_client, password="not-the-password-1")
    unknown_email = login(anon_client, email="nobody@example.com")
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


@pytest.mark.parametrize(
    "method, path, body",
    [
        ("GET", "/accounts/1", None),
        ("POST", "/accounts", {"name": "A", "currency": "INR"}),
        ("POST", "/accounts/1/deposits", {"amount": 100}),
        ("POST", "/transfers", {"from_account_id": 1, "to_account_id": 2, "amount": 100}),
    ],
)
def test_protected_endpoints_require_a_token(anon_client, method, path, body):
    response = anon_client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_bad_tokens_are_rejected(anon_client):
    expired = create_access_token(1, expires_delta=timedelta(seconds=-1))
    for token in [expired, "not.a.token", "garbage"]:
        response = anon_client.get(
            "/accounts/1", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401


def test_validly_signed_token_for_a_missing_user_is_rejected(anon_client):
    token = create_access_token(999999999)
    response = anon_client.get(
        "/accounts/1", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401
