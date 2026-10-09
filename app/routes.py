from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_session
from app.ledger import AccountNotFound, deposit, get_balance, transfer
from app.models import Account
from app.schemas import (
    AccountCreate,
    AccountOut,
    DepositIn,
    TransactionOut,
    TransferIn,
)

router = APIRouter()


@router.post("/accounts", response_model=AccountOut, status_code=201)
def create_account(body: AccountCreate, session: Session = Depends(get_session)):
    account = Account(name=body.name, currency=body.currency)
    session.add(account)
    session.flush()
    result = AccountOut(
        id=account.id, name=account.name, currency=account.currency, balance=0
    )
    session.commit()
    return result


@router.get("/accounts/{account_id}", response_model=AccountOut)
def read_account(account_id: int, session: Session = Depends(get_session)):
    account = session.get(Account, account_id)
    if account is None:
        raise AccountNotFound("account does not exist")
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
    account_id: int, body: DepositIn, session: Session = Depends(get_session)
):
    transaction = deposit(session, account_id, body.amount)
    result = TransactionOut(id=transaction.id, description=transaction.description)
    session.commit()
    return result


@router.post("/transfers", response_model=TransactionOut, status_code=201)
def create_transfer(body: TransferIn, session: Session = Depends(get_session)):
    transaction = transfer(
        session,
        body.from_account_id,
        body.to_account_id,
        body.amount,
        body.description,
    )
    result = TransactionOut(id=transaction.id, description=transaction.description)
    session.commit()
    return result
