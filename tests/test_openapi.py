"""Tests for OpenAPI documentation endpoints."""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_openapi_json_returns_valid_schema() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "ContentFlow API"
        assert schema["info"]["version"] == "0.2.0"
        assert "paths" in schema
        assert schema["info"]["license"]["name"] == "MIT"
        assert len(schema.get("servers", [])) == 2


async def test_openapi_schema_has_all_tags() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()
        tag_names = {tag["name"] for tag in schema.get("tags", [])}
        expected = {
            "Posts", "Videos", "Bombs", "Comments",
            "Prediction", "Schedules", "Usage",
            "Accounts", "Analytics", "ops",
        }
        assert expected.issubset(tag_names)


async def test_openapi_schema_has_error_responses() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/openapi.json")
        schema = resp.json()
        # Check that posts endpoints include 401 error response
        post_create = schema["paths"].get("/api/v1/posts", {}).get("post", {})
        assert "401" in post_create.get("responses", {})


async def test_docs_endpoint_returns_html() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/docs")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")


async def test_redoc_endpoint_returns_html() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        resp = await client.get("/redoc")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")
