# Benchmarks

Load tests with [k6](https://k6.io) against the docker compose stack on one laptop. The numbers describe this setup only; they are not a claim about production performance.

## Conditions

- Date: 2026-10-10
- Machine: Apple M2, 8 cores, 8 GB RAM. The load generator (k6 v2.3.0) and the server ran on the same machine.
- Docker Desktop limits: 8 CPUs, 4 GB memory.
- Code under test: commit `da0bb9e`; one uvicorn worker; SQLAlchemy default connection pool (5 + 10 overflow); PostgreSQL 16 in a container with default settings.
- Two idle containers from another project (a Postgres and a Redis) were also running.
- Procedure: fresh database (`docker compose down -v` then `up`); series in the order reads, transfers_spread, transfers_hot; each series is 4 runs of 30 s at 10 virtual users. Run 1 of each series is a warm-up and is excluded. Raw output for every run is in `benchmarks/results/`.
- No predictions were written before this first series.

## Scenarios

- `reads`: `GET /accounts/{id}` (a balance is a `SUM` over ledger entries).
- `transfers_spread`: each virtual user transfers between its own pair of accounts (no shared rows).
- `transfers_hot`: all virtual users transfer between the same two accounts (every transfer waits on the same row locks).

Every transfer carries a unique idempotency key. Login happens once per run, outside the measured requests.

## Results

Median of runs 2 to 4, with the range in brackets.

| Scenario | Requests/s | p50 (ms) | p95 (ms) | p99 (ms) | Failed |
|---|---|---|---|---|---|
| reads | 610.1 (609.6-610.4) | 15.76 (15.74-15.77) | 22.92 (22.91-23.07) | 28.35 (28.27-28.47) | 0.00% |
| transfers_spread | 330.0 (319.3-331.2) | 29.34 (29.19-29.99) | 39.14 (38.94-42.53) | 46.85 (46.77-52.95) | 0.00% |
| transfers_hot | 364.3 (360.9-368.1) | 27.33 (27.21-27.45) | 35.39 (34.72-36.43) | 42.16 (41.48-44.52) | 0.00% |

## Observations

- Reads reach about 1.7 to 1.85 times the throughput of transfers.
- The contended scenario (`transfers_hot`) was not slower than the uncontended one: about 10% higher throughput, with non-overlapping ranges. This was unexpected.
- In every scenario, throughput times mean latency is about 9.9, consistent with 10 closed-loop users, which sanity-checks the measurements.
- One `docker stats` snapshot taken during a `transfers_spread` run showed the API container at 141.69% CPU and the database at 20.45% (a single sample, not a measurement series).

## Open question and next experiment

Hypothesis (not yet tested): the single API process is the bottleneck in all three scenarios. Planned experiment: run with 4 API workers (`WEB_CONCURRENCY=4`) using the same procedure, with predictions written down beforehand.

| Scenario | Requests/s, 4 workers | p95 (ms), 4 workers |
|---|---|---|
| reads | [X] | [X] |
| transfers_spread | [X] | [X] |
| transfers_hot | [X] | [X] |

## Limitations

- Load generator and server share one machine; Docker Desktop on macOS adds network overhead.
- Single machine, single run session, default database settings; do not compare these numbers with other hardware.
- Each run is 30 seconds, so rare slow requests are only partly captured.

## Reproduce

```bash
brew install k6
docker compose down -v && docker compose up --build -d
benchmarks/run.sh reads 10
benchmarks/run.sh transfers_spread 10
benchmarks/run.sh transfers_hot 10
```
