"""Meta OAuth 2.0 provider for Instagram, Facebook, and Threads."""

from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.oauth.provider import OAuthProvider, OAuthTokenResponse, OAuthUserInfo

_AUTHORIZE_URL = "https://www.facebook.com/v19.0/dialog/oauth"
_TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
_EXCHANGE_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
_ME_URL = "https://graph.facebook.com/v19.0/me"

_DEFAULT_SCOPES: dict[str, list[str]] = {
    "instagram": [
        "instagram_basic",
        "instagram_content_publish",
        "pages_show_list",
    ],
    "facebook": [
        "pages_manage_posts",
        "pages_read_engagement",
        "pages_show_list",
    ],
    "threads": [
        "threads_basic",
        "threads_content_publish",
        "threads_manage_replies",
    ],
}


class MetaOAuthProvider(OAuthProvider):
    """Handles Meta OAuth for Instagram, Facebook, and Threads."""

    def __init__(self, platform: str = "instagram") -> None:
        self.platform = platform

    def get_authorize_url(self, state: str, scopes: list[str] | None = None) -> str:
        settings = get_settings()
        params = {
            "client_id": settings.meta_client_id,
            "redirect_uri": self.build_redirect_uri(),
            "response_type": "code",
            "scope": ",".join(scopes or _DEFAULT_SCOPES.get(self.platform, [])),
            "state": state,
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokenResponse:
        settings = get_settings()

        # Step 1: exchange code for short-lived token
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _TOKEN_URL,
                params={
                    "client_id": settings.meta_client_id,
                    "client_secret": settings.meta_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            resp.raise_for_status()
            short_data = resp.json()

            # Step 2: exchange for long-lived token
            resp = await client.get(
                _EXCHANGE_URL,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.meta_client_id,
                    "client_secret": settings.meta_client_secret,
                    "fb_exchange_token": short_data["access_token"],
                },
            )
            resp.raise_for_status()
            long_data = resp.json()

        return OAuthTokenResponse(
            access_token=long_data["access_token"],
            refresh_token=None,
            expires_in=long_data.get("expires_in"),
            token_type=long_data.get("token_type", "Bearer"),
        )

    async def refresh_access_token(self, refresh_token: str) -> OAuthTokenResponse:
        """Meta long-lived tokens are refreshed by exchanging the current token."""
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _EXCHANGE_URL,
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.meta_client_id,
                    "client_secret": settings.meta_client_secret,
                    "fb_exchange_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthTokenResponse(
            access_token=data["access_token"],
            refresh_token=None,
            expires_in=data.get("expires_in"),
            token_type=data.get("token_type", "Bearer"),
        )

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _ME_URL,
                params={"fields": "id,name,email", "access_token": access_token},
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthUserInfo(
            platform_user_id=data["id"],
            handle=data.get("name", data["id"]),
            display_name=data.get("name"),
            metadata={"email": data.get("email")},
        )
