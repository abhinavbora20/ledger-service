from fastapi import APIRouter, Depends, Header, Response
from sqlalchemy.orm import Session

from app.deps import get_current_user, get_session
from app.idempotency import fingerprint, run_idempotent
from app.ledger import AccountNotFound, deposit, get_balance, transfer
from app.models import Account, User
from app.schemas import (
    AccountCreate,
    AccountOut,
    DepositIn,
    TransactionOut,
    TransferIn,
)

router = APIRouter()


def get_account_for_user(session: Session, account_id: int, user: User) -> Account:
    """Load an account the given user may act on."""
    account = session.get(Account, account_id)
    # 404, not 403: a 403 would confirm that the account exists.
    if account is None or account.user_id != user.id:
        raise AccountNotFound("account does not exist")
    return account


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(
    body: AccountCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    account = Account(name=body.name, currency=body.currency, user_id=current_user.id)
    session.add(account)
    session.flush()
    result = AccountOut(
        id=account.id, name=account.name, currency=account.currency, balance=0
    )
    session.commit()
    return result


@router.get("/accounts/{account_id}", response_model=AccountOut)
def read_account(
    account_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    account = get_account_for_user(session, account_id, current_user)
    return AccountOut(
        id=account.id,
        name=account.name,
        currency=account.currency,
        balance=get_balance(session, account.id),
    )


@router.post(
    "/accounts/{account_id}/deposits", response_model=TransactionOut, status_code=201
)
def deposit_money(
    account_id: int,
    body: DepositIn,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=255),
):
    def work() -> dict:
        get_account_for_user(session, account_id, current_user)
        transaction = deposit(session, account_id, body.amount)
        return {"id": transaction.id, "description": transaction.description}

    result, replayed = run_idempotent(
        session,
        current_user.id,
        idempotency_key,
        fingerprint("deposit", account_id=account_id, amount=body.amount),
        work,
    )
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    session.commit()
    return result


@router.post("/transfers", response_model=TransactionOut, status_code=201)
def create_transfer(
    body: TransferIn,
    response: Response,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, min_length=1, max_length=255),
):
    def work() -> dict:
        # The money can only leave an account the caller owns.
        get_account_for_user(session, body.from_account_id, current_user)
        transaction = transfer(
            session,
            body.from_account_id,
            body.to_account_id,
            body.amount,
            body.description,
        )
        return {"id": transaction.id, "description": transaction.description}

    result, replayed = run_idempotent(
        session,
        current_user.id,
        idempotency_key,
        fingerprint(
            "transfer",
            from_account_id=body.from_account_id,
            to_account_id=body.to_account_id,
            amount=body.amount,
            description=body.description,
        ),
        work,
    )
    if replayed:
        response.headers["Idempotent-Replayed"] = "true"
    session.commit()
    return result
