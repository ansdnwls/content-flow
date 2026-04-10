# Smoke Test Results

- Generated at: `2026-04-09T22:08:46.015525+00:00`
- Base URL: `http://127.0.0.1:8000`
- Summary: `8 passed, 1 failed`

## Steps

| Step | Status | Detail |
| --- | --- | --- |
| Bootstrap identity | OK | user_id=a606bae4-c6eb-4389-90b8-d4d55db142ce |
| API live | OK | status=200 |
| API ready | FAIL | status=503 readiness=degraded |
| DB connection | OK | supabase=ok |
| Redis connection | OK | redis=ok |
| API key create + persist | OK | key_id=0c32ee95-9dce-4ac0-b09b-38891c321af2 stored=yes |
| Workspace create | OK | workspace_id=a466e136-d11d-4948-bf35-33377e5386ef slug=smoke-workspace-9184e0 |
| Posts dry run | OK | validated=True deliveries=1 |
| Webhook register + dispatch | OK | webhook_id=de3f4b12-11c3-4c76-9721-26ff512a8d79 status=delivered received=1 |

## Failures

- `API ready`: status=503 readiness=degraded
