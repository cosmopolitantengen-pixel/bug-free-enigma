from __future__ import annotations

from app.core.models import DomainEvent


class EventBus:
    def __init__(self, events: list[DomainEvent] | None = None) -> None:
        self._events: dict[str, DomainEvent] = {event.event_id: event for event in events or []}

    def publish(self, event: DomainEvent) -> DomainEvent:
        self._events[event.event_id] = event
        return event

    def list(
        self,
        event_type: str | None = None,
        source_type: str | None = None,
        task_id: str | None = None,
    ) -> list[DomainEvent]:
        events = list(self._events.values())
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        if source_type is not None:
            events = [event for event in events if event.source_type == source_type]
        if task_id is not None:
            events = [event for event in events if event.task_id == task_id]
        return events
