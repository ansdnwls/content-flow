"""Supabase client singleton using the service-role key."""

from __future__ import annotations

from supabase import Client, create_client

from app.config import get_settings

_client: Client | None = None


def get_supabase() -> Client:
    """Return a singleton Supabase client."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


def reset_client() -> None:
    """Reset the singleton (for testing)."""
    global _client
    _client = None
