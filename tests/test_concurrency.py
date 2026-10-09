import threading
import time

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

import app.ledger as ledger
from app.ledger import get_balance, transfer
from app.models import Account


@pytest.fixture
def committed_accounts(engine):
    """Real, committed data: concurrent tests need separate connections."""
    with Session(engine) as s:
        external = Account(name="External", currency="INR", allow_negative=True)
        alice = Account(name="Alice", currency="INR")
        bob = Account(name="Bob", currency="INR")
        s.add_all([external, alice, bob])
        s.flush()
        ids = {"external": external.id, "alice": alice.id, "bob": bob.id}
        transfer(s, ids["external"], ids["alice"], 1000, "deposit")
        transfer(s, ids["external"], ids["bob"], 1000, "deposit")
        s.commit()
    yield ids
    with engine.begin() as conn:
        conn.execute(
            text("TRUNCATE ledger_entries, transactions, accounts RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def slow_balance_check(monkeypatch):
    """Widen the gap between 'check balance' and 'write entries'."""
    original = ledger.get_balance

    def slow(session, account_id):
        balance = original(session, account_id)
        time.sleep(0.5)
        return balance

    monkeypatch.setattr(ledger, "get_balance", slow)


def run_in_threads(engine, jobs):
    """Run each (from_id, to_id, amount) job in its own thread, session and connection."""
    results = []

    def worker(from_id, to_id, amount):
        with Session(engine) as s:
            try:
                transfer(s, from_id, to_id, amount, "concurrent")
                s.commit()
                results.append("ok")
            except Exception as exc:
                s.rollback()
                results.append(type(getattr(exc, "orig", exc)).__name__)

    threads = [threading.Thread(target=worker, args=job) for job in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    return results


def test_concurrent_withdrawals_cannot_overdraw(engine, committed_accounts, slow_balance_check):
    alice = committed_accounts["alice"]
    bob = committed_accounts["bob"]

    # Alice has 1000. Two requests each try to move 800 at the same moment.
    results = run_in_threads(engine, [(alice, bob, 800), (alice, bob, 800)])

    with Session(engine) as s:
        balance = get_balance(s, alice)
    assert balance >= 0, f"Alice was overdrawn: balance={balance}, results={results}"
    assert sorted(results) == ["InsufficientFunds", "ok"]
    assert balance == 200


@pytest.fixture
def slow_lock(monkeypatch):
    """Pause after taking each lock, so opposite transfers would interleave."""
    original = ledger.lock_account

    def slow(session, account_id):
        account = original(session, account_id)
        time.sleep(0.5)
        return account

    monkeypatch.setattr(ledger, "lock_account", slow)


def test_opposite_transfers_do_not_deadlock(engine, committed_accounts, slow_lock):
    alice = committed_accounts["alice"]
    bob = committed_accounts["bob"]

    results = run_in_threads(engine, [(alice, bob, 100), (bob, alice, 100)])

    assert results == ["ok", "ok"]
    with Session(engine) as s:
        assert get_balance(s, alice) == 1000
        assert get_balance(s, bob) == 1000
