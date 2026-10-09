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
    return int(total or 0)


def lock_account(session: Session, account_id: int) -> Account | None:
    """Fetch an account row and lock it (SELECT ... FOR UPDATE).

    Any other transaction that tries to lock the same row waits until
    this transaction commits or rolls back.
    """
    return session.get(Account, account_id, with_for_update=True)


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

    # Lock both rows in a fixed order (lowest id first) so two opposite
    # transfers can never wait on each other in a circle (deadlock).
    first_id, second_id = sorted((from_account_id, to_account_id))
    locked = {
        first_id: lock_account(session, first_id),
        second_id: lock_account(session, second_id),
    }
    source = locked[from_account_id]
    destination = locked[to_account_id]
    if source is None or destination is None:
        raise AccountNotFound("source or destination account does not exist")
    if source.currency != destination.currency:
        raise CurrencyMismatch("accounts have different currencies")

    # Safe: both rows stay locked until the caller commits or rolls back, so no
    # other transfer can change these balances between this check and the writes.
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


def get_external_account(session: Session, currency: str) -> Account:
    """The system account that deposits come from, one per currency."""
    name = f"External {currency}"
    account = session.scalar(
        select(Account).where(Account.name == name, Account.allow_negative.is_(True))
    )
    if account is None:
        account = Account(name=name, currency=currency, allow_negative=True)
        session.add(account)
        session.flush()
    return account


def deposit(session: Session, account_id: int, amount: int) -> Transaction:
    """Credit an account with money coming from outside the system."""
    if amount <= 0:
        raise InvalidAmount("amount must be a positive integer")
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFound("account does not exist")
    external = get_external_account(session, account.currency)
    return transfer(session, external.id, account.id, amount, "deposit")
