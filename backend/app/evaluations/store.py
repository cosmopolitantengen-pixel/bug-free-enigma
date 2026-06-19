from __future__ import annotations

from app.core.models import EvaluationRecord


class EvaluationStore:
    def __init__(self, records: list[EvaluationRecord] | None = None) -> None:
        self._records: list[EvaluationRecord] = list(records or [])

    def write(self, record: EvaluationRecord) -> EvaluationRecord:
        self._records.append(record)
        return record

    def list(self) -> tuple[EvaluationRecord, ...]:
        return tuple(self._records)
