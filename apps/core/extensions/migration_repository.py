from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.core.models import ExtensionInstallation


@dataclass(frozen=True)
class ExtensionMigrationRecord:
    extension_id: str
    execution: dict[str, Any]
    applied_steps: tuple[str, ...]
    applied_files: tuple[str, ...]


class ExtensionMigrationRepository:
    """Stores extension migration state in ExtensionInstallation.meta.

    This keeps the persistence contract centralized behind a repository
    without introducing a new table while extension storage is still settling.
    """

    def get_record(self, extension_id: str) -> ExtensionMigrationRecord:
        normalized = str(extension_id or "").strip()
        installation = ExtensionInstallation.objects.filter(extension_id=normalized).first()
        meta = dict((installation.meta or {}) if installation is not None else {})
        execution = dict(meta.get("migration_execution") or {})
        details = dict(execution.get("details") or {})
        return ExtensionMigrationRecord(
            extension_id=normalized,
            execution=execution,
            applied_steps=tuple(details.get("applied_steps") or ()),
            applied_files=tuple(meta.get("applied_migration_files") or ()),
        )

    def build_execution_meta(
        self,
        extension_id: str,
        result: dict[str, Any] | None,
        *,
        direction: str = "up",
    ) -> dict[str, Any]:
        payload = dict(result or {})
        record = self.get_record(extension_id)
        migration_files = list((payload.get("details") or {}).get("migration_files") or [])
        applied_files = self._resolve_applied_files(record.applied_files, migration_files, direction=direction)
        return {
            "migration_execution": payload,
            "applied_migration_files": applied_files,
        }

    @staticmethod
    def _resolve_applied_files(
        current_files: tuple[str, ...],
        migration_files: list[str],
        *,
        direction: str,
    ) -> list[str]:
        normalized_direction = str(direction or "up").strip().lower()
        if normalized_direction in {"down", "rollback", "reset"}:
            if not migration_files:
                return []
            rollback_set = set(migration_files)
            return [item for item in current_files if item not in rollback_set]
        return list(dict.fromkeys([*current_files, *migration_files]))
