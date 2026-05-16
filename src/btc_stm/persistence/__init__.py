"""Safe local persistence for paper trading sessions."""

from btc_stm.persistence.local_store import LocalSessionStore
from btc_stm.persistence.models import PersistenceConfig, PersistedSession, SessionManifest
from btc_stm.persistence.neon_store import NeonSessionStore
from btc_stm.persistence.paths import resolve_safe_path, sanitize_session_id
from btc_stm.persistence.protocols import SessionStore
from btc_stm.persistence.serialization import (
    read_json,
    to_jsonable,
    write_json_atomic,
    write_jsonl_atomic,
)
from btc_stm.persistence.store_factory import get_store

__all__ = [
    "LocalSessionStore",
    "NeonSessionStore",
    "PersistedSession",
    "PersistenceConfig",
    "SessionManifest",
    "SessionStore",
    "get_store",
    "read_json",
    "resolve_safe_path",
    "sanitize_session_id",
    "to_jsonable",
    "write_json_atomic",
    "write_jsonl_atomic",
]
