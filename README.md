# Ledger Service

[![CI](https://github.com/abhinavbora20/ledger-service/actions/workflows/ci.yml/badge.svg)](https://github.com/abhinavbora20/ledger-service/actions/workflows/ci.yml)

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
- [x] PostgreSQL schema (accounts, transactions, ledger entries)
- [x] Transfers with database transactions and locking
- [x] JWT authentication and idempotency keys
- [ ] Docker, CI, deployment, benchmarks

## Database and migrations

Requires PostgreSQL 16 running locally.

```bash
createdb ledger_dev
createdb ledger_test
alembic upgrade head
```

- `alembic upgrade head` applies all migrations to the database in `DATABASE_URL` (default: local `ledger_dev`).
- `alembic downgrade base` removes everything; `alembic current` shows the applied revision.
- Tests use the separate `ledger_test` database. The test run rebuilds its schema from the migrations, so every test run also checks that the migrations work.

## API

Start the server and open the interactive docs at http://127.0.0.1:8000/docs.

| Method | Path | Purpose |
|---|---|---|
| POST | `/accounts` | Create an account (`name`, 3-letter uppercase `currency`) |
| GET | `/accounts/{id}` | Read an account and its balance |
| POST | `/accounts/{id}/deposits` | Deposit money from outside the system |
| POST | `/transfers` | Move money between two accounts of the same currency |
| GET | `/health` | Liveness check |

Amounts are **integers in minor units** (for example paise): `100000` means 1000.00. Strings and decimals are rejected.

Errors return a JSON body with a machine-readable `code`:

| Status | Code | Meaning |
|---|---|---|
| 404 | `account_not_found` | An account does not exist |
| 409 | `insufficient_funds` | The source balance is too low |
| 422 | `invalid_amount`, `same_account`, `currency_mismatch` | The request cannot be processed |

## Design notes

- **Double-entry:** every transaction has entries that sum to zero; balances are computed from entries, never stored.
- **Concurrency:** transfers lock both account rows (`SELECT ... FOR UPDATE`) in id order, which prevents overdrawing under concurrent requests and prevents deadlocks between opposite transfers. Both are covered by tests that force the race.
- **Deposits** come from a per-currency `External` system account that is allowed to go negative.

## Known limitations

- No authentication yet (planned next).
- Every deposit in a currency locks the same `External` account row, so deposits in one currency are serialized.
- Two simultaneous first-ever deposits in a currency could create two `External` accounts; the ledger still balances.

## Security notes

Implemented and tested:
- **Broken access control:** every account endpoint checks ownership; another user's account returns `404` (tests try reading, depositing into, and spending from someone else's account).
- **Password storage:** Argon2id hashes with per-password salts; the login path takes similar time for unknown emails and wrong passwords.
- **Tokens:** short-lived (30 minutes) signed JWTs; decoding pins the algorithm and requires `exp` and `sub`; tampered, expired, unsigned, and wrongly-signed tokens are tested.
- **Injection:** all database access goes through SQLAlchemy with bound parameters; no SQL is built from user input.
- **Input validation:** strict integer amounts, length limits, and format checks at the schema layer.
- **Secrets:** the signing key is read from the environment (`.env` is git-ignored).

Known gaps (not yet addressed):
- No rate limiting or lockout on login, so password guessing is not throttled.
- Tokens cannot be revoked before they expire; there are no refresh tokens.
- `POST /accounts/{id}/deposits` lets any owner create money; in a real system deposits would come from a payment provider, not a user-facing endpoint.
- Registration reveals whether an email is already registered.
- No audit log of logins or transfers.
- HTTPS is required in any real deployment; the local dev server uses plain HTTP.

## Idempotency

`POST /transfers` and `POST /accounts/{id}/deposits` accept an optional `Idempotency-Key` header (any unique string up to 255 characters, typically a UUID). Retrying with the same key never repeats the money movement:

| Situation | Result |
|---|---|
| New key | The request runs; its response is saved |
| Same key, same request | The saved response is returned with `Idempotent-Replayed: true` |
| Same key, different request | `422` with code `idempotency_key_reused` |
| Two identical requests at the same moment | One runs; the other waits and receives the same response |
| Request failed (for example insufficient funds) | Nothing is saved, so a retry runs again |

Keys are scoped per user. The key row is written in the **same database transaction** as the ledger entries, so they commit or roll back together; a unique constraint on `(user_id, key)` makes concurrent duplicates wait on each other instead of both running.

Not yet handled: keys are never deleted (a real system expires them after a retention period), and the header is optional, so clients that omit it get no protection.

## Run with Docker

```bash
cp .env.example .env        # then edit .env and set real values
docker compose up --build -d
./scripts/smoke_test.sh     # end-to-end check against the running stack
docker compose down         # stop; data stays in a named volume
```

Three services start in order: `db` (PostgreSQL 16, healthchecked), `migrate` (runs `alembic upgrade head` once and exits), and `api` (starts after the migration succeeds). The database port is not published to the host. The image runs as a non-root user and contains no secrets; they are passed as environment variables.

Known limitations: the image installs everything in `requirements.txt`, including test tools (a runtime/dev split would make it smaller), and the base image tag is not pinned to a digest.

## Live demo

https://ledger-service-bi8t.onrender.com/docs (interactive API docs)

![Interactive API docs on the live deployment](docs/images/api-docs.png)

Deployed on Render (Docker web service, free tier) with a Neon Postgres database (free tier). Notes:

- The free web service sleeps after 15 minutes without traffic and the free database suspends when idle, so the first request after a quiet period can take about a minute.
- It is a demo: use fake data only. Registration is open and there is no rate limiting yet.
- Configuration is through environment variables: `DATABASE_URL` and `JWT_SECRET`. No secrets are stored in the repository or the image.
- Database migrations are currently run manually (`alembic upgrade head` against the database); automating this is a planned improvement.
- Deploys are triggered by merges to `main`, gated on CI passing.

## Live demo

https://ledger-service-bi8t.onrender.com/docs (interactive API docs)

Deployed on Render (Docker web service, free tier) with a Neon Postgres database (free tier). Notes:

- The free web service sleeps after 15 minutes without traffic and the free database suspends when idle, so the first request after a quiet period can take about a minute.
- It is a demo: use fake data only. Registration is open and there is no rate limiting yet.
- Configuration is through environment variables: `DATABASE_URL` and `JWT_SECRET`. No secrets are stored in the repository or the image.
- Database migrations are currently run manually (`alembic upgrade head` against the database); automating this is a planned improvement.
- Deploys are triggered by merges to `main`, gated on CI passing.
