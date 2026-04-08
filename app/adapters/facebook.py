"""Facebook adapter — Page posting via Graph API."""

from __future__ import annotations

from datetime import datetime
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

GRAPH_API = "https://graph.facebook.com/v19.0"


class FacebookAdapter(PlatformAdapter):
    platform_name = "facebook"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        page_token = credentials["page_access_token"]
        page_id = credentials["page_id"]

        async with httpx.AsyncClient(timeout=60.0) as client:
            if not media:
                return await self._publish_text(client, page_id, page_token, text, options)

            first = media[0]
            if first.media_type == "video":
                return await self._publish_video(
                    client, page_id, page_token, first, text, options
                )

            if len(media) == 1 and first.media_type == "image":
                return await self._publish_photo(
                    client, page_id, page_token, first, text, options
                )

            # Multiple images → multi-photo post
            return await self._publish_multi_photo(
                client, page_id, page_token, media, text, options
            )

    async def _publish_text(
        self, client, page_id, token, text, options
    ) -> PublishResult:
        params: dict[str, Any] = {"access_token": token}
        if text:
            params["message"] = text
        link = options.get("link")
        if link:
            params["link"] = link

        resp = await client.post(f"{GRAPH_API}/{page_id}/feed", params=params)
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        post_id = data.get("id", "")
        return PublishResult(
            success=True,
            platform_post_id=post_id,
            url=f"https://www.facebook.com/{post_id.replace('_', '/posts/')}",
            raw_response=data,
        )

    async def _publish_photo(
        self, client, page_id, token, image: MediaSpec, text, options
    ) -> PublishResult:
        params: dict[str, Any] = {
            "url": image.url,
            "access_token": token,
        }
        if text:
            params["message"] = text

        resp = await client.post(f"{GRAPH_API}/{page_id}/photos", params=params)
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        return PublishResult(
            success=True,
            platform_post_id=data.get("post_id", data.get("id", "")),
            raw_response=data,
        )

    async def _publish_multi_photo(
        self, client, page_id, token, media: list[MediaSpec], text, options
    ) -> PublishResult:
        # Step 1: Upload each photo as unpublished
        attached_media = []
        for m in media:
            if m.media_type != "image":
                continue
            resp = await client.post(
                f"{GRAPH_API}/{page_id}/photos",
                params={
                    "url": m.url,
                    "published": "false",
                    "access_token": token,
                },
            )
            if resp.status_code != 200:
                return PublishResult(
                    success=False, error=f"Photo upload failed: {resp.text}"
                )
            attached_media.append({"media_fbid": resp.json()["id"]})

        # Step 2: Create post with attached photos
        params: dict[str, Any] = {"access_token": token}
        if text:
            params["message"] = text
        for i, am in enumerate(attached_media):
            params[f"attached_media[{i}]"] = f'{{"media_fbid":"{am["media_fbid"]}"}}'

        resp = await client.post(f"{GRAPH_API}/{page_id}/feed", params=params)
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        return PublishResult(
            success=True,
            platform_post_id=data.get("id", ""),
            raw_response=data,
        )

    async def _publish_video(
        self, client, page_id, token, video: MediaSpec, text, options
    ) -> PublishResult:
        params: dict[str, Any] = {
            "file_url": video.url,
            "access_token": token,
        }
        if text:
            params["description"] = text
        title = options.get("title")
        if title:
            params["title"] = title

        resp = await client.post(
            f"{GRAPH_API}/{page_id}/videos",
            params=params,
            timeout=120.0,
        )
        if resp.status_code != 200:
            return PublishResult(success=False, error=resp.text)

        data = resp.json()
        video_id = data.get("id", "")
        return PublishResult(
            success=True,
            platform_post_id=video_id,
            url=f"https://www.facebook.com/{page_id}/videos/{video_id}",
            raw_response=data,
        )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{GRAPH_API}/{platform_post_id}",
                params={"access_token": credentials["page_access_token"]},
            )
            return resp.status_code == 200

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{GRAPH_API}/me",
                params={"access_token": credentials["page_access_token"]},
            )
            return resp.status_code == 200

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        comments: list[Comment] = []
        url = f"{GRAPH_API}/{platform_post_id}/comments"
        params: dict[str, Any] = {
            "fields": "id,from,message,created_time,parent",
            "access_token": credentials["page_access_token"],
        }
        if since:
            params["since"] = int(since.timestamp())

        async with httpx.AsyncClient(timeout=30.0) as client:
            while url:
                resp = await client.get(url, params=params)
                if resp.status_code != 200:
                    break

                payload = resp.json()
                for item in payload.get("data", []):
                    created_value = item.get("created_time")
                    if not created_value:
                        continue
                    created_at = datetime.fromisoformat(
                        created_value.replace("Z", "+00:00")
                    )
                    from_data = item.get("from", {})
                    parent = item.get("parent", {})
                    comments.append(
                        Comment(
                            platform_comment_id=item.get("id", ""),
                            author_id=from_data.get("id", ""),
                            author_name=from_data.get("name", ""),
                            text=item.get("message", ""),
                            created_at=created_at,
                            parent_id=parent.get("id"),
                            raw=item,
                        )
                    )

                paging = payload.get("paging", {})
                url = paging.get("next", "")
                params = {}

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
                f"{GRAPH_API}/{comment_id}/comments",
                params={
                    "message": text,
                    "access_token": credentials["page_access_token"],
                },
            )
            if resp.status_code != 200:
                return ReplyResult(success=False, error=resp.text)

            payload = resp.json()
            return ReplyResult(
                success=True,
                platform_comment_id=payload.get("id"),
            )

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        token = credentials["page_access_token"]
        page_id = credentials.get("page_id", "me")
        results: list[AnalyticsData] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            if platform_post_id:
                resp = await client.get(
                    f"{GRAPH_API}/{platform_post_id}/insights",
                    params={
                        "metric": (
                            "post_impressions,post_impressions_unique,"
                            "post_reactions_like_total,post_comments,post_shares"
                        ),
                        "access_token": token,
                    },
                )
                if resp.status_code != 200:
                    return results

                metrics: dict[str, int] = {}
                for entry in resp.json().get("data", []):
                    name = entry.get("name", "")
                    value = entry.get("values", [{}])[0].get("value", 0)
                    if isinstance(value, dict):
                        value = sum(
                            int(v) for v in value.values() if isinstance(v, (int, float))
                        )
                    metrics[name] = int(value) if isinstance(value, (int, float)) else 0

                impressions = metrics.get("post_impressions", 0)
                reach = metrics.get("post_impressions_unique", 0)
                likes = metrics.get("post_reactions_like_total", 0)
                comments = metrics.get("post_comments", 0)
                shares = metrics.get("post_shares", 0)
                denominator = impressions if impressions > 0 else 1
                results.append(
                    AnalyticsData(
                        platform=self.platform_name,
                        platform_post_id=platform_post_id,
                        views=impressions,
                        likes=likes,
                        comments=comments,
                        shares=shares,
                        impressions=impressions,
                        reach=reach,
                        engagement_rate=round(
                            (likes + comments + shares) / denominator * 100,
                            2,
                        ),
                        raw=metrics,
                    )
                )
                return results

            resp = await client.get(
                f"{GRAPH_API}/{page_id}",
                params={
                    "fields": "fan_count,followers_count",
                    "access_token": token,
                },
            )
            if resp.status_code != 200:
                return results

            payload = resp.json()
            results.append(
                AnalyticsData(
                    platform=self.platform_name,
                    followers=int(
                        payload.get("followers_count", payload.get("fan_count", 0))
                    ),
                    raw=payload,
                )
            )
        return results
