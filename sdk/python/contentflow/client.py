"""ContentFlow API client — sync and async interfaces."""

from __future__ import annotations

from typing import Any

import httpx


DEFAULT_BASE_URL = "https://api.contentflow.dev"
DEFAULT_TIMEOUT = 30.0


class _PostsResource:
    """Posts sub-resource bound to a client session."""

    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/posts"

    def create(
        self,
        *,
        platforms: list[str],
        text: str | None = None,
        media_urls: list[str] | None = None,
        media_type: str = "text",
        scheduled_for: str | None = None,
        platform_options: dict | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"platforms": platforms}
        if text is not None:
            body["text"] = text
        if media_urls:
            body["media_urls"] = media_urls
            body["media_type"] = media_type
        if scheduled_for:
            body["scheduled_for"] = scheduled_for
        if platform_options:
            body["platform_options"] = platform_options
        resp = self._client.post(self._url, json=body)
        resp.raise_for_status()
        return resp.json()

    def get(self, post_id: str) -> dict[str, Any]:
        resp = self._client.get(f"{self._url}/{post_id}")
        resp.raise_for_status()
        return resp.json()

    def list(
        self, *, page: int = 1, limit: int = 20, status: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        resp = self._client.get(self._url, params=params)
        resp.raise_for_status()
        return resp.json()

    def cancel(self, post_id: str) -> dict[str, Any]:
        resp = self._client.delete(f"{self._url}/{post_id}")
        resp.raise_for_status()
        return resp.json()


class _VideosResource:
    """Videos sub-resource bound to a client session."""

    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/videos"

    def generate(
        self,
        *,
        topic: str,
        mode: str = "general",
        language: str = "ko",
        format: str = "shorts",
        style: str = "realistic",
        auto_publish: dict | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "topic": topic,
            "mode": mode,
            "language": language,
            "format": format,
            "style": style,
        }
        if auto_publish:
            body["auto_publish"] = auto_publish
        resp = self._client.post(f"{self._url}/generate", json=body)
        resp.raise_for_status()
        return resp.json()

    def get(self, video_id: str) -> dict[str, Any]:
        resp = self._client.get(f"{self._url}/{video_id}")
        resp.raise_for_status()
        return resp.json()


class _AccountsResource:
    """Accounts sub-resource bound to a client session."""

    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/accounts"

    def list(self) -> dict[str, Any]:
        resp = self._client.get(self._url)
        resp.raise_for_status()
        return resp.json()

    def connect(self, platform: str) -> dict[str, Any]:
        resp = self._client.post(f"{self._url}/connect/{platform}")
        resp.raise_for_status()
        return resp.json()


class _AnalyticsResource:
    """Analytics sub-resource bound to a client session."""

    def __init__(self, client: httpx.Client, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/analytics"

    def get(self, *, platform: str | None = None) -> dict[str, Any]:
        url = f"{self._url}/{platform}" if platform else self._url
        resp = self._client.get(url)
        resp.raise_for_status()
        return resp.json()


# ── Async variants ────────────────────────────────────────────────


class _AsyncPostsResource:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/posts"

    async def create(
        self,
        *,
        platforms: list[str],
        text: str | None = None,
        media_urls: list[str] | None = None,
        media_type: str = "text",
        scheduled_for: str | None = None,
        platform_options: dict | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"platforms": platforms}
        if text is not None:
            body["text"] = text
        if media_urls:
            body["media_urls"] = media_urls
            body["media_type"] = media_type
        if scheduled_for:
            body["scheduled_for"] = scheduled_for
        if platform_options:
            body["platform_options"] = platform_options
        resp = await self._client.post(self._url, json=body)
        resp.raise_for_status()
        return resp.json()

    async def get(self, post_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"{self._url}/{post_id}")
        resp.raise_for_status()
        return resp.json()

    async def list(
        self, *, page: int = 1, limit: int = 20, status: str | None = None
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"page": page, "limit": limit}
        if status:
            params["status"] = status
        resp = await self._client.get(self._url, params=params)
        resp.raise_for_status()
        return resp.json()

    async def cancel(self, post_id: str) -> dict[str, Any]:
        resp = await self._client.delete(f"{self._url}/{post_id}")
        resp.raise_for_status()
        return resp.json()


class _AsyncVideosResource:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/videos"

    async def generate(
        self,
        *,
        topic: str,
        mode: str = "general",
        language: str = "ko",
        format: str = "shorts",
        style: str = "realistic",
        auto_publish: dict | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "topic": topic,
            "mode": mode,
            "language": language,
            "format": format,
            "style": style,
        }
        if auto_publish:
            body["auto_publish"] = auto_publish
        resp = await self._client.post(f"{self._url}/generate", json=body)
        resp.raise_for_status()
        return resp.json()

    async def get(self, video_id: str) -> dict[str, Any]:
        resp = await self._client.get(f"{self._url}/{video_id}")
        resp.raise_for_status()
        return resp.json()


class _AsyncAccountsResource:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/accounts"

    async def list(self) -> dict[str, Any]:
        resp = await self._client.get(self._url)
        resp.raise_for_status()
        return resp.json()

    async def connect(self, platform: str) -> dict[str, Any]:
        resp = await self._client.post(f"{self._url}/connect/{platform}")
        resp.raise_for_status()
        return resp.json()


class _AsyncAnalyticsResource:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._url = f"{base_url}/api/v1/analytics"

    async def get(self, *, platform: str | None = None) -> dict[str, Any]:
        url = f"{self._url}/{platform}" if platform else self._url
        resp = await self._client.get(url)
        resp.raise_for_status()
        return resp.json()


# ── Main clients ──────────────────────────────────────────────────


class ContentFlow:
    """Synchronous ContentFlow API client.

    Usage::

        from contentflow import ContentFlow

        cf = ContentFlow(api_key="cf_live_xxx")
        post = cf.posts.create(text="Hello!", platforms=["youtube", "tiktok"])
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._client = httpx.Client(
            base_url="",
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )
        self._base_url = base_url.rstrip("/")
        self.posts = _PostsResource(self._client, self._base_url)
        self.videos = _VideosResource(self._client, self._base_url)
        self.accounts = _AccountsResource(self._client, self._base_url)
        self.analytics = _AnalyticsResource(self._client, self._base_url)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> ContentFlow:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


class AsyncContentFlow:
    """Asynchronous ContentFlow API client.

    Usage::

        from contentflow import AsyncContentFlow

        async with AsyncContentFlow(api_key="cf_live_xxx") as cf:
            post = await cf.posts.create(text="Hello!", platforms=["youtube"])
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url="",
            headers={"X-API-Key": api_key},
            timeout=timeout,
        )
        self._base_url = base_url.rstrip("/")
        self.posts = _AsyncPostsResource(self._client, self._base_url)
        self.videos = _AsyncVideosResource(self._client, self._base_url)
        self.accounts = _AsyncAccountsResource(self._client, self._base_url)
        self.analytics = _AsyncAnalyticsResource(self._client, self._base_url)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncContentFlow:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()
