import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg:///ledger_test"
)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Tokens in tests are signed with this throwaway secret (set before any app code runs).
os.environ.setdefault("JWT_SECRET", "test-only-secret-never-use-in-production-0123456789")


def run_alembic(*args):
    env = {**os.environ, "DATABASE_URL": TEST_DATABASE_URL}
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        check=True,
    )


@pytest.fixture(scope="session")
def engine():
    # Safety guard: the next step deletes every table, so refuse to run
    # against anything that isn't clearly a test database.
    db_name = make_url(TEST_DATABASE_URL).database
    assert db_name and "test" in db_name, f"Refusing to run on database {db_name!r}"

    run_alembic("downgrade", "base")
    run_alembic("upgrade", "head")
    eng = create_engine(TEST_DATABASE_URL)
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    db_session = Session(bind=connection, join_transaction_mode="create_savepoint")
    yield db_session
    db_session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def anon_client(session):
    """A test client whose requests use the rollback-protected test session."""
    from fastapi.testclient import TestClient

    from app.deps import get_session
    from app.main import app

    def override_get_session():
        try:
            yield session
        finally:
            # Mimic production, where closing the session discards uncommitted work.
            session.rollback()

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def register_and_login(anon_client):
    """Returns a function that registers a user and returns their auth headers."""

    def _register_and_login(email, password="a-long-password-1"):
        response = anon_client.post(
            "/auth/register", json={"email": email, "password": password}
        )
        assert response.status_code == 201, response.text
        response = anon_client.post(
            "/auth/login", json={"email": email, "password": password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    return _register_and_login


@pytest.fixture
def client(anon_client, register_and_login):
    """A test client already logged in as alice@example.com."""
    anon_client.headers.update(register_and_login("alice@example.com"))
    return anon_client
