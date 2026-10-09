import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.models import Account, LedgerEntry, Transaction


def make_account(session, name="Alice"):
    account = Account(name=name, currency="INR")
    session.add(account)
    session.flush()
    return account


def make_transaction(session, description="test transaction"):
    transaction = Transaction(description=description)
    session.add(transaction)
    session.flush()
    return transaction


def test_zero_amount_entry_is_rejected(session):
    account = make_account(session)
    transaction = make_transaction(session)
    session.add(
        LedgerEntry(transaction_id=transaction.id, account_id=account.id, amount=0)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_entry_for_unknown_account_is_rejected(session):
    transaction = make_transaction(session)
    session.add(
        LedgerEntry(transaction_id=transaction.id, account_id=999999999, amount=100)
    )
    with pytest.raises(IntegrityError):
        session.flush()


def test_account_requires_a_currency(session):
    session.add(Account(name="No Currency"))
    with pytest.raises(IntegrityError):
        session.flush()


def test_balance_is_the_sum_of_entries(session):
    alice = make_account(session, "Alice")
    bob = make_account(session, "Bob")
    transaction = make_transaction(session, "Alice pays Bob")
    session.add_all(
        [
            LedgerEntry(transaction_id=transaction.id, account_id=alice.id, amount=-25000),
            LedgerEntry(transaction_id=transaction.id, account_id=bob.id, amount=25000),
        ]
    )
    session.flush()

    def balance(account):
        return session.scalar(
            select(func.sum(LedgerEntry.amount)).where(
                LedgerEntry.account_id == account.id
            )
        )

    assert balance(alice) == -25000
    assert balance(bob) == 25000
    # The double-entry rule: all entries of one transaction sum to zero.
    total = session.scalar(
        select(func.sum(LedgerEntry.amount)).where(
            LedgerEntry.transaction_id == transaction.id
        )
    )
    assert total == 0


def test_each_test_starts_with_an_empty_database(session):
    # If rollback between tests were broken, accounts created by the
    # other tests would show up here.
    assert session.scalar(select(func.count()).select_from(Account)) == 0
