import os

from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql+psycopg:///ledger_dev")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
