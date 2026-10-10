# Benchmarks

Load tests with [k6](https://k6.io) against the docker compose stack on one laptop. The numbers describe this setup only; they are not a claim about production performance.

## Conditions

- Date: 2026-10-10
- Machine: Apple M2, 8 cores, 8 GB RAM. The load generator (k6 v2.3.0) and the server ran on the same machine.
- Docker Desktop limits: 8 CPUs, 4 GB memory.
- Code under test: commit `da0bb9e`; SQLAlchemy default connection pool (5 + 10 overflow) per worker; PostgreSQL 16 in a container with default settings.
- Procedure (both sessions): fresh database (`docker compose down -v` then `up`); series in the order reads, transfers_spread, transfers_hot; each series is 4 runs of 30 s at 10 virtual users. Raw output for every run is in `benchmarks/results/`.
- Session 1: one uvicorn worker. No predictions were written before this session. Two idle containers from another project (a Postgres and a Redis) were running; a `docker stats` snapshot showed them using about 0.3% CPU in total.
- Session 2: `WEB_CONCURRENCY=4` (via `benchmarks/compose.bench.yaml`); 4 worker processes confirmed from the startup logs. Predictions were committed before running (`benchmarks/predictions-workers4.md`). A `docker stats` snapshot from this session listed only the ledger containers.
- The medians below use runs 2 to 4. Run 1 was treated as a warm-up but is shown in the per-run table, because it was not slower than the others.

## Scenarios

- `reads`: `GET /accounts/{id}` (a balance is a `SUM` over ledger entries).
- `transfers_spread`: each virtual user transfers between its own pair of accounts (no shared rows).
- `transfers_hot`: all virtual users transfer between the same two accounts (every transfer waits on the same row locks).

Every transfer carries a unique idempotency key. Login happens once per run, outside the measured requests.

## Results

Median of runs 2 to 4, with the range in brackets.

| Scenario | Workers | Requests/s | p50 (ms) | p95 (ms) | p99 (ms) | Failed |
|---|---|---|---|---|---|---|
| reads | 1 | 610.1 (609.6-610.4) | 15.76 (15.74-15.77) | 22.92 (22.91-23.07) | 28.35 (28.27-28.47) | 0.00% |
| reads | 4 | 1545.9 (1407.9-1621.1) | 6.27 (5.58-6.43) | 9.40 (9.27-10.53) | 13.14 (12.49-15.56) | 0.00% |
| transfers_spread | 1 | 330.0 (319.3-331.2) | 29.34 (29.19-29.99) | 39.14 (38.94-42.53) | 46.85 (46.77-52.95) | 0.00% |
| transfers_spread | 4 | 578.9 (515.0-619.0) | 15.93 (13.65-17.04) | 28.78 (28.75-32.36) | 43.56 (40.96-56.06) | 0.00% |
| transfers_hot | 1 | 364.3 (360.9-368.1) | 27.33 (27.21-27.45) | 35.39 (34.72-36.43) | 42.16 (41.48-44.52) | 0.00% |
| transfers_hot | 4 | 366.8 (349.9-368.1) | 26.88 (26.39-27.81) | 36.40 (34.50-38.72) | 47.52 (43.73-49.39) | 0.00% |

Throughput by run in the 4-worker session (requests/s; run 1 is the warm-up that was excluded from the medians):

| Scenario | Run 1 | Run 2 | Run 3 | Run 4 |
|---|---|---|---|---|
| reads | 1559.8 | 1621.1 | 1407.9 | 1545.9 |
| transfers_spread | 695.6 | 619.0 | 578.9 | 515.0 |
| transfers_hot | 375.9 | 366.8 | 368.0 | 349.9 |

## Observations

- With 4 workers, reads were about 2.5 times and `transfers_spread` about 1.75 times the 1-worker throughput. `transfers_hot` was unchanged (366.8 against 364.3 requests/s).
- For `transfers_spread`, p50 roughly halved but p99 barely moved (46.85 to 43.56 ms).
- With 1 worker, `transfers_hot` was about 10% faster than `transfers_spread`, which was unexpected.
- In the 1-worker session, throughput times mean latency was about 9.9 in every scenario, consistent with 10 closed-loop users.
- With 4 workers, run-to-run variation was much larger than with 1 worker (reads varied by about 14%).
- In the 4-worker session, `transfers_spread` throughput fell on every run, from 695.6 to 515.0 requests/s (about 26%). Reads showed no trend and `transfers_hot` was nearly flat.
- Resource snapshots (single samples, not series). 1 worker, during `transfers_spread`: API 141.69% CPU and 70.98 MiB, database 20.45% CPU. 4 workers (scenario not recorded): API 356.90% CPU and 302.6 MiB, database 82.16% CPU and 202.5 MiB. Four workers used about four times the memory of one.

## Interpretation (inference, not measured directly)

- Same-account transfers are capped at about 365 per second here. If the row lock is the limit, each transfer holds its locks for about 1 / 364 s, roughly 2.7 ms. Every deposit in a currency locks the same system account row, so deposits would face the same ceiling (not benchmarked).
- A single API process limited reads and transfers between different accounts. The exact mechanism (CPU, or thread contention inside one process) was not isolated.
- Decision: the default stays at 1 worker, and the worker count is a documented setting (`WEB_CONCURRENCY`). The free-tier deployment has limited memory, and the 4-worker run used about 300 MiB; check the instance limits before raising it.

## Limitations

- Load generator and server share one machine; Docker Desktop on macOS adds network overhead.
- Each configuration was measured in one session. The decline in `transfers_spread` throughput across runs could come from heat (a fanless laptop), database growth, or CPU contention; this was not separated, so treat the spread figures as a range (515 to 696 requests/s in the 4-worker session).
- The two sessions differed slightly: idle containers from another project were running only in session 1.
- Default database settings and 30-second runs, so rare slow requests are only partly captured.
- The tail of `transfers_spread` did not improve with more workers; its cause was not investigated.
- Deposits were not benchmarked.

## Reproduce

```bash
brew install k6
docker compose down -v && docker compose up --build -d
benchmarks/run.sh reads 10
benchmarks/run.sh transfers_spread 10
benchmarks/run.sh transfers_hot 10

# 4 workers:
docker compose down -v
WEB_CONCURRENCY=4 docker compose -f compose.yaml -f benchmarks/compose.bench.yaml up --build -d
LABEL=workers4 benchmarks/run.sh reads 10    # and the other two scenarios
```
