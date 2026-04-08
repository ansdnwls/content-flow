"""OAuth provider registry — maps platform slugs to OAuthProvider instances."""

from __future__ import annotations

from app.oauth.provider import OAuthProvider
from app.oauth.providers.google import GoogleOAuthProvider
from app.oauth.providers.meta import MetaOAuthProvider
from app.oauth.providers.tiktok import TikTokOAuthProvider
from app.oauth.providers.x import XOAuthProvider

_PROVIDERS: dict[str, OAuthProvider] = {
    "youtube": GoogleOAuthProvider(platform="youtube"),
    "instagram": MetaOAuthProvider(platform="instagram"),
    "facebook": MetaOAuthProvider(platform="facebook"),
    "threads": MetaOAuthProvider(platform="threads"),
    "tiktok": TikTokOAuthProvider(),
    "x_twitter": XOAuthProvider(),
}

SUPPORTED_PLATFORMS: tuple[str, ...] = tuple(_PROVIDERS.keys())


def get_oauth_provider(platform: str) -> OAuthProvider:
    """Return the OAuth provider for *platform* or raise ValueError."""
    provider = _PROVIDERS.get(platform)
    if provider is None:
        raise ValueError(
            f"Unsupported platform '{platform}'. Must be one of: {', '.join(SUPPORTED_PLATFORMS)}"
        )
    return provider
