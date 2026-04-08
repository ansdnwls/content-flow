"""Mastodon adapter — status posting via Mastodon-compatible API."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from app.adapters.base import (
    AnalyticsData,
    Comment,
    MediaSpec,
    PlatformAdapter,
    PublishResult,
    ReplyResult,
)


class MastodonAdapter(PlatformAdapter):
    platform_name = "mastodon"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        instance_url = credentials["instance_url"].rstrip("/")
        token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        visibility = options.get("visibility", "public")
        spoiler_text = options.get("spoiler_text", "")

        async with httpx.AsyncClient(timeout=60.0) as client:
            media_ids: list[str] = []
            for m in media:
                media_id = await self._upload_media(
                    client, instance_url, headers, m,
                )
                if media_id:
                    media_ids.append(media_id)

            payload: dict[str, Any] = {
                "status": text or "",
                "visibility": visibility,
                "media_ids": media_ids,
            }
            if spoiler_text:
                payload["spoiler_text"] = spoiler_text

            language = options.get("language")
            if language:
                payload["language"] = language

            resp = await client.post(
                f"{instance_url}/api/v1/statuses",
                json=payload,
                headers=headers,
            )
            if resp.status_code not in (200, 201):
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            return PublishResult(
                success=True,
                platform_post_id=str(data.get("id", "")),
                url=data.get("url"),
                raw_response=data,
            )

    async def _upload_media(
        self,
        client: httpx.AsyncClient,
        instance_url: str,
        headers: dict[str, str],
        media: MediaSpec,
    ) -> str | None:
        dl_resp = await client.get(media.url)
        if dl_resp.status_code != 200:
            return None

        content_type = dl_resp.headers.get("content-type", "application/octet-stream")
        filename = media.url.rsplit("/", 1)[-1] or "upload"

        resp = await client.post(
            f"{instance_url}/api/v2/media",
            files={"file": (filename, dl_resp.content, content_type)},
            headers=headers,
        )
        if resp.status_code not in (200, 202):
            return None
        return str(resp.json().get("id", ""))

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        instance_url = credentials["instance_url"].rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{instance_url}/api/v1/statuses/{platform_post_id}",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        instance_url = credentials["instance_url"].rstrip("/")
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{instance_url}/api/v1/accounts/verify_credentials",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200

    @staticmethod
    def _parse_created_at(value: str | None) -> datetime:
        if value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(UTC)

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        instance_url = credentials["instance_url"].rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{instance_url}/api/v1/statuses/{platform_post_id}/context",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            if resp.status_code != 200:
                return []

            comments: list[Comment] = []
            for item in resp.json().get("descendants", []):
                created_at = self._parse_created_at(item.get("created_at"))
                if since and created_at <= since:
                    continue
                account = item.get("account", {})
                comments.append(
                    Comment(
                        platform_comment_id=str(item.get("id", "")),
                        author_id=str(account.get("id", "")),
                        author_name=account.get("display_name")
                        or account.get("username", ""),
                        text=item.get("content", ""),
                        created_at=created_at,
                        parent_id=item.get("in_reply_to_id"),
                        raw=item,
                    )
                )
            return comments

    async def reply_comment(
        self,
        platform_post_id: str,
        comment_id: str,
        text: str,
        credentials: dict[str, str],
    ) -> ReplyResult:
        instance_url = credentials["instance_url"].rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{instance_url}/api/v1/statuses",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
                data={"status": text, "in_reply_to_id": comment_id},
            )
            if resp.status_code not in (200, 201):
                return ReplyResult(success=False, error=resp.text)

            data = resp.json()
            return ReplyResult(
                success=True,
                platform_comment_id=str(data.get("id", "")),
            )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        instance_url = credentials["instance_url"].rstrip("/")
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            if platform_post_id:
                resp = await client.get(
                    f"{instance_url}/api/v1/statuses/{platform_post_id}",
                    headers=headers,
                )
                if resp.status_code != 200:
                    return []

                data = resp.json()
                likes = int(data.get("favourites_count", 0))
                comments = int(data.get("replies_count", 0))
                shares = int(data.get("reblogs_count", 0))
                return [
                    AnalyticsData(
                        platform=self.platform_name,
                        platform_post_id=str(data.get("id", platform_post_id)),
                        likes=likes,
                        comments=comments,
                        shares=shares,
                        raw=data,
                    )
                ]

            resp = await client.get(
                f"{instance_url}/api/v1/accounts/verify_credentials",
                headers=headers,
            )
            if resp.status_code != 200:
                return []

            data = resp.json()
            return [
                AnalyticsData(
                    platform=self.platform_name,
                    followers=int(data.get("followers_count", 0)),
                    raw=data,
                )
            ]
