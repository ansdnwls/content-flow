"""TikTok OAuth 2.0 provider."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.oauth.provider import OAuthProvider, OAuthTokenResponse, OAuthUserInfo

_AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize/"
_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
_USERINFO_URL = "https://open.tiktokapis.com/v2/user/info/"


class TikTokOAuthProvider(OAuthProvider):
    platform = "tiktok"

    def get_authorize_url(self, state: str, scopes: list[str] | None = None) -> str:
        settings = get_settings()
        scope = ",".join(scopes or ["user.info.basic", "video.publish", "video.upload"])
        params = {
            "client_key": settings.tiktok_client_key,
            "redirect_uri": self.build_redirect_uri(),
            "response_type": "code",
            "scope": scope,
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokenResponse:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthTokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )

    async def refresh_access_token(self, refresh_token: str) -> OAuthTokenResponse:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthTokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                json={"fields": ["open_id", "display_name", "avatar_url"]},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {}).get("user", {})

        return OAuthUserInfo(
            platform_user_id=data.get("open_id", ""),
            handle=data.get("display_name", ""),
            display_name=data.get("display_name"),
            metadata={"avatar_url": data.get("avatar_url")},
        )
