#!/usr/bin/env bash
# End-to-end check against a running server.
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
EMAIL="smoke-$(date +%s)-${RANDOM}@example.com"
PASSWORD="smoke-test-password-1"
JSON="Content-Type: application/json"

field() { python3 -c "import sys, json; print(json.load(sys.stdin)[sys.argv[1]])" "$1"; }

expect() { # label, expected, actual
  if [ "$2" != "$3" ]; then
    echo "FAIL: $1 (expected $2, got $3)"
    exit 1
  fi
  echo "ok: $1"
}

curl -fsS -X POST "$BASE_URL/auth/register" -H "$JSON" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" > /dev/null

TOKEN=$(curl -fsS -X POST "$BASE_URL/auth/login" -H "$JSON" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}" | field access_token)
AUTH="Authorization: Bearer $TOKEN"

new_account() {
  curl -fsS -X POST "$BASE_URL/accounts" -H "$AUTH" -H "$JSON" \
    -d "{\"name\":\"$1\",\"currency\":\"INR\"}" | field id
}
balance() { curl -fsS "$BASE_URL/accounts/$1" -H "$AUTH" | field balance; }

A=$(new_account "Smoke A")
B=$(new_account "Smoke B")

# The same deposit sent twice with one idempotency key must credit only once.
for _ in 1 2; do
  curl -fsS -X POST "$BASE_URL/accounts/$A/deposits" -H "$AUTH" -H "$JSON" \
    -H "Idempotency-Key: smoke-deposit-$EMAIL" -d '{"amount":1000}' > /dev/null
done
expect "deposit credited once despite retry" 1000 "$(balance "$A")"

curl -fsS -X POST "$BASE_URL/transfers" -H "$AUTH" -H "$JSON" \
  -d "{\"from_account_id\":$A,\"to_account_id\":$B,\"amount\":250,\"description\":\"smoke\"}" > /dev/null
expect "sender balance after transfer" 750 "$(balance "$A")"
expect "receiver balance after transfer" 250 "$(balance "$B")"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/accounts/$A")
expect "request without a token is refused" 401 "$CODE"

echo "SMOKE TEST PASSED"
