"""X (Twitter) OAuth 2.0 provider with PKCE (S256)."""

from __future__ import annotations

import base64
import hashlib
import secrets
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.oauth.provider import OAuthProvider, OAuthTokenResponse, OAuthUserInfo

_AUTHORIZE_URL = "https://twitter.com/i/oauth2/authorize"
_TOKEN_URL = "https://api.twitter.com/2/oauth2/token"
_USERINFO_URL = "https://api.twitter.com/2/users/me"


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for S256 PKCE."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


class XOAuthProvider(OAuthProvider):
    platform = "x_twitter"

    def get_authorize_url(self, state: str, scopes: list[str] | None = None) -> str:
        settings = get_settings()
        scope = " ".join(scopes or ["tweet.read", "tweet.write", "users.read", "offline.access"])
        params = {
            "client_id": settings.x_client_id,
            "redirect_uri": self.build_redirect_uri(),
            "response_type": "code",
            "scope": scope,
            "state": state,
            "code_challenge_method": "S256",
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}"

    def get_authorize_url_with_pkce(
        self, state: str, scopes: list[str] | None = None
    ) -> tuple[str, str]:
        """Return (authorize_url, code_verifier). The verifier must be stored in state."""
        verifier, challenge = generate_pkce_pair()
        settings = get_settings()
        scope = " ".join(scopes or ["tweet.read", "tweet.write", "users.read", "offline.access"])
        params = {
            "client_id": settings.x_client_id,
            "redirect_uri": self.build_redirect_uri(),
            "response_type": "code",
            "scope": scope,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        return f"{_AUTHORIZE_URL}?{urlencode(params)}", verifier

    async def exchange_code(
        self, code: str, redirect_uri: str, code_verifier: str | None = None
    ) -> OAuthTokenResponse:
        settings = get_settings()
        data = {
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "client_id": settings.x_client_id,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data=data,
                auth=(settings.x_client_id or "", settings.x_client_secret or ""),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            body = resp.json()

        return OAuthTokenResponse(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("expires_in"),
            token_type=body.get("token_type", "Bearer"),
            scope=body.get("scope"),
        )

    async def refresh_access_token(self, refresh_token: str) -> OAuthTokenResponse:
        settings = get_settings()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                    "client_id": settings.x_client_id,
                },
                auth=(settings.x_client_id or "", settings.x_client_secret or ""),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            body = resp.json()

        return OAuthTokenResponse(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token"),
            expires_in=body.get("expires_in"),
            token_type=body.get("token_type", "Bearer"),
            scope=body.get("scope"),
        )

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _USERINFO_URL,
                params={"user.fields": "id,name,username,profile_image_url"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})

        return OAuthUserInfo(
            platform_user_id=data.get("id", ""),
            handle=f"@{data.get('username', '')}",
            display_name=data.get("name"),
            metadata={"profile_image_url": data.get("profile_image_url")},
        )
