from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_request_id_header_and_metrics_output(monkeypatch) -> None:
    async def fake_runtime() -> dict[str, int]:
        return {"active_workers": 1, "queue_depth": 0, "db_connections": 1}

    monkeypatch.setattr("app.api.health.collect_runtime_metrics", fake_runtime)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/health/live")
        metrics = await client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    assert metrics.status_code == 200
    assert "http_requests_total" in metrics.text
    assert "http_request_duration_seconds" in metrics.text
    assert "contentflow_active_workers" in metrics.text


async def test_error_tracking_middleware_captures_exception(monkeypatch) -> None:
    captured: list[str] = []

    def fake_capture(request, exc) -> None:
        captured.append(f"{request.url.path}:{exc.__class__.__name__}")

    monkeypatch.setattr("app.core.middleware.capture_exception_context", fake_capture)

    async def boom():
        raise RuntimeError("boom")

    app.add_api_route("/__monitoring_boom", boom, methods=["GET"])

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            response = await client.get("/__monitoring_boom")
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__monitoring_boom"
        ]

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert response.headers["X-Request-ID"]
    assert captured == ["/__monitoring_boom:RuntimeError"]
