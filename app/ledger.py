from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Account, LedgerEntry, Transaction


class LedgerError(Exception):
    """Base class for business-rule violations."""


class InvalidAmount(LedgerError):
    pass


class SameAccount(LedgerError):
    pass


class AccountNotFound(LedgerError):
    pass


class CurrencyMismatch(LedgerError):
    pass


class InsufficientFunds(LedgerError):
    pass


def get_balance(session: Session, account_id: int) -> int:
    total = session.scalar(
        select(func.sum(LedgerEntry.amount)).where(LedgerEntry.account_id == account_id)
    )
    return total or 0


def transfer(
    session: Session,
    from_account_id: int,
    to_account_id: int,
    amount: int,
    description: str,
) -> Transaction:
    """Move `amount` (in minor units) between two accounts.

    Does NOT commit: the caller owns the database transaction.
    """
    if amount <= 0:
        raise InvalidAmount("amount must be a positive integer")
    if from_account_id == to_account_id:
        raise SameAccount("cannot transfer to the same account")

    source = session.get(Account, from_account_id)
    destination = session.get(Account, to_account_id)
    if source is None or destination is None:
        raise AccountNotFound("source or destination account does not exist")
    if source.currency != destination.currency:
        raise CurrencyMismatch("accounts have different currencies")

    # NAIVE VERSION: check the balance, then write. Not safe under concurrency.
    # We will prove that in 1.4b and fix it.
    if not source.allow_negative and get_balance(session, source.id) < amount:
        raise InsufficientFunds("balance is too low for this transfer")

    transaction = Transaction(description=description)
    session.add(transaction)
    session.flush()  # sends the INSERT so transaction.id exists

    session.add_all(
        [
            LedgerEntry(transaction_id=transaction.id, account_id=source.id, amount=-amount),
            LedgerEntry(transaction_id=transaction.id, account_id=destination.id, amount=amount),
        ]
    )
    session.flush()
    return transaction
