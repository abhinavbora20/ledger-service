def create_account(client, headers=None, name="Main"):
    response = client.post(
        "/accounts", json={"name": name, "currency": "INR"}, headers=headers
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_user_cannot_read_another_users_account(client, register_and_login):
    alice_account = create_account(client)  # `client` is logged in as Alice
    bob = register_and_login("bob@example.com")

    response = client.get(f"/accounts/{alice_account['id']}", headers=bob)

    assert response.status_code == 404
    assert response.json()["code"] == "account_not_found"


def test_user_cannot_deposit_into_another_users_account(client, register_and_login):
    alice_account = create_account(client)
    bob = register_and_login("bob@example.com")

    response = client.post(
        f"/accounts/{alice_account['id']}/deposits", json={"amount": 500}, headers=bob
    )

    assert response.status_code == 404
    assert client.get(f"/accounts/{alice_account['id']}").json()["balance"] == 0


def test_user_cannot_spend_from_another_users_account(client, register_and_login):
    alice_account = create_account(client)
    client.post(f"/accounts/{alice_account['id']}/deposits", json={"amount": 1000})
    bob = register_and_login("bob@example.com")
    bob_account = create_account(client, headers=bob, name="Bob main")

    response = client.post(
        "/transfers",
        json={
            "from_account_id": alice_account["id"],
            "to_account_id": bob_account["id"],
            "amount": 500,
        },
        headers=bob,
    )

    assert response.status_code == 404
    assert client.get(f"/accounts/{alice_account['id']}").json()["balance"] == 1000
    assert client.get(f"/accounts/{bob_account['id']}", headers=bob).json()["balance"] == 0


def test_user_can_send_money_to_another_users_account(client, register_and_login):
    alice_account = create_account(client)
    client.post(f"/accounts/{alice_account['id']}/deposits", json={"amount": 1000})
    bob = register_and_login("bob@example.com")
    bob_account = create_account(client, headers=bob, name="Bob main")

    response = client.post(
        "/transfers",
        json={
            "from_account_id": alice_account["id"],
            "to_account_id": bob_account["id"],
            "amount": 300,
        },
    )

    assert response.status_code == 201
    assert client.get(f"/accounts/{bob_account['id']}", headers=bob).json()["balance"] == 300
