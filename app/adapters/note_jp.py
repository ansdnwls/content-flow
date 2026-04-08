"""note.com (Japan) adapter — note API for article publishing."""

from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import MediaSpec, PlatformAdapter, PublishResult

NOTE_API = "https://note.com/api"


class NoteJpAdapter(PlatformAdapter):
    platform_name = "note_jp"

    async def publish(
        self,
        text: str | None,
        media: list[MediaSpec],
        options: dict[str, Any],
        credentials: dict[str, str],
    ) -> PublishResult:
        access_token = credentials["access_token"]
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        title = options.get("title", "ContentFlow Post")
        note_type = options.get("type", "TextNote")  # TextNote, ImageNote, MovieNote
        status = options.get("status", "published")  # draft, published
        price = options.get("price", 0)
        hashtags = options.get("hashtags", [])

        # Build body content with media embeds
        body_parts: list[str] = []
        for m in media:
            if m.media_type == "image":
                body_parts.append(f'<figure><img src="{m.url}" /></figure>')
            elif m.media_type == "video":
                body_parts.append(f'<figure><video src="{m.url}" controls></video></figure>')
        if text:
            body_parts.append(text)

        payload: dict[str, Any] = {
            "title": title,
            "body": "\n".join(body_parts),
            "type": note_type,
            "status": status,
            "price": price,
            "hashtags": hashtags,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{NOTE_API}/v3/notes",
                headers=headers,
                json=payload,
            )

            if resp.status_code not in (200, 201):
                return PublishResult(success=False, error=resp.text)

            data = resp.json()
            note_data = data.get("data", data)
            note_id = str(note_data.get("id", ""))
            key = note_data.get("key", note_id)
            user_slug = note_data.get("user", {}).get("urlname", "")
            url = f"https://note.com/{user_slug}/n/{key}" if user_slug else None

            return PublishResult(
                success=True,
                platform_post_id=note_id,
                url=url,
                raw_response=data,
            )

    async def delete(
        self, platform_post_id: str, credentials: dict[str, str]
    ) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.delete(
                f"{NOTE_API}/v3/notes/{platform_post_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code in (200, 204)

    async def validate_credentials(self, credentials: dict[str, str]) -> bool:
        access_token = credentials["access_token"]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{NOTE_API}/v2/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            return resp.status_code == 200
