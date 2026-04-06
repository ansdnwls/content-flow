from supabase import create_client, Client

from app.config import settings

_client: Client | None = None


def get_supabase() -> Client:
    """Return a singleton Supabase client using the service-role key."""
    global _client
    if _client is None:
        _client = create_client(settings.supabase_url, settings.supabase_service_key)
    return _client


def reset_client() -> None:
    """Reset the singleton (for testing)."""
    global _client
    _client = None
