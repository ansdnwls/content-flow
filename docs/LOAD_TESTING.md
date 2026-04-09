# Load Testing

## Purpose

ContentFlow uses Locust scenarios in `scripts/load_test/locustfile.py` to exercise the real HTTP surface with authenticated traffic.

Each scenario starts with `GET /health/live`, then uses an API key to call:

- `GET /api/v1/posts`
- `POST /api/v1/posts?dry_run=true`
- `GET /api/v1/analytics`
- `POST /api/v1/bombs` for the `bulk_posting` scenario

## Scenarios

| Scenario | Spawn Rate | Runtime | Purpose |
|----------|------------|---------|---------|
| `normal_user` | `10 users/sec` | `5m` | Day-to-day mixed read/write traffic. |
| `spike` | `1000 users/sec` | `1m` | Burst tolerance and queue shock. |
| `sustained` | `100 users/sec` | `10m` | Longer steady-state regression check. |
| `bulk_posting` | `25 users/sec` | `5m` | Content Bomb-heavy write pressure. |

## Local Run

1. Start local services:

```bash
docker-compose up
```

2. Export an API key:

```bash
export LOAD_TEST_API_KEY=cf_live_your_local_key
export LOAD_TEST_SCENARIO=normal_user
```

3. Start Locust:

```bash
locust -f scripts/load_test/locustfile.py --host http://localhost:8000
```

4. Open the web UI:

```text
http://localhost:8089
```

5. Or run headless with the helper:

```bash
./scripts/run_load_test.sh http://localhost:8000 normal_user
```

## What To Read

Primary metrics:

- `p50`: median response time. Good first signal for steady-state performance.
- `p95`: latency tail most users feel. This is the main regression guard.
- `p99`: extreme tail. Useful for burst and lock contention debugging.
- `error_rate_pct`: request failures divided by total requests.

Suggested interpretation:

| Level | P95 | P99 | Error Rate |
|-------|-----|-----|------------|
| Normal | `< 100ms` | `< 250ms` | `< 0.1%` |
| Warning | `100-250ms` | `250-500ms` | `0.1%-1%` |
| Risk | `> 250ms` | `> 500ms` | `> 1%` |

For `bulk_posting`, a slightly higher latency envelope is acceptable if the error rate remains low and the queue recovers.

## CI Usage

The workflow `.github/workflows/load_test.yml` supports:

- Manual runs via `workflow_dispatch`
- Nightly scheduled runs against `vars.LOAD_TEST_HOST` and `secrets.LOAD_TEST_API_KEY`

Artifacts uploaded by CI:

- Locust HTML report
- CSV time series
- JSON summary with `p50`, `p95`, `p99`, and `error_rate_pct`

## Result Template

Use this template when recording a run:

```markdown
## Load Test Result

- Date:
- Environment:
- Scenario:
- Host:
- Users:
- Spawn rate:
- Runtime:
- Total requests:
- P50:
- P95:
- P99:
- Error rate:
- Notes:
```
