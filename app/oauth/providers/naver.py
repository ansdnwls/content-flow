"""Naver OAuth 2.0 provider for Naver Blog."""
from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.oauth.provider import OAuthProvider, OAuthTokenResponse, OAuthUserInfo

_AUTHORIZE_URL = "https://nid.naver.com/oauth2.0/authorize"
_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
_USERINFO_URL = "https://openapi.naver.com/v1/nid/me"

_DEFAULT_SCOPES = ["blog"]


class NaverOAuthProvider(OAuthProvider):
    """Handles Naver OAuth 2.0 for Naver Blog."""

    platform = "naver_blog"

    def get_authorize_url(self, state: str, scopes: list[str] | None = None) -> str:
        settings = get_settings()
        params = {
            "client_id": settings.naver_client_id,
            "redirect_uri": self.build_redirect_uri(),
            "response_type": "code",
            "state": state,
            "scope": " ".join(scopes or _DEFAULT_SCOPES),
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokenResponse:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                params={
                    "grant_type": "authorization_code",
                    "client_id": settings.naver_client_id,
                    "client_secret": settings.naver_client_secret,
                    "code": code,
                    "state": "",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("error"):
            raise RuntimeError(
                f"Naver token exchange failed: {data.get('error_description', data['error'])}"
            )

        return OAuthTokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_in=data.get("expires_in"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )

    async def refresh_access_token(self, refresh_token: str) -> OAuthTokenResponse:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                params={
                    "grant_type": "refresh_token",
                    "client_id": settings.naver_client_id,
                    "client_secret": settings.naver_client_secret,
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("error"):
            raise RuntimeError(
                f"Naver token refresh failed: {data.get('error_description', data['error'])}"
            )

        return OAuthTokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_in=data.get("expires_in"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                _USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        profile = data.get("response", data)
        naver_id = str(profile.get("id", ""))
        nickname = profile.get("nickname", "")

        return OAuthUserInfo(
            platform_user_id=naver_id,
            handle=nickname or naver_id,
            display_name=profile.get("name") or nickname,
            metadata={
                "email": profile.get("email"),
                "profile_image": profile.get("profile_image"),
                "blog_name": profile.get("blog_name"),
            },
        )
