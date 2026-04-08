"""Security headers and request validation middleware tests."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport

from app.main import app


@pytest.mark.anyio()
async def test_security_headers_present() -> None:
    """All security headers must be set on responses."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("X-XSS-Protection") == "1; mode=block"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "default-src" in resp.headers.get("Content-Security-Policy", "")
    assert "geolocation=()" in resp.headers.get("Permissions-Policy", "")
    assert "max-age=" in resp.headers.get("Strict-Transport-Security", "")


@pytest.mark.anyio()
async def test_scanner_user_agent_blocked() -> None:
    """Requests from known scanner user-agents must be rejected."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/health",
            headers={"User-Agent": "sqlmap/1.6"},
        )
    assert resp.status_code == 403


@pytest.mark.anyio()
async def test_nikto_user_agent_blocked() -> None:
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/health",
            headers={"User-Agent": "Nikto/2.1.6"},
        )
    assert resp.status_code == 403


@pytest.mark.anyio()
async def test_oversized_content_length_rejected() -> None:
    """Requests with Content-Length > 10MB should be rejected."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.post(
            "/api/v1/posts",
            content=b"x",
            headers={
                "Content-Length": str(11 * 1024 * 1024),
                "Content-Type": "application/json",
            },
        )
    assert resp.status_code == 413


@pytest.mark.anyio()
async def test_normal_user_agent_allowed() -> None:
    """Normal user-agents must not be blocked."""
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test",
    ) as client:
        resp = await client.get(
            "/health",
            headers={"User-Agent": "Mozilla/5.0 ContentFlow-Client/1.0"},
        )
    assert resp.status_code == 200
