"""Naver Commerce API OAuth 2.0 provider with HMAC-SHA256 signing."""
from __future__ import annotations

import hashlib
import hmac
import time
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.oauth.provider import OAuthProvider, OAuthTokenResponse, OAuthUserInfo

_AUTH_URL = "https://accounts.commerce.naver.com/oauth/authorize"
_TOKEN_URL = "https://accounts.commerce.naver.com/oauth/token"
_SELLER_URL = "https://api.commerce.naver.com/external/v1/seller/shop"

_DEFAULT_SCOPES = [
    "product",
    "product.image",
]


def generate_signature(client_id: str, client_secret: str, timestamp: int) -> str:
    """Generate HMAC-SHA256 signature for Naver Commerce API.

    Signature = HMAC-SHA256(client_secret, f"{client_id}_{timestamp}")
    """
    base = f"{client_id}_{timestamp}"
    return hmac.new(
        client_secret.encode(),
        base.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_signature(
    client_id: str,
    client_secret: str,
    timestamp: int,
    signature: str,
) -> bool:
    """Verify an HMAC-SHA256 signature."""
    expected = generate_signature(client_id, client_secret, timestamp)
    return hmac.compare_digest(expected, signature)


def _build_auth_headers(access_token: str) -> dict[str, str]:
    """Build authorization headers with Bearer token and timestamp."""
    settings = get_settings()
    ts = int(time.time() * 1000)
    client_id = settings.naver_commerce_client_id or ""
    client_secret = settings.naver_commerce_client_secret or ""
    sig = generate_signature(client_id, client_secret, ts)
    return {
        "Authorization": f"Bearer {access_token}",
        "X-Naver-Client-Id": client_id,
        "X-Naver-Timestamp": str(ts),
        "X-Naver-Signature": sig,
    }


class NaverCommerceOAuthProvider(OAuthProvider):
    """OAuth 2.0 provider for Naver Commerce API (SmartStore)."""

    platform = "naver_commerce"

    def get_authorize_url(
        self,
        state: str,
        scopes: list[str] | None = None,
    ) -> str:
        """Build Naver Commerce OAuth authorization URL."""
        settings = get_settings()
        params = {
            "response_type": "code",
            "client_id": settings.naver_commerce_client_id or "",
            "redirect_uri": self.build_redirect_uri(),
            "state": state,
            "scope": " ".join(scopes or _DEFAULT_SCOPES),
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> OAuthTokenResponse:
        """Exchange authorization code for access + refresh tokens."""
        settings = get_settings()
        ts = int(time.time() * 1000)
        client_id = settings.naver_commerce_client_id or ""
        client_secret = settings.naver_commerce_client_secret or ""
        sig = generate_signature(client_id, client_secret, ts)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "timestamp": str(ts),
                    "signature": sig,
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

    async def refresh_access_token(
        self,
        refresh_token: str,
    ) -> OAuthTokenResponse:
        """Refresh an expired access token."""
        settings = get_settings()
        ts = int(time.time() * 1000)
        client_id = settings.naver_commerce_client_id or ""
        client_secret = settings.naver_commerce_client_secret or ""
        sig = generate_signature(client_id, client_secret, ts)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                _TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "timestamp": str(ts),
                    "signature": sig,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthTokenResponse(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_in=data.get("expires_in"),
            token_type=data.get("token_type", "Bearer"),
            scope=data.get("scope"),
        )

    async def get_user_info(
        self,
        access_token: str,
    ) -> OAuthUserInfo:
        """Fetch seller profile from Naver Commerce API."""
        headers = _build_auth_headers(access_token)
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_SELLER_URL, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        seller = data.get("content", data)
        bizmember_id = str(seller.get("bizMemberId", ""))
        return OAuthUserInfo(
            platform_user_id=str(seller.get("channelNo", "")),
            handle=seller.get("channelName", ""),
            display_name=seller.get("representativeName"),
            metadata={
                "channel_id": seller.get("channelId"),
                "channel_name": seller.get("channelName"),
                "business_type": seller.get("businessType"),
                "bizmember_id": bizmember_id,
            },
        )
