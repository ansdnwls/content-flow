from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_health_endpoints() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        health = await client.get("/health")
        healthz = await client.get("/healthz")
        live = await client.get("/health/live")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert healthz.status_code == 200
    assert healthz.json()["status"] == "ok"
    assert live.status_code == 200
    assert live.json()["status"] == "ok"


async def test_ready_and_health_metrics(monkeypatch) -> None:
    async def fake_supabase() -> bool:
        return True

    async def fake_redis() -> bool:
        return True

    def fake_celery() -> bool:
        return True

    async def fake_runtime() -> dict[str, int]:
        return {"active_workers": 2, "queue_depth": 4, "db_connections": 1}

    monkeypatch.setattr("app.api.health.check_supabase_ready", fake_supabase)
    monkeypatch.setattr("app.api.health.check_redis_ready", fake_redis)
    monkeypatch.setattr("app.api.health.check_celery_ready", fake_celery)
    monkeypatch.setattr("app.api.health.collect_runtime_metrics", fake_runtime)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        ready = await client.get("/health/ready")
        metrics = await client.get("/health/metrics")

    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert metrics.status_code == 200
    assert metrics.json()["active_workers"] == 2


async def test_ready_returns_503_when_dependency_down(monkeypatch) -> None:
    async def fake_supabase() -> bool:
        return False

    async def fake_redis() -> bool:
        return True

    def fake_celery() -> bool:
        return False

    monkeypatch.setattr("app.api.health.check_supabase_ready", fake_supabase)
    monkeypatch.setattr("app.api.health.check_redis_ready", fake_redis)
    monkeypatch.setattr("app.api.health.check_celery_ready", fake_celery)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        ready = await client.get("/health/ready")

    assert ready.status_code == 503
    payload = ready.json()["detail"]
    assert payload["status"] == "degraded"
    assert payload["checks"]["supabase"] is False
