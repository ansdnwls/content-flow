"""Abstract OAuth provider and JWT-based state management."""

from __future__ import annotations

import secrets
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt

from app.config import get_settings

_STATE_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class OAuthTokenResponse:
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    token_type: str = "Bearer"
    scope: str | None = None


@dataclass(frozen=True)
class OAuthUserInfo:
    platform_user_id: str
    handle: str
    display_name: str | None = None
    metadata: dict | None = None


class OAuthProvider(ABC):
    """Base class for platform-specific OAuth 2.0 implementations."""

    platform: str

    @abstractmethod
    def get_authorize_url(self, state: str, scopes: list[str] | None = None) -> str:
        """Return the authorization URL the user should be redirected to."""

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokenResponse:
        """Exchange an authorization code for tokens."""

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> OAuthTokenResponse:
        """Use a refresh token to obtain a new access token."""

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch the authenticated user's profile from the platform."""

    def build_redirect_uri(self) -> str:
        """Build the OAuth callback URL from config."""
        base = get_settings().oauth_redirect_base_url.rstrip("/")
        return f"{base}/api/v1/accounts/callback/{self.platform}"


def _get_state_secret() -> str:
    secret = get_settings().oauth_state_secret
    if not secret:
        raise RuntimeError("OAUTH_STATE_SECRET is not configured")
    return secret


def create_oauth_state(owner_id: str, platform: str, extra: dict | None = None) -> str:
    """Create a signed JWT encoding the OAuth state (sub, platform, nonce, exp)."""
    now = datetime.now(UTC)
    payload: dict = {
        "sub": owner_id,
        "platform": platform,
        "nonce": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + _STATE_TTL,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, _get_state_secret(), algorithm="HS256")


def verify_oauth_state(state: str) -> dict:
    """Verify and decode an OAuth state JWT. Raises jwt.InvalidTokenError on failure."""
    return jwt.decode(state, _get_state_secret(), algorithms=["HS256"])
