from __future__ import annotations

from app.core.models import AuditEvent


class AuditLog:
    def __init__(self, events: list[AuditEvent] | None = None) -> None:
        self._events: list[AuditEvent] = list(events or [])

    def append(self, event: AuditEvent) -> AuditEvent:
        self._events.append(event)
        return event

    def list(self) -> tuple[AuditEvent, ...]:
        return tuple(self._events)

    def delete(self, event_id: str) -> None:
        raise PermissionError("audit log is append-only")

    def clear(self) -> None:
        raise PermissionError("audit log is append-only")
