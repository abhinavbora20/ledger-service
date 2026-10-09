from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.auth_routes import router as auth_router
from app.ledger import (
    AccountNotFound,
    CurrencyMismatch,
    InsufficientFunds,
    InvalidAmount,
    LedgerError,
    SameAccount,
)
from app.routes import router
from app.users import (
    AuthError,
    EmailAlreadyRegistered,
    InvalidCredentials,
    NotAuthenticated,
)

app = FastAPI(title="Ledger Service")
app.include_router(auth_router)
app.include_router(router)

# business error -> (HTTP status, machine-readable code)
ERROR_RESPONSES = {
    AccountNotFound: (404, "account_not_found"),
    InsufficientFunds: (409, "insufficient_funds"),
    InvalidAmount: (422, "invalid_amount"),
    SameAccount: (422, "same_account"),
    CurrencyMismatch: (422, "currency_mismatch"),
}

AUTH_ERROR_RESPONSES = {
    EmailAlreadyRegistered: (409, "email_already_registered"),
    InvalidCredentials: (401, "invalid_credentials"),
    NotAuthenticated: (401, "not_authenticated"),
}


@app.exception_handler(LedgerError)
async def ledger_error_handler(request: Request, exc: LedgerError):
    status_code, code = ERROR_RESPONSES.get(type(exc), (400, "ledger_error"))
    return JSONResponse(status_code=status_code, content={"code": code, "detail": str(exc)})


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    status_code, code = AUTH_ERROR_RESPONSES.get(type(exc), (401, "auth_error"))
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "detail": str(exc)},
        headers=headers,
    )


@app.get("/health")
def health():
    return {"status": "ok"}
