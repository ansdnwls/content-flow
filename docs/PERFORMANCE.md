# ContentFlow Performance & Load Testing

## Current Status

Performance work completed on April 8, 2026:

1. Redis-backed API key auth cache
   - Verified API keys are cached for `300s`
   - Cache stores only the key fingerprint -> api key id mapping
   - `last_used_at` writes are throttled to once per `60s` per key
2. Response caching
   - `GET /api/v1/analytics` -> `300s`
   - `GET /api/v1/trending` -> `1800s`
   - `GET /api/v1/usage` -> `60s`
   - `GET /api/v1/accounts` -> `3600s`
   - `GET /api/v1/videos/templates` -> `3600s`
3. Post listing query reduction
   - `GET /api/v1/posts` now fetches `post_deliveries` in the initial select
4. Batched audit writes
   - Audit logs now use `BatchWriter(flush_interval=1.0, batch_size=100)`
5. DB index migration
   - Added [010_performance_indexes.sql](/C:/Users/y2k_w/projects/content-flow/infra/supabase/migrations/010_performance_indexes.sql)

## Before / After

### Auth Cache Benchmark

Local microbenchmark run on April 8, 2026 with 25 repeated auth checks against the same key:

| Path | Time |
|------|------|
| Before cache | `5174.10ms` |
| After cache warm-up | `6.58ms` |
| Relative speedup | `786.66x` |

Benchmark notes:

- Before: bcrypt verification on every authenticated request
- After: first request warms Redis; repeated requests reuse the cached api key id
- This benchmark isolates the auth path, not full HTTP request latency

### Optimization Effects

| Optimization | Main Effect | Expected Benefit |
|-------------|-------------|------------------|
| API key cache | CPU + auth latency | Removes repeat bcrypt work on hot keys |
| `last_used_at` throttling | DB writes | Avoids one write per request on active keys |
| Response cache | DB + external API load | Reduces repeated dashboard and trend reads |
| Joined post listing | Query count | Avoids delivery fan-out during post pagination |
| Batched audit writes | Insert pressure | Replaces many tiny inserts with fewer larger batches |
| New indexes | Read/query plan stability | Improves owner/status/date lookups and retry queue scans |

## Load Test Setup

### Tool

[Locust](https://locust.io/) for HTTP load generation.

### Installation

```bash
pip install locust
```

### Scenarios

| Scenario | Spawn Rate | Runtime | Description |
|----------|------------|---------|-------------|
| `normal_user` | `10 users/sec` | `5m` | Mixed authenticated post and analytics traffic |
| `spike` | `1000 users/sec` | `1m` | Burst load and queue shock |
| `sustained` | `100 users/sec` | `10m` | Longer steady-state regression |
| `bulk_posting` | `25 users/sec` | `5m` | Content Bomb-heavy write load |

### Running Tests

```bash
# Interactive mode (web UI at http://localhost:8089)
locust -f scripts/load_test/locustfile.py --host http://localhost:8000

# Headless scenario run
./scripts/run_load_test.sh http://localhost:8000 normal_user
```

## Expected Baselines

Targets measured on a single Railway instance (1 vCPU, 512MB RAM):

| Metric | Target | Notes |
|--------|--------|-------|
| P50 latency (reads) | < 50ms | GET endpoints |
| P95 latency (reads) | < 200ms | GET endpoints |
| P50 latency (writes) | < 100ms | POST endpoints |
| P95 latency (writes) | < 500ms | POST endpoints |
| Throughput | > 100 RPS | At 100 concurrent users |
| Error rate | < 1% | At 100 concurrent users |

## Production Recommendations

| Setting | Recommended Value | Why |
|--------|--------------------|-----|
| `API_KEY_CACHE_TTL_SECONDS` | `300` | Good balance between speed and stale-key exposure |
| `API_KEY_LAST_USED_UPDATE_SECONDS` | `60` | Preserves usage visibility without write amplification |
| API replicas | `2` | Safer baseline once cached read traffic grows |
| Worker concurrency | `8` | Good starting point for publish and video side work |
| Redis | Dedicated instance | Keeps auth cache, response cache, and rate limits isolated |
| Audit batch size | `100` | Reduces insert overhead without over-buffering |
| Audit flush interval | `1s` | Fast enough for ops visibility while staying asynchronous |

## Known Bottlenecks

1. bcrypt API key verification
   - Mitigation: implemented Redis key cache
   - Remaining impact: first request per TTL window still pays bcrypt cost
2. Supabase cold connections
   - Mitigation: Supabase PgBouncer / pooled connections
3. Celery dispatch latency
   - Mitigation: already using grouped enqueue for bulk posts
4. External trending fetches
   - Mitigation: 30-minute cache plus scheduled refresh worker

## Next Candidates

1. Read replicas for analytics and usage endpoints
2. Batched email log writes using the shared batch writer
3. Precomputed usage rollups if monthly volumes become large
4. Edge caching for OpenAPI and public landing assets
5. Endpoint-specific cache invalidation for analytics snapshot writes beyond the current user-prefix invalidation

## Reports

Load test reports are written to `reports/load/` after running `scripts/run_load_test.sh`.

```text
reports/load/
  report_100u_YYYYMMDD_HHMMSS.html
  report_500u_YYYYMMDD_HHMMSS.html
  report_1000u_YYYYMMDD_HHMMSS.html
  csv_100u_*.csv
  csv_500u_*.csv
  csv_1000u_*.csv
```
