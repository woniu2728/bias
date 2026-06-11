from __future__ import annotations

from pathlib import Path
from typing import Any

from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.recorder import MigrationRecorder


def has_django_extension_migrations(extension_definition) -> bool:
    return bool(resolve_django_extension_migration_dir(extension_definition))


def resolve_django_extension_app_label(extension_definition) -> str:
    manifest = extension_definition.manifest
    return str(manifest.django_app_label or extension_definition.id.replace("-", "_")).strip()


def resolve_django_extension_migration_module(extension_definition) -> str:
    if not str(extension_definition.manifest.django_app_config or "").strip():
        return ""
    return f"extensions.{extension_definition.id.replace('-', '_')}.backend.django_migrations"


def resolve_django_extension_migration_dir(extension_definition) -> Path | None:
    root_path = Path(str(extension_definition.manifest.path or "").strip())
    migration_dir = root_path / "backend" / "django_migrations"
    if not migration_dir.exists():
        return None
    return migration_dir


def list_django_extension_migration_files(extension_definition) -> list[str]:
    migration_dir = resolve_django_extension_migration_dir(extension_definition)
    if migration_dir is None:
        return []
    return sorted(
        item.name
        for item in migration_dir.glob("*.py")
        if item.name != "__init__.py"
    )


def list_applied_django_extension_migration_files(extension_definition, *, database: str = DEFAULT_DB_ALIAS) -> list[str]:
    app_label = resolve_django_extension_app_label(extension_definition)
    if not app_label:
        return []
    connection = connections[database]
    recorder = MigrationRecorder(connection)
    applied = recorder.applied_migrations()
    return sorted(
        f"{migration_name}.py"
        for migration_app_label, migration_name in applied
        if migration_app_label == app_label
    )


def list_unapplied_django_extension_migration_files(extension_definition, *, database: str = DEFAULT_DB_ALIAS) -> list[str]:
    declared_files = list_django_extension_migration_files(extension_definition)
    applied_files = set(list_applied_django_extension_migration_files(extension_definition, database=database))
    return [item for item in declared_files if item not in applied_files]


def run_extension_migrations(
    extension_definition,
    *,
    applied_steps: list[str] | None = None,
    applied_migration_files: list[str] | None = None,
    direction: str = "up",
) -> dict[str, Any]:
    migration_module = resolve_django_extension_migration_module(extension_definition)
    migration_files = list_django_extension_migration_files(extension_definition)
    app_label = resolve_django_extension_app_label(extension_definition)

    if not migration_module:
        return {
            "status": "skipped",
            "status_label": "已跳过",
            "message": "当前扩展未声明 Django AppConfig。",
            "details": {
                "django_app_label": app_label,
                "django_migration_module": "",
                "applied_steps": [],
                "migration_files": [],
                "skipped_migration_files": [],
            },
        }

    if not migration_files:
        return {
            "status": "skipped",
            "status_label": "已跳过",
            "message": "当前扩展没有 Django 迁移文件。",
            "details": {
                "django_app_label": app_label,
                "django_migration_module": migration_module,
                "applied_steps": [],
                "migration_files": [],
                "skipped_migration_files": [],
            },
        }

    already_applied_files = set(applied_migration_files or [])
    pending_files = [item for item in migration_files if item not in already_applied_files]
    skipped_files = [item for item in migration_files if item in already_applied_files]
    normalized_direction = "down" if str(direction or "").strip().lower() in {"down", "rollback", "reset"} else "up"
    applied = list(applied_steps or [])
    if normalized_direction == "up":
        applied.extend(Path(item).stem for item in pending_files)

    message = (
        f"{extension_definition.name} 的 Django 扩展迁移摘要已同步。"
        if pending_files
        else f"{extension_definition.name} 的 Django 扩展迁移已是最新摘要。"
    )
    return {
        "status": "ok",
        "status_label": "已同步",
        "message": message,
        "details": {
            "django_app_label": app_label,
            "django_migration_module": migration_module,
            "direction": normalized_direction,
            "applied_steps": applied,
            "migration_files": pending_files,
            "skipped_migration_files": skipped_files,
            "declared_migration_files": migration_files,
        },
    }
