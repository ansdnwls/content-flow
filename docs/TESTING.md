# Testing

## Batch Runs

Use batched execution when you need fast feedback on a large change set.

```powershell
pytest -q tests/test_feature_flags.py tests/test_admin.py
pytest -q tests/test_notifications.py tests/test_notification_prefs.py
pytest -q tests/test_webhook_idempotency.py tests/test_webhooks/test_webhook_dispatcher.py
```

For a broad smoke pass before a full run:

```powershell
pytest -q tests/test_openapi.py tests/test_health.py tests/test_security/test_auth_bypass.py
```

## Hang Debugging

Install dev dependencies so `pytest-timeout` is available:

```powershell
pip install -e ".[dev]"
```

Reproduce hangs with a per-test timeout:

```powershell
pytest -vv --timeout=30 --timeout-method=thread
```

If the suite stalls late, rerun the last failing or last timed-out case:

```powershell
pytest -vv --lf --timeout=30 --timeout-method=thread
```

If a timeout report shows `socket.getaddrinfo`, suspect an unmocked HTTP request or an unclosed async client.

## Async Test Practices

- Prefer `async with httpx.AsyncClient(...)` for request clients.
- Mock outbound HTTP calls with `respx` or `httpx.MockTransport`.
- Do not return raw `AsyncClient` instances from fixtures unless teardown closes them.
- Keep async fixtures at function scope unless there is a clear reason to share state.
- Close Redis, `aiohttp.ClientSession`, and `httpx.AsyncClient` instances in test teardown.
- Clear `app.dependency_overrides` after tests that patch FastAPI dependencies.
