import pytest


def create_account(client, name="Alice", currency="INR"):
    response = client.post("/accounts", json={"name": name, "currency": currency})
    assert response.status_code == 201
    return response.json()


def deposit(client, account_id, amount):
    return client.post(f"/accounts/{account_id}/deposits", json={"amount": amount})


def transfer(client, from_id, to_id, amount, description="test"):
    return client.post(
        "/transfers",
        json={
            "from_account_id": from_id,
            "to_account_id": to_id,
            "amount": amount,
            "description": description,
        },
    )


def balance(client, account_id):
    return client.get(f"/accounts/{account_id}").json()["balance"]


def test_create_account_starts_with_zero_balance(client):
    body = create_account(client)
    assert body["name"] == "Alice"
    assert body["currency"] == "INR"
    assert body["balance"] == 0
    assert isinstance(body["id"], int)


def test_deposit_then_read_balance(client):
    alice = create_account(client)
    response = deposit(client, alice["id"], 100000)
    assert response.status_code == 201
    assert response.json()["description"] == "deposit"
    assert balance(client, alice["id"]) == 100000


def test_transfer_moves_money(client):
    alice = create_account(client, "Alice")
    bob = create_account(client, "Bob")
    deposit(client, alice["id"], 100000)

    response = transfer(client, alice["id"], bob["id"], 25000, "Alice pays Bob")

    assert response.status_code == 201
    assert balance(client, alice["id"]) == 75000
    assert balance(client, bob["id"]) == 25000


def test_insufficient_funds_returns_409_and_changes_nothing(client):
    alice = create_account(client, "Alice")
    bob = create_account(client, "Bob")
    deposit(client, alice["id"], 1000)

    response = transfer(client, alice["id"], bob["id"], 5000)

    assert response.status_code == 409
    assert response.json()["code"] == "insufficient_funds"
    assert balance(client, alice["id"]) == 1000
    assert balance(client, bob["id"]) == 0


def test_unknown_account_returns_404(client):
    response = client.get("/accounts/999999999")
    assert response.status_code == 404
    assert response.json()["code"] == "account_not_found"

    alice = create_account(client)
    deposit(client, alice["id"], 1000)
    response = transfer(client, alice["id"], 999999999, 100)
    assert response.status_code == 404


@pytest.mark.parametrize("bad_amount", [0, -5, "100", 10.5])
def test_invalid_amounts_are_rejected_with_422(client, bad_amount):
    alice = create_account(client)
    response = deposit(client, alice["id"], bad_amount)
    assert response.status_code == 422
    assert balance(client, alice["id"]) == 0


def test_currency_mismatch_returns_422(client):
    inr = create_account(client, "A", "INR")
    usd = create_account(client, "B", "USD")
    deposit(client, inr["id"], 1000)

    response = transfer(client, inr["id"], usd["id"], 100)

    assert response.status_code == 422
    assert response.json()["code"] == "currency_mismatch"


def test_transfer_to_same_account_returns_422(client):
    alice = create_account(client)
    deposit(client, alice["id"], 1000)
    response = transfer(client, alice["id"], alice["id"], 100)
    assert response.status_code == 422
    assert response.json()["code"] == "same_account"


def test_lowercase_currency_is_rejected(client):
    response = client.post("/accounts", json={"name": "A", "currency": "inr"})
    assert response.status_code == 422
