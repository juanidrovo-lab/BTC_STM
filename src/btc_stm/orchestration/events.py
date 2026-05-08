"""Auditable event helpers for paper orchestration."""

from __future__ import annotations

from datetime import datetime

from btc_stm.orchestration.models import OrchestratorEvent, OrchestratorEventType


def make_event(
    event_type: OrchestratorEventType,
    *,
    timestamp: datetime,
    message: str,
    metadata: dict[str, str] | None = None,
) -> OrchestratorEvent:
    return OrchestratorEvent(
        event_type=event_type,
        timestamp=timestamp,
        message=message,
        metadata=metadata or {},
    )
