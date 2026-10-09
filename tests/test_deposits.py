import pytest
from sqlalchemy import func, select

from app.ledger import AccountNotFound, InvalidAmount, deposit, get_balance
from app.models import Account


def make_account(session, name="Alice", currency="INR"):
    account = Account(name=name, currency=currency)
    session.add(account)
    session.flush()
    return account


def count_accounts_named(session, name):
    return session.scalar(
        select(func.count()).select_from(Account).where(Account.name == name)
    )


def test_deposit_credits_the_account_and_debits_external(session):
    alice = make_account(session)
    deposit(session, alice.id, 1000)

    external = session.scalar(select(Account).where(Account.name == "External INR"))
    assert get_balance(session, alice.id) == 1000
    assert external.allow_negative is True
    assert get_balance(session, external.id) == -1000


def test_deposits_reuse_one_external_account_per_currency(session):
    a = make_account(session, "A")
    b = make_account(session, "B")
    deposit(session, a.id, 100)
    deposit(session, b.id, 200)
    assert count_accounts_named(session, "External INR") == 1


def test_each_currency_gets_its_own_external_account(session):
    inr = make_account(session, "A", "INR")
    usd = make_account(session, "B", "USD")
    deposit(session, inr.id, 100)
    deposit(session, usd.id, 100)
    names = set(session.scalars(select(Account.name).where(Account.allow_negative.is_(True))))
    assert names == {"External INR", "External USD"}


def test_deposit_to_unknown_account_is_rejected(session):
    with pytest.raises(AccountNotFound):
        deposit(session, 999999999, 100)


@pytest.mark.parametrize("bad_amount", [0, -1])
def test_deposit_rejects_non_positive_amounts_without_side_effects(session, bad_amount):
    alice = make_account(session)
    with pytest.raises(InvalidAmount):
        deposit(session, alice.id, bad_amount)
    assert count_accounts_named(session, "External INR") == 0
