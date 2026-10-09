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
    db_session = Session(bind=connection)
    yield db_session
    db_session.close()
    transaction.rollback()
    connection.close()
