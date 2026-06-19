from __future__ import annotations

from app.core.models import MemoryRecord


class MemoryStore:
    def __init__(self, records: list[MemoryRecord] | None = None) -> None:
        self._records: list[MemoryRecord] = list(records or [])

    def write(self, record: MemoryRecord) -> MemoryRecord:
        self._records.append(record)
        return record

    def list(self) -> tuple[MemoryRecord, ...]:
        return tuple(self._records)
