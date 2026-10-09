from collections.abc import Iterator

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db import engine
from app.models import User
from app.security import InvalidToken, decode_access_token
from app.users import NotAuthenticated

bearer_scheme = HTTPBearer(auto_error=False)


def get_session() -> Iterator[Session]:
    """One database session per request, always closed afterwards.

    Closing without a commit discards any uncommitted work, so a request
    that fails halfway leaves nothing behind.
    """
    with Session(engine) as session:
        yield session


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise NotAuthenticated("missing bearer token")
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidToken:
        raise NotAuthenticated("invalid or expired token") from None
    user = session.get(User, user_id)
    if user is None:
        raise NotAuthenticated("invalid or expired token")
    return user
