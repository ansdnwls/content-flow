"""YouTube adapter — Resumable upload via YouTube Data API v3."""

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


class YouTubeAdapter(PlatformAdapter):
    platform_name = "youtube"

    @staticmethod
    def _build_status(options: dict[str, Any]) -> dict[str, Any]:
        privacy_status = options.get("privacy", "public")
        publish_at = options.get("publish_at")
        status_body: dict[str, Any] = {"privacyStatus": privacy_status}

        if publish_at:
            parsed = datetime.fromisoformat(str(publish_at).replace("Z", "+00:00"))
            status_body["publishAt"] = parsed.isoformat()
            status_body["privacyStatus"] = "private"

        return status_body

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        video = next((m for m in media if m.media_type == "video"), None)
        if not video:
            return PublishResult(success=False, error="No video provided")

        snippet = {
            "title": options.get("title", text or "Untitled"),
            "description": options.get("description", ""),
            "tags": options.get("tags", []),
            "categoryId": options.get("category_id", "22"),
        }
        try:
            status_body = self._build_status(options)
        except ValueError:
            return PublishResult(success=False, error="publish_at must be RFC 3339 / ISO 8601")

        async with httpx.AsyncClient() as client:
            # Step 1: Start resumable upload
            init_resp = await client.post(
                "https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"snippet": snippet, "status": status_body},
            )
            if init_resp.status_code != 200:
                return PublishResult(success=False, error=init_resp.text)

            upload_url = init_resp.headers.get("Location")
            if not upload_url:
                return PublishResult(success=False, error="No upload URL returned")

            # Step 2: Download media then upload
            media_resp = await client.get(video.url)
            upload_resp = await client.put(
                upload_url,
                content=media_resp.content,
                headers={"Content-Type": "video/*"},
            )

            if upload_resp.status_code in (200, 201):
                data = upload_resp.json()
                return PublishResult(
                    success=True,
                    platform_post_id=data["id"],
                    url=f"https://youtu.be/{data['id']}",
                    raw_response=data,
                )
            return PublishResult(success=False, error=upload_resp.text)

    async def delete(self, platform_post_id: str, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                "https://www.googleapis.com/youtube/v3/videos",
                params={"id": platform_post_id},
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 204

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "id", "mine": "true"},
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200

    async def get_comments(
        self,
        platform_post_id: str,
        credentials: dict[str, str],
        since: datetime | None = None,
    ) -> list[Comment]:
        access_token = credentials["access_token"]
        comments: list[Comment] = []
        page_token: str | None = None

        async with httpx.AsyncClient() as client:
            while True:
                params: dict[str, Any] = {
                    "part": "snippet",
                    "videoId": platform_post_id,
                    "order": "time",
                    "maxResults": 100,
                }
                if page_token:
                    params["pageToken"] = page_token

                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/commentThreads",
                    params=params,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code != 200:
                    break

                data = resp.json()
                for item in data.get("items", []):
                    snippet = item["snippet"]["topLevelComment"]["snippet"]
                    published = datetime.fromisoformat(
                        snippet["publishedAt"].replace("Z", "+00:00")
                    )
                    if since and published <= since:
                        return comments
                    comments.append(
                        Comment(
                            platform_comment_id=item["snippet"]["topLevelComment"]["id"],
                            author_id=snippet.get("authorChannelId", {}).get("value", ""),
                            author_name=snippet.get("authorDisplayName", ""),
                            text=snippet.get("textDisplay", ""),
                            created_at=published,
                            parent_id=None,
                            raw=item,
                        )
                    )

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

        return comments

    async def reply_comment(
        self,
        platform_post_id: str,
        comment_id: str,
        text: str,
        credentials: dict[str, str],
    ) -> ReplyResult:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://www.googleapis.com/youtube/v3/comments",
                params={"part": "snippet"},
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "snippet": {
                        "parentId": comment_id,
                        "textOriginal": text,
                    }
                },
            )
            if resp.status_code in (200, 201):
                data = resp.json()
                return ReplyResult(success=True, platform_comment_id=data["id"])
            return ReplyResult(success=False, error=resp.text)

    async def get_analytics(
        self,
        platform_post_id: str | None,
        credentials: dict[str, str],
    ) -> list[AnalyticsData]:
        access_token = credentials["access_token"]
        results: list[AnalyticsData] = []
        async with httpx.AsyncClient() as client:
            if platform_post_id:
                # Single video statistics
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/videos",
                    params={
                        "part": "statistics",
                        "id": platform_post_id,
                    },
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        stats = item.get("statistics", {})
                        views = int(stats.get("viewCount", 0))
                        likes = int(stats.get("likeCount", 0))
                        comments = int(stats.get("commentCount", 0))
                        total = views if views > 0 else 1
                        results.append(AnalyticsData(
                            platform="youtube",
                            platform_post_id=item["id"],
                            views=views,
                            likes=likes,
                            comments=comments,
                            shares=0,
                            engagement_rate=round(
                                (likes + comments) / total * 100, 2,
                            ),
                            raw=stats,
                        ))
            else:
                # Channel-level: subscriber count
                resp = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels",
                    params={"part": "statistics", "mine": "true"},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        stats = item.get("statistics", {})
                        results.append(AnalyticsData(
                            platform="youtube",
                            views=int(stats.get("viewCount", 0)),
                            followers=int(
                                stats.get("subscriberCount", 0),
                            ),
                            raw=stats,
                        ))
        return results
