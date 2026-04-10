"""Google OAuth 2.0 provider for YouTube and Google Business."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.oauth.provider import OAuthProvider, OAuthTokenResponse, OAuthUserInfo

_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

_DEFAULT_SCOPES = {
    "youtube": [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.readonly",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile",
    ],
}

class GoogleOAuthProvider(OAuthProvider):
    """Handles Google OAuth for YouTube (extendable to Google Business)."""

    def __init__(self, platform: str = "youtube") -> None:
        self.platform = platform

    def get_authorize_url(self, state: str, scopes: list[str] | None = None) -> str:
        settings = get_settings()
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": self.build_redirect_uri(),
            "response_type": "code",
            "scope": " ".join(scopes or _DEFAULT_SCOPES.get(self.platform, [])),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokenResponse:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
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
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthTokenResponse(
            access_token=data["access_token"],
            refresh_token=refresh_token,
            expires_in=data.get("expires_in"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthUserInfo(
            platform_user_id=data["id"],
            handle=data.get("email", data["id"]),
            display_name=data.get("name"),
            metadata={"picture": data.get("picture")},
        )
