import threading
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.idempotency import fingerprint, run_idempotent
from app.ledger import deposit, get_balance, transfer
from app.models import Account, User


@pytest.fixture
def world(engine):
    """Committed data: concurrent tests need real commits on separate connections."""
    with Session(engine) as s:
        user = User(email="owner@example.com", password_hash="not-used-in-this-test")
        s.add(user)
        s.flush()
        source = Account(name="Source", currency="INR", user_id=user.id)
        target = Account(name="Target", currency="INR", user_id=user.id)
        s.add_all([source, target])
        s.flush()
        ids = {"user": user.id, "source": source.id, "target": target.id}
        deposit(s, ids["source"], 1000)
        s.commit()
    yield ids
    with engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE idempotency_keys, ledger_entries, transactions, "
                "accounts, users RESTART IDENTITY CASCADE"
            )
        )


def test_two_simultaneous_identical_requests_run_the_operation_once(engine, world):
    executions = []
    outcomes = []

    def worker():
        with Session(engine) as s:

            def operation():
                executions.append(1)
                time.sleep(0.5)  # keep this transaction open so the other overlaps
                t = transfer(s, world["source"], world["target"], 300, "idempotent")
                return {"id": t.id, "description": t.description}

            body, replayed = run_idempotent(
                s,
                world["user"],
                "same-key",
                fingerprint("transfer", amount=300),
                operation,
            )
            s.commit()
            outcomes.append((body, replayed))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert len(outcomes) == 2, f"a worker failed: outcomes={outcomes}"
    assert len(executions) == 1
    assert sorted(replayed for _, replayed in outcomes) == [False, True]
    assert outcomes[0][0] == outcomes[1][0]
    with Session(engine) as s:
        assert get_balance(s, world["source"]) == 700
        assert get_balance(s, world["target"]) == 300
