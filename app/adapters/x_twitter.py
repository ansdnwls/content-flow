"""X adapter using Posts API v2 and media upload v2."""

from __future__ import annotations

import asyncio
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

X_API_V2 = "https://api.x.com/2"
MEDIA_UPLOAD_INIT = f"{X_API_V2}/media/upload/initialize"

# Chunked upload: 5 MB segments
_CHUNK_SIZE = 5 * 1024 * 1024
_MAX_POST_TEXT_LENGTH = 280


class XTwitterAdapter(PlatformAdapter):
    platform_name = "x_twitter"

    @staticmethod
    def _parse_created_at(value: str | None) -> datetime:
        if value:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        return datetime.now(UTC)

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        if text and len(text) > _MAX_POST_TEXT_LENGTH:
            return PublishResult(
                success=False,
                error=f"X posts must be {_MAX_POST_TEXT_LENGTH} characters or fewer",
            )

        tweet_body: dict[str, Any] = {}
        if text:
            tweet_body["text"] = text

        if media:
            media_ids = []
            for media_item in media:
                media_id = await self._upload_media(media_item, credentials)
                if media_id is None:
                    return PublishResult(
                        success=False,
                        error=f"Media upload failed for {media_item.url}",
                    )
                media_ids.append(media_id)
            tweet_body["media"] = {"media_ids": media_ids}

        reply_settings = options.get("reply_settings")
        if reply_settings:
            tweet_body["reply_settings"] = reply_settings

        quote_tweet_id = options.get("quote_tweet_id")
        if quote_tweet_id:
            tweet_body["quote_tweet_id"] = quote_tweet_id

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{X_API_V2}/tweets",
                headers={**headers, "Content-Type": "application/json"},
                json=tweet_body,
            )
            if resp.status_code != 201:
                return PublishResult(success=False, error=resp.text)

            data = resp.json().get("data", {})
            tweet_id = data.get("id")
            return PublishResult(
                success=True,
                platform_post_id=tweet_id,
                url=f"https://x.com/i/status/{tweet_id}",
                raw_response=data,
            )

    async def _upload_media(
        self, media_item: MediaSpec, credentials: dict[str, str]
    ) -> str | None:
        access_token = credentials["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=120.0) as client:
            download_resp = await client.get(media_item.url)
            if download_resp.status_code != 200:
                return None

            media_bytes = download_resp.content
            total_bytes = len(media_bytes)
            media_type = "video/mp4" if media_item.media_type == "video" else "image/jpeg"
            media_category = "tweet_video" if media_item.media_type == "video" else "tweet_image"

            init_resp = await client.post(
                MEDIA_UPLOAD_INIT,
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "media_type": media_type,
                    "media_category": media_category,
                    "shared": True,
                    "total_bytes": total_bytes,
                },
            )
            if init_resp.status_code not in (200, 201):
                return None

            media_id = init_resp.json().get("data", {}).get("id")
            if not media_id:
                return None

            append_url = f"{X_API_V2}/media/upload/{media_id}/append"
            for segment_index, offset in enumerate(range(0, total_bytes, _CHUNK_SIZE)):
                chunk = media_bytes[offset : offset + _CHUNK_SIZE]
                append_resp = await client.post(
                    append_url,
                    headers=headers,
                    data={"segment_index": str(segment_index)},
                    files={"media": ("chunk", chunk, media_type)},
                )
                if append_resp.status_code not in (200, 201):
                    return None

            finalize_resp = await client.post(
                f"{X_API_V2}/media/upload/{media_id}/finalize",
                headers=headers,
            )
            if finalize_resp.status_code not in (200, 201):
                return None

            if not await self._wait_for_media_processing(
                client,
                headers,
                media_id,
                finalize_resp.json().get("data", {}).get("processing_info"),
            ):
                return None

            return media_id

    async def _wait_for_media_processing(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        media_id: str,
        processing_info: dict[str, Any] | None,
    ) -> bool:
        if not processing_info:
            return True

        for _ in range(10):
            state = processing_info.get("state")
            if state == "succeeded":
                return True
            if state == "failed":
                return False

            await asyncio.sleep(float(processing_info.get("check_after_secs", 1)))
            status_resp = await client.get(
                f"{X_API_V2}/media/upload",
                headers=headers,
                params={"command": "STATUS", "media_id": media_id},
            )
            if status_resp.status_code != 200:
                return False
            processing_info = status_resp.json().get("data", {}).get("processing_info")
            if not processing_info:
                return True

        return False

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{X_API_V2}/tweets/{platform_post_id}",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{X_API_V2}/users/me",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        comments: list[Comment] = []
        next_token: str | None = None
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params: dict[str, Any] = {
                    "query": f"conversation_id:{platform_post_id} -is:retweet",
                    "max_results": 100,
                    "tweet.fields": "author_id,created_at,conversation_id,in_reply_to_user_id",
                    "expansions": "author_id",
                    "user.fields": "name,username",
                }
                if next_token:
                    params["next_token"] = next_token

                resp = await client.get(
                    f"{X_API_V2}/tweets/search/recent",
                    headers=headers,
                    params=params,
                )
                if resp.status_code != 200:
                    break

                payload = resp.json()
                users = {
                    user.get("id", ""): user
                    for user in payload.get("includes", {}).get("users", [])
                }
                for item in payload.get("data", []):
                    created_at = self._parse_created_at(item.get("created_at"))
                    if since and created_at <= since:
                        continue
                    author = users.get(item.get("author_id", ""), {})
                    comments.append(
                        Comment(
                            platform_comment_id=item.get("id", ""),
                            author_id=item.get("author_id", ""),
                            author_name=author.get("name")
                            or author.get("username", ""),
                            text=item.get("text", ""),
                            created_at=created_at,
                            raw=item,
                        )
                    )

                next_token = payload.get("meta", {}).get("next_token")
                if not next_token:
                    break

        return comments

    async def reply_comment(
        self,
        platform_post_id: str,
        comment_id: str,
        text: str,
        credentials: dict[str, str],
    ) -> ReplyResult:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{X_API_V2}/tweets",
                headers={
                    "Authorization": f"Bearer {credentials['access_token']}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "reply": {"in_reply_to_tweet_id": comment_id},
                },
            )
            if resp.status_code != 201:
                return ReplyResult(success=False, error=resp.text)

            data = resp.json().get("data", {})
            return ReplyResult(
                success=True,
                platform_comment_id=data.get("id"),
            )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        headers = {"Authorization": f"Bearer {credentials['access_token']}"}
        results: list[AnalyticsData] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            if platform_post_id:
                resp = await client.get(
                    f"{X_API_V2}/tweets/{platform_post_id}",
                    headers=headers,
                    params={"tweet.fields": "public_metrics"},
                )
                if resp.status_code != 200:
                    return results

                data = resp.json().get("data", {})
                metrics = data.get("public_metrics", {})
                views = int(metrics.get("impression_count", 0))
                likes = int(metrics.get("like_count", 0))
                comments = int(metrics.get("reply_count", 0))
                shares = int(metrics.get("retweet_count", 0)) + int(
                    metrics.get("quote_count", 0)
                )
                denominator = views if views > 0 else 1
                results.append(
                    AnalyticsData(
                        platform=self.platform_name,
                        platform_post_id=data.get("id"),
                        views=views,
                        likes=likes,
                        comments=comments,
                        shares=shares,
                        impressions=views,
                        engagement_rate=round(
                            (likes + comments + shares) / denominator * 100,
                            2,
                        ),
                        raw=metrics,
                    )
                )
                return results

            resp = await client.get(
                f"{X_API_V2}/users/me",
                headers=headers,
                params={"user.fields": "public_metrics"},
            )
            if resp.status_code != 200:
                return results

            data = resp.json().get("data", {})
            metrics = data.get("public_metrics", {})
            results.append(
                AnalyticsData(
                    platform=self.platform_name,
                    followers=int(metrics.get("followers_count", 0)),
                    raw=metrics,
                )
            )
        return results
