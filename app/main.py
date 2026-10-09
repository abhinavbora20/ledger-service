from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.ledger import (
    AccountNotFound,
    CurrencyMismatch,
    InsufficientFunds,
    InvalidAmount,
    LedgerError,
    SameAccount,
)
from app.routes import router

app = FastAPI(title="Ledger Service")
app.include_router(router)

# business error -> (HTTP status, machine-readable code)
ERROR_RESPONSES = {
    AccountNotFound: (404, "account_not_found"),
    InsufficientFunds: (409, "insufficient_funds"),
    InvalidAmount: (422, "invalid_amount"),
    SameAccount: (422, "same_account"),
    CurrencyMismatch: (422, "currency_mismatch"),
}


@app.exception_handler(LedgerError)
async def ledger_error_handler(request: Request, exc: LedgerError):
    status_code, code = ERROR_RESPONSES.get(type(exc), (400, "ledger_error"))
    return JSONResponse(status_code=status_code, content={"code": code, "detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok"}
