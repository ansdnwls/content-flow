"""LinkedIn adapter using Posts API with Images and Videos upload flows."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

LINKEDIN_API = "https://api.linkedin.com"
LINKEDIN_VERSION = "202510"


class LinkedInAdapter(PlatformAdapter):
    platform_name = "linkedin"

    @staticmethod
    def _is_valid_author_urn(author: str) -> bool:
        return author.startswith("urn:li:person:") or author.startswith(
            "urn:li:organization:"
        )

    def _build_headers(
        self,
        access_token: str,
        *,
        include_json_content_type: bool = True,
        version: str = LINKEDIN_VERSION,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "X-Restli-Protocol-Version": "2.0.0",
            "Linkedin-Version": version,
        }
        if include_json_content_type:
            headers["Content-Type"] = "application/json"
        return headers

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        author = credentials.get("author_urn", options.get("author"))
        if not author:
            return PublishResult(success=False, error="Missing author URN")
        if not self._is_valid_author_urn(author):
            return PublishResult(
                success=False,
                error=(
                    "author must be a LinkedIn person or organization URN "
                    "(urn:li:person:<id> or urn:li:organization:<id>)"
                ),
            )

        headers = self._build_headers(access_token)

        async with httpx.AsyncClient(timeout=60.0) as client:
            media_assets = []
            for media_item in media:
                asset = await self._upload_media(client, access_token, headers, author, media_item)
                if asset is None:
                    return PublishResult(
                        success=False,
                        error=f"Media upload failed for {media_item.url}",
                    )
                media_assets.append(asset)

            post_body: dict[str, Any] = {
                "author": author,
                "commentary": text or "",
                "visibility": options.get("visibility", "PUBLIC"),
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": options.get(
                    "is_reshare_disabled_by_author",
                    False,
                ),
            }

            if media_assets:
                if len(media_assets) == 1:
                    asset_urn, _ = media_assets[0]
                    post_body["content"] = {
                        "media": {
                            "id": asset_urn,
                            "title": options.get("title", ""),
                        }
                    }
                else:
                    post_body["content"] = {
                        "multiImage": {
                            "images": [
                                {"id": asset_urn, "altText": ""}
                                for asset_urn, _ in media_assets
                            ]
                        }
                    }

            resp = await client.post(
                f"{LINKEDIN_API}/rest/posts",
                headers=headers,
                json=post_body,
            )

            if resp.status_code in (200, 201):
                post_urn = resp.headers.get("x-restli-id", "")
                return PublishResult(
                    success=True,
                    platform_post_id=post_urn,
                    url=f"https://www.linkedin.com/feed/update/{post_urn}",
                    raw_response=resp.json() if resp.text else {},
                )
            return PublishResult(success=False, error=resp.text)

    async def _upload_media(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        headers: dict[str, str],
        author: str,
        media_item: MediaSpec,
    ) -> tuple[str, str] | None:
        if media_item.media_type == "video":
            return await self._upload_video(client, access_token, headers, author, media_item)
        return await self._upload_image(client, access_token, headers, author, media_item)

    async def _download_media(
        self,
        client: httpx.AsyncClient,
        media_item: MediaSpec,
    ) -> bytes | None:
        resp = await client.get(media_item.url)
        if resp.status_code != 200:
            return None
        return resp.content

    async def _upload_image(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        headers: dict[str, str],
        author: str,
        media_item: MediaSpec,
    ) -> tuple[str, str] | None:
        register_resp = await client.post(
            f"{LINKEDIN_API}/rest/images?action=initializeUpload",
            headers=headers,
            json={"initializeUploadRequest": {"owner": author}},
        )
        if register_resp.status_code not in (200, 201):
            return None

        payload = register_resp.json().get("value", {})
        upload_url = payload.get("uploadUrl")
        asset_urn = payload.get("image", "")
        if not upload_url or not asset_urn:
            return None

        media_bytes = await self._download_media(client, media_item)
        if media_bytes is None:
            return None

        upload_resp = await client.put(
            upload_url,
            content=media_bytes,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/jpeg"},
        )
        if upload_resp.status_code not in (200, 201):
            return None

        return asset_urn, media_item.media_type

    async def _upload_video(
        self,
        client: httpx.AsyncClient,
        access_token: str,
        headers: dict[str, str],
        author: str,
        media_item: MediaSpec,
    ) -> tuple[str, str] | None:
        media_bytes = await self._download_media(client, media_item)
        if media_bytes is None:
            return None

        register_resp = await client.post(
            f"{LINKEDIN_API}/rest/videos?action=initializeUpload",
            headers=headers,
            json={
                "initializeUploadRequest": {
                    "owner": author,
                    "fileSizeBytes": len(media_bytes),
                    "uploadCaptions": False,
                    "uploadThumbnail": False,
                }
            },
        )
        if register_resp.status_code not in (200, 201):
            return None

        payload = register_resp.json().get("value", {})
        asset_urn = payload.get("video", "")
        upload_token = payload.get("uploadToken")
        upload_instructions = payload.get("uploadInstructions", [])
        if not asset_urn or upload_token is None or not upload_instructions:
            return None

        uploaded_part_ids: list[str] = []
        for instruction in upload_instructions:
            upload_url = instruction.get("uploadUrl")
            first_byte = instruction.get("firstByte")
            last_byte = instruction.get("lastByte")
            if upload_url is None or first_byte is None or last_byte is None:
                return None

            chunk = media_bytes[first_byte : last_byte + 1]
            upload_resp = await client.put(
                upload_url,
                content=chunk,
                headers={"Authorization": f"Bearer {access_token}", "Content-Type": "video/mp4"},
            )
            if upload_resp.status_code not in (200, 201):
                return None

            etag = upload_resp.headers.get("ETag", "").strip('"')
            if not etag:
                return None
            uploaded_part_ids.append(etag)

        finalize_resp = await client.post(
            f"{LINKEDIN_API}/rest/videos?action=finalizeUpload",
            headers=headers,
            json={
                "finalizeUploadRequest": {
                    "video": asset_urn,
                    "uploadToken": upload_token,
                    "uploadedPartIds": uploaded_part_ids,
                }
            },
        )
        if finalize_resp.status_code not in (200, 201):
            return None

        return asset_urn, media_item.media_type

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{LINKEDIN_API}/rest/posts/{platform_post_id}",
                headers=self._build_headers(
                    credentials["access_token"],
                    include_json_content_type=False,
                ),
            )
            return resp.status_code == 204

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{LINKEDIN_API}/v2/userinfo",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
            )
            return resp.status_code == 200
