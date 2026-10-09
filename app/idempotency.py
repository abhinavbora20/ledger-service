import hashlib
import json
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.ledger import LedgerError
from app.models import IdempotencyKey


class IdempotencyKeyReused(LedgerError):
    """The same key was already used for a different request."""


def fingerprint(operation: str, **fields) -> str:
    """A stable hash of what the request asks for (same request -> same hash)."""
    canonical = json.dumps(
        {"operation": operation, **fields}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def run_idempotent(
    session: Session,
    user_id: int,
    key: str | None,
    request_hash: str,
    operation: Callable[[], dict],
) -> tuple[dict, bool]:
    """Run `operation` at most once per (user, key).

    Returns (response_body, replayed). The caller commits: the key row and the
    operation's writes live in the same database transaction, so they succeed
    or fail together.
    """
    if key is None:
        return operation(), False

    # If another transaction holds an uncommitted row with this (user, key),
    # this statement waits for it to commit or roll back.
    inserted_id = session.scalar(
        pg_insert(IdempotencyKey)
        .values(user_id=user_id, key=key, request_hash=request_hash)
        .on_conflict_do_nothing(index_elements=["user_id", "key"])
        .returning(IdempotencyKey.id)
    )

    if inserted_id is None:  # the key already exists and is committed
        existing = session.scalar(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id, IdempotencyKey.key == key
            )
        )
        if existing.request_hash != request_hash:
            raise IdempotencyKeyReused(
                "this idempotency key was already used for a different request"
            )
        return existing.response_body, True

    body = operation()
    session.execute(
        update(IdempotencyKey)
        .where(IdempotencyKey.id == inserted_id)
        .values(response_body=body)
    )
    return body, False
