"""Protocol definitions for session store backends."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from btc_stm.orchestration.models import PaperTradingSessionResult
from btc_stm.persistence.models import PersistedSession, SessionManifest


@runtime_checkable
class SessionStore(Protocol):
    """Protocol that all session store implementations must satisfy.

    Both ``LocalSessionStore`` and ``NeonSessionStore`` implement this
    interface so callers can treat them interchangeably.  Note that
    ``NeonSessionStore`` exposes *async* methods; callers that need to
    support both backends must use ``await`` unconditionally and wrap
    ``LocalSessionStore`` calls in ``asyncio.to_thread`` when needed.
    """

    def save_session(
        self,
        session_id: str,
        result: PaperTradingSessionResult,
    ) -> SessionManifest:
        """Persist a completed trading session and return its manifest."""
        ...

    def load_manifest(self, session_id: str) -> SessionManifest:
        """Return the ``SessionManifest`` for a previously stored session."""
        ...

    def load_session_summary(self, session_id: str) -> PersistedSession:
        """Return a ``PersistedSession`` containing manifest, config, and report."""
        ...

    def list_sessions(self) -> list[SessionManifest]:
        """Return manifests for all stored sessions, ordered by creation time."""
        ...
