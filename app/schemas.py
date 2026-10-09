from typing import Annotated

from pydantic import BaseModel, Field

# Strict: reject "100" (a string) and 100.5 (a float).
# Amounts are integers in minor units (paise, cents).
Amount = Annotated[int, Field(strict=True, gt=0)]


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class AccountOut(BaseModel):
    id: int
    name: str
    currency: str
    balance: int


class DepositIn(BaseModel):
    amount: Amount


class TransferIn(BaseModel):
    from_account_id: int
    to_account_id: int
    amount: Amount
    description: str = Field(default="transfer", min_length=1, max_length=200)


class TransactionOut(BaseModel):
    id: int
    description: str


class RegisterIn(BaseModel):
    email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=10, max_length=128)


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    id: int
    email: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
