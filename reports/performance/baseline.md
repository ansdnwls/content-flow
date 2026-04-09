# Performance Baseline

## Current Expected Baseline

These are the working expectations for local and pre-production load runs using `scripts/load_test/locustfile.py`.

| Scenario | Expected P50 | Expected P95 | Expected P99 | Expected Error Rate |
|----------|--------------|--------------|--------------|---------------------|
| `normal_user` | `< 50ms` | `< 100ms` | `< 250ms` | `< 0.1%` |
| `spike` | `< 100ms` | `< 200ms` | `< 500ms` | `< 1.0%` |
| `sustained` | `< 60ms` | `< 100ms` | `< 300ms` | `< 0.1%` |
| `bulk_posting` | `< 80ms` | `< 150ms` | `< 400ms` | `< 0.5%` |

## Target

- `p95 < 100ms`
- `error_rate < 0.1%`

## Reading The Numbers

- If `p50` is low but `p95` and `p99` climb, the issue is likely queueing, DB contention, or cache misses.
- If all percentiles rise together, the bottleneck is usually CPU, network saturation, or upstream dependency latency.
- If error rate rises before latency, authentication, rate limiting, or worker dispatch should be inspected first.

## Recording

| Date | Environment | Scenario | P50 | P95 | P99 | Error Rate | Notes |
|------|-------------|----------|-----|-----|-----|------------|-------|
| _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ | _TBD_ |
