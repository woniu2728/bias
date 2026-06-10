from __future__ import annotations

import json
from pathlib import Path


def discover_extension_django_apps(base_dir: str | Path) -> list[str]:
    return [item["app_config"] for item in _discover_extension_django_app_records(base_dir)]


def discover_extension_django_migration_modules(base_dir: str | Path) -> dict[str, str]:
    return {
        item["app_label"]: item["migration_module"]
        for item in _discover_extension_django_app_records(base_dir)
    }


def _discover_extension_django_app_records(base_dir: str | Path) -> list[dict[str, str]]:
    extensions_dir = Path(base_dir) / "extensions"
    if not extensions_dir.exists():
        return []

    records: list[dict[str, str]] = []
    for manifest_path in sorted(extensions_dir.glob("*/extension.json")):
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        extension_id = str(payload.get("id") or manifest_path.parent.name).strip()
        app_config = str(payload.get("django_app_config") or "").strip()
        expected_prefix = f"extensions.{extension_id.replace('-', '_')}.backend.apps."
        if app_config and app_config.startswith(expected_prefix):
            app_label = normalize_extension_django_app_label(
                extension_id,
                payload.get("django_app_label"),
            )
            migration_module = f"extensions.{extension_id.replace('-', '_')}.backend.django_migrations"
            records.append({
                "app_config": app_config,
                "app_label": app_label,
                "migration_module": migration_module,
            })

    return records


def normalize_extension_django_app_label(extension_id: str, app_label: str | None = None) -> str:
    normalized = str(app_label or "").strip()
    if normalized:
        return normalized
    return str(extension_id or "").replace("-", "_").strip()
