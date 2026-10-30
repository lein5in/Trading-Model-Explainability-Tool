import copy
import threading
import uuid
from datetime import datetime, timezone
from typing import Protocol

ANALYSES_TABLE = "analyses"
OHLCV_CACHE_TABLE = "ohlcv_cache"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(str(value))
    except ValueError:
        return False
    return True


class RepositoryError(Exception):
    pass


class AnalysisRepository(Protocol):
    def create_analysis(self, row: dict) -> dict: ...

    def get_analysis(self, analysis_id: str) -> dict | None: ...

    def update_analysis(self, analysis_id: str, fields: dict) -> dict | None: ...

    def count_analyses_since(self, since: datetime) -> int: ...

    def list_analyses_with_status(self, statuses: list[str], created_before: datetime) -> list[dict]: ...

    def get_cache(self, key: str) -> dict | None: ...

    def set_cache(self, key: str, payload) -> None: ...

    def ping(self) -> bool: ...


class InMemoryRepository:
    def __init__(self):
        self._analyses: dict[str, dict] = {}
        self._cache: dict[str, dict] = {}
        self._lock = threading.Lock()

    def create_analysis(self, row: dict) -> dict:
        with self._lock:
            stored = copy.deepcopy(row)
            stored.setdefault("id", str(uuid.uuid4()))
            stored.setdefault("created_at", utc_now().isoformat())
            self._analyses[stored["id"]] = stored
            return copy.deepcopy(stored)

    def get_analysis(self, analysis_id: str) -> dict | None:
        with self._lock:
            row = self._analyses.get(str(analysis_id))
            return copy.deepcopy(row) if row is not None else None

    def update_analysis(self, analysis_id: str, fields: dict) -> dict | None:
        with self._lock:
            row = self._analyses.get(str(analysis_id))
            if row is None:
                return None
            row.update(copy.deepcopy(fields))
            return copy.deepcopy(row)

    def count_analyses_since(self, since: datetime) -> int:
        with self._lock:
            return sum(1 for row in self._analyses.values() if parse_timestamp(row["created_at"]) >= since)

    def list_analyses_with_status(self, statuses: list[str], created_before: datetime) -> list[dict]:
        with self._lock:
            return [
                copy.deepcopy(row)
                for row in self._analyses.values()
                if row.get("status") in statuses and parse_timestamp(row["created_at"]) < created_before
            ]

    def get_cache(self, key: str) -> dict | None:
        with self._lock:
            entry = self._cache.get(key)
            return copy.deepcopy(entry) if entry is not None else None

    def set_cache(self, key: str, payload) -> None:
        with self._lock:
            self._cache[key] = {"key": key, "payload": copy.deepcopy(payload), "fetched_at": utc_now().isoformat()}

    def ping(self) -> bool:
        return True


class SupabaseRepository:
    def __init__(self, client_factory=None):
        if client_factory is None:
            from app.db.client import get_supabase_client

            client_factory = get_supabase_client
        self._client_factory = client_factory

    def _table(self, name: str):
        return self._client_factory().table(name)

    def create_analysis(self, row: dict) -> dict:
        response = self._table(ANALYSES_TABLE).insert(row).execute()
        if not response.data:
            raise RepositoryError("Failed to create the analysis row.")
        return response.data[0]

    def get_analysis(self, analysis_id: str) -> dict | None:
        if not is_valid_uuid(analysis_id):
            return None
        response = self._table(ANALYSES_TABLE).select("*").eq("id", str(analysis_id)).limit(1).execute()
        return response.data[0] if response.data else None

    def update_analysis(self, analysis_id: str, fields: dict) -> dict | None:
        response = self._table(ANALYSES_TABLE).update(fields).eq("id", str(analysis_id)).execute()
        return response.data[0] if response.data else None

    def count_analyses_since(self, since: datetime) -> int:
        response = (
            self._table(ANALYSES_TABLE)
            .select("id", count="exact")
            .gte("created_at", since.isoformat())
            .execute()
        )
        return int(response.count or 0)

    def list_analyses_with_status(self, statuses: list[str], created_before: datetime) -> list[dict]:
        response = (
            self._table(ANALYSES_TABLE)
            .select("id,status,stage,created_at,result")
            .in_("status", statuses)
            .lt("created_at", created_before.isoformat())
            .execute()
        )
        return list(response.data or [])

    def get_cache(self, key: str) -> dict | None:
        response = self._table(OHLCV_CACHE_TABLE).select("*").eq("key", key).limit(1).execute()
        return response.data[0] if response.data else None

    def set_cache(self, key: str, payload) -> None:
        self._table(OHLCV_CACHE_TABLE).upsert(
            {"key": key, "payload": payload, "fetched_at": utc_now().isoformat()}
        ).execute()

    def ping(self) -> bool:
        self._table(ANALYSES_TABLE).select("id").limit(1).execute()
        return True
