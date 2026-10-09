from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, get_jwt_secret

_hasher = PasswordHasher()


class InvalidToken(Exception):
    """The token is malformed, tampered with, expired, or signed with another key."""


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_MINUTES)),
    }
    return jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id inside a valid token, or raise InvalidToken."""
    try:
        payload = jwt.decode(
            token,
            get_jwt_secret(),
            algorithms=[JWT_ALGORITHM],  # never accept the algorithm the token asks for
            options={"require": ["exp", "sub"]},
        )
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise InvalidToken("invalid or expired token") from exc
