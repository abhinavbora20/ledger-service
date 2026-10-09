import pytest
from sqlalchemy import func, select

from app.ledger import (
    AccountNotFound,
    CurrencyMismatch,
    InsufficientFunds,
    InvalidAmount,
    SameAccount,
    get_balance,
    transfer,
)
from app.models import Account, LedgerEntry, Transaction


def make_account(session, name, currency="INR", allow_negative=False):
    account = Account(name=name, currency=currency, allow_negative=allow_negative)
    session.add(account)
    session.flush()
    return account


def count_transactions(session):
    return session.scalar(select(func.count()).select_from(Transaction))


def test_transfer_moves_money(session):
    external = make_account(session, "External", allow_negative=True)
    alice = make_account(session, "Alice")
    bob = make_account(session, "Bob")

    transfer(session, external.id, alice.id, 100000, "deposit")
    transfer(session, alice.id, bob.id, 25000, "Alice pays Bob")

    assert get_balance(session, alice.id) == 75000
    assert get_balance(session, bob.id) == 25000
    assert get_balance(session, external.id) == -100000


def test_every_transaction_sums_to_zero(session):
    external = make_account(session, "External", allow_negative=True)
    alice = make_account(session, "Alice")
    bob = make_account(session, "Bob")
    transfer(session, external.id, alice.id, 100000, "deposit")
    transfer(session, alice.id, bob.id, 25000, "Alice pays Bob")

    unbalanced = session.execute(
        select(LedgerEntry.transaction_id)
        .group_by(LedgerEntry.transaction_id)
        .having(func.sum(LedgerEntry.amount) != 0)
    ).all()
    assert unbalanced == []


def test_overdraft_is_rejected_and_changes_nothing(session):
    external = make_account(session, "External", allow_negative=True)
    alice = make_account(session, "Alice")
    bob = make_account(session, "Bob")
    transfer(session, external.id, alice.id, 1000, "deposit")
    before = count_transactions(session)

    with pytest.raises(InsufficientFunds):
        transfer(session, alice.id, bob.id, 5000, "too much")

    assert count_transactions(session) == before
    assert get_balance(session, alice.id) == 1000
    assert get_balance(session, bob.id) == 0


@pytest.mark.parametrize("bad_amount", [0, -5])
def test_non_positive_amount_is_rejected(session, bad_amount):
    external = make_account(session, "External", allow_negative=True)
    alice = make_account(session, "Alice")
    with pytest.raises(InvalidAmount):
        transfer(session, external.id, alice.id, bad_amount, "bad")


def test_transfer_to_same_account_is_rejected(session):
    alice = make_account(session, "Alice", allow_negative=True)
    with pytest.raises(SameAccount):
        transfer(session, alice.id, alice.id, 100, "self")


def test_unknown_account_is_rejected(session):
    alice = make_account(session, "Alice", allow_negative=True)
    with pytest.raises(AccountNotFound):
        transfer(session, alice.id, 999999999, 100, "nobody")


def test_currency_mismatch_is_rejected(session):
    inr = make_account(session, "Alice", currency="INR", allow_negative=True)
    usd = make_account(session, "Bob", currency="USD")
    with pytest.raises(CurrencyMismatch):
        transfer(session, inr.id, usd.id, 100, "mixed currencies")


def test_get_balance_returns_a_plain_int(session):
    external = make_account(session, "External", allow_negative=True)
    alice = make_account(session, "Alice")
    transfer(session, external.id, alice.id, 500, "deposit")

    balance = get_balance(session, alice.id)

    assert type(balance) is int
    assert balance == 500
