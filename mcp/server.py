"""MCP server tools backed by the running ContentFlow HTTP API."""

from __future__ import annotations

import os
from typing import Any

import httpx

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - optional runtime dependency
    FastMCP = None

API_BASE_URL = os.getenv("CONTENTFLOW_API_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("CONTENTFLOW_API_KEY", "")
TIMEOUT_SECONDS = float(os.getenv("CONTENTFLOW_MCP_TIMEOUT_SECONDS", "30"))


class ContentFlowAPIClient:
    def __init__(self, *, base_url: str = API_BASE_URL, api_key: str = API_KEY) -> None:
        self.base_url = base_url
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers=self._headers(),
                json=json_body,
                params=params,
            )
            response.raise_for_status()
            return response.json()


api_client = ContentFlowAPIClient()


async def contentflow_post(payload: dict[str, Any]) -> dict[str, Any]:
    return await api_client.request("POST", "/api/v1/posts", json_body=payload)


async def contentflow_generate_video(payload: dict[str, Any]) -> dict[str, Any]:
    return await api_client.request("POST", "/api/v1/videos/generate", json_body=payload)


async def contentflow_list_accounts() -> dict[str, Any]:
    return await api_client.request("GET", "/api/v1/accounts")


async def contentflow_get_analytics() -> dict[str, Any]:
    return await api_client.request("GET", "/api/v1/analytics")


if FastMCP is not None:  # pragma: no branch
    mcp = FastMCP("contentflow")
    mcp.tool(name="contentflow_post")(contentflow_post)
    mcp.tool(name="contentflow_generate_video")(contentflow_generate_video)
    mcp.tool(name="contentflow_list_accounts")(contentflow_list_accounts)
    mcp.tool(name="contentflow_get_analytics")(contentflow_get_analytics)
else:  # pragma: no cover - depends on optional package
    mcp = None


def main() -> None:
    if mcp is None:
        raise RuntimeError("Install the `mcp` package to run the ContentFlow MCP server.")
    mcp.run()


if __name__ == "__main__":  # pragma: no cover - manual entrypoint
    main()
