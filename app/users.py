from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password, verify_password


class AuthError(Exception):
    """Base class for authentication problems."""


class EmailAlreadyRegistered(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class NotAuthenticated(AuthError):
    pass


# Compared against when the email is unknown, so "unknown email" and "wrong
# password" take about the same time. Otherwise response time would reveal
# which emails are registered.
_DUMMY_HASH = hash_password("dummy-password-used-only-for-timing")


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(session: Session, email: str, password: str) -> User:
    user = User(email=normalize_email(email), password_hash=hash_password(password))
    try:
        # A savepoint: if the unique constraint fires, only this insert is undone
        # and the caller's session stays usable.
        with session.begin_nested():
            session.add(user)
            session.flush()
    except IntegrityError:
        raise EmailAlreadyRegistered("email is already registered") from None
    return user


def authenticate(session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        raise InvalidCredentials("invalid email or password")
    if not verify_password(password, user.password_hash):
        raise InvalidCredentials("invalid email or password")
    return user
