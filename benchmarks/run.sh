#!/usr/bin/env bash
# usage: benchmarks/run.sh <reads|transfers_spread|transfers_hot> <vus> [runs]
# Run 1 of every series is a warm-up and is discarded when reporting.
set -euo pipefail

SCENARIO="$1"
VUS="$2"
RUNS="${3:-4}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
mkdir -p benchmarks/results

for i in $(seq 1 "$RUNS"); do
  OUT="benchmarks/results/${SCENARIO}-vus${VUS}-run${i}.txt"
  echo "== ${SCENARIO}, ${VUS} VUs, run ${i} of ${RUNS} =="
  BASE_URL="$BASE_URL" SCENARIO="$SCENARIO" VUS="$VUS" DURATION="${DURATION:-30s}" \
    k6 run --summary-trend-stats="avg,med,p(95),p(99),max" benchmarks/load_test.js | tee "$OUT"
done
