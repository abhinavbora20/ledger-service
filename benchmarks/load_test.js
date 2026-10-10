import http from 'k6/http';
import { check, fail } from 'k6';
import { Trend, Counter, Rate } from 'k6/metrics';

const BASE_URL = __ENV.BASE_URL || 'http://127.0.0.1:8000';
const SCENARIO = __ENV.SCENARIO || 'reads';
const ACCOUNTS = 40; // 20 pairs: supports up to 20 VUs with no shared accounts

export const options = {
  vus: parseInt(__ENV.VUS || '10'),
  duration: __ENV.DURATION || '30s',
};

// Custom metrics are recorded only for the measured requests, so the slow
// one-time setup (password hashing) does not pollute the results.
const latency = new Trend('bench_latency_ms', true);
const requests = new Counter('bench_requests');
const failed = new Rate('bench_failed');

function post(path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return http.post(`${BASE_URL}${path}`, JSON.stringify(body), { headers });
}

export function setup() {
  const email = `bench-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;
  const password = 'benchmark-password-1';

  let r = post('/auth/register', { email, password });
  if (r.status !== 201) fail(`register failed: ${r.status} ${r.body}`);
  r = post('/auth/login', { email, password });
  if (r.status !== 200) fail(`login failed: ${r.status} ${r.body}`);
  const token = r.json('access_token');

  const accounts = [];
  for (let i = 0; i < ACCOUNTS; i++) {
    r = post('/accounts', { name: `Bench ${i}`, currency: 'INR' }, token);
    if (r.status !== 201) fail(`create account failed: ${r.status} ${r.body}`);
    const id = r.json('id');
    // Large enough that no transfer in the test can run out of funds.
    r = post(`/accounts/${id}/deposits`, { amount: 1000000000 }, token);
    if (r.status !== 201) fail(`deposit failed: ${r.status} ${r.body}`);
    accounts.push(id);
  }
  return { token, accounts };
}

export default function (data) {
  const { token, accounts } = data;
  const auth = { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
  let res;
  let expected;

  if (SCENARIO === 'reads') {
    const id = accounts[(__VU + __ITER) % accounts.length];
    res = http.get(`${BASE_URL}/accounts/${id}`, {
      headers: auth,
      tags: { name: 'GET /accounts/{id}' },
    });
    expected = 200;
  } else {
    let from;
    let to;
    if (SCENARIO === 'transfers_hot') {
      from = accounts[0];
      to = accounts[1];
    } else if (SCENARIO === 'transfers_spread') {
      const pair = (__VU - 1) % (accounts.length / 2);
      from = accounts[pair * 2];
      to = accounts[pair * 2 + 1];
    } else {
      fail(`unknown SCENARIO: ${SCENARIO}`);
    }
    const headers = Object.assign({}, auth, {
      'Idempotency-Key': `bench-${__VU}-${__ITER}-${Date.now()}`,
    });
    res = http.post(
      `${BASE_URL}/transfers`,
      JSON.stringify({ from_account_id: from, to_account_id: to, amount: 1, description: 'bench' }),
      { headers, tags: { name: 'POST /transfers' } },
    );
    expected = 201;
  }

  latency.add(res.timings.duration);
  requests.add(1);
  failed.add(res.status !== expected);
  check(res, { 'expected status': (r) => r.status === expected });
}
