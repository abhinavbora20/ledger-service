import pytest


def with_key(headers, key):
    merged = dict(headers or {})
    if key is not None:
        merged["Idempotency-Key"] = key
    return merged


def create_account(client, headers=None, name="Main"):
    response = client.post(
        "/accounts", json={"name": name, "currency": "INR"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def deposit(client, account_id, amount, headers=None, key=None):
    return client.post(
        f"/accounts/{account_id}/deposits",
        json={"amount": amount},
        headers=with_key(headers, key),
    )


def transfer(client, from_id, to_id, amount, key=None, headers=None):
    return client.post(
        "/transfers",
        json={
            "from_account_id": from_id,
            "to_account_id": to_id,
            "amount": amount,
            "description": "idempotency test",
        },
        headers=with_key(headers, key),
    )


def balance(client, account_id, headers=None):
    return client.get(f"/accounts/{account_id}", headers=headers).json()["balance"]


@pytest.fixture
def accounts(client):
    source = create_account(client, name="Source")
    target = create_account(client, name="Target")
    assert deposit(client, source["id"], 1000).status_code == 201
    return source, target


def test_same_key_twice_moves_money_once(client, accounts):
    source, target = accounts
    first = transfer(client, source["id"], target["id"], 300, key="key-1")
    second = transfer(client, source["id"], target["id"], 300, key="key-1")

    assert first.status_code == second.status_code == 201
    assert second.json() == first.json()
    assert "idempotent-replayed" not in first.headers
    assert second.headers["idempotent-replayed"] == "true"
    assert balance(client, source["id"]) == 700
    assert balance(client, target["id"]) == 300


def test_same_key_with_a_different_request_is_rejected(client, accounts):
    source, target = accounts
    transfer(client, source["id"], target["id"], 300, key="key-1")

    second = transfer(client, source["id"], target["id"], 400, key="key-1")

    assert second.status_code == 422
    assert second.json()["code"] == "idempotency_key_reused"
    assert balance(client, source["id"]) == 700


def test_different_keys_are_independent_requests(client, accounts):
    source, target = accounts
    transfer(client, source["id"], target["id"], 300, key="key-1")
    transfer(client, source["id"], target["id"], 300, key="key-2")
    assert balance(client, source["id"]) == 400
    assert balance(client, target["id"]) == 600


def test_without_a_key_nothing_is_deduplicated(client, accounts):
    source, target = accounts
    transfer(client, source["id"], target["id"], 300)
    transfer(client, source["id"], target["id"], 300)
    assert balance(client, source["id"]) == 400


def test_keys_are_scoped_per_user(client, register_and_login):
    alice_account = create_account(client, name="Alice main")
    deposit(client, alice_account["id"], 1000)
    bob = register_and_login("bob@example.com")
    bob_account = create_account(client, headers=bob, name="Bob main")
    deposit(client, bob_account["id"], 1000, headers=bob)

    a = transfer(client, alice_account["id"], bob_account["id"], 100, key="shared-key")
    b = transfer(
        client, bob_account["id"], alice_account["id"], 200, key="shared-key", headers=bob
    )

    assert a.status_code == b.status_code == 201
    assert "idempotent-replayed" not in b.headers
    assert balance(client, alice_account["id"]) == 1100
    assert balance(client, bob_account["id"], headers=bob) == 900


def test_failed_requests_are_not_recorded_so_a_retry_can_succeed(client, accounts):
    source, target = accounts
    failed = transfer(client, source["id"], target["id"], 5000, key="retry-me")
    assert failed.status_code == 409

    deposit(client, source["id"], 5000)
    retried = transfer(client, source["id"], target["id"], 5000, key="retry-me")

    assert retried.status_code == 201
    assert balance(client, source["id"]) == 1000


def test_deposit_with_the_same_key_credits_once(client):
    account = create_account(client)
    first = deposit(client, account["id"], 500, key="dep-1")
    second = deposit(client, account["id"], 500, key="dep-1")

    assert second.json() == first.json()
    assert second.headers["idempotent-replayed"] == "true"
    assert balance(client, account["id"]) == 500


def test_overlong_key_is_rejected(client, accounts):
    source, target = accounts
    response = transfer(client, source["id"], target["id"], 100, key="x" * 256)
    assert response.status_code == 422
    assert balance(client, source["id"]) == 1000
