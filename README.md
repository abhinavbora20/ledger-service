# Ledger Service

A double-entry ledger and transaction API built with FastAPI and PostgreSQL.

**Status:** early development. Only the `/health` endpoint exists so far.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then check it works:

```bash
curl -i http://127.0.0.1:8000/health
```

## Run the tests

```bash
python -m pytest -v
```

## Roadmap

- [x] Health endpoint and tests
- [ ] PostgreSQL schema (accounts, transactions, ledger entries)
- [ ] Transfers with database transactions and locking
- [ ] JWT authentication and idempotency keys
- [ ] Docker, CI, deployment, benchmarks
