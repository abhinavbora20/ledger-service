from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db import engine


def get_session() -> Iterator[Session]:
    """One database session per request, always closed afterwards.

    Closing without a commit discards any uncommitted work, so a request
    that fails halfway leaves nothing behind.
    """
    with Session(engine) as session:
        yield session
