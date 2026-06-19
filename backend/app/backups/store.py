from __future__ import annotations

from app.core.models import BackupRecord


class BackupStore:
    def __init__(self, backups: list[BackupRecord] | None = None) -> None:
        self._backups: dict[str, BackupRecord] = {backup.backup_id: backup for backup in backups or []}

    def create(self, backup: BackupRecord) -> BackupRecord:
        self._backups[backup.backup_id] = backup
        return backup

    def get(self, backup_id: str) -> BackupRecord:
        return self._backups[backup_id]

    def list(self) -> list[BackupRecord]:
        return list(self._backups.values())
