from supabase import Client, create_client
from app.config import ConfigurationError, get_settings

_client: Client | None = None


def get_supabase_client() -> Client:
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise ConfigurationError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be configured.")
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client
