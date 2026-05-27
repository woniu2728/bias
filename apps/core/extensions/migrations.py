from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


MIGRATION_FUNCTION_NAMES = (
    "apply",
    "run",
    "upgrade",
)


def run_extension_migrations(
    extension_definition,
    *,
    applied_steps: list[str] | None = None,
    applied_migration_files: list[str] | None = None,
) -> dict[str, Any]:
    root_path = Path(str(extension_definition.manifest.path or "").strip())
    migration_dir = root_path / "backend" / "migrations"
    namespace = str(extension_definition.manifest.migration_namespace or "").strip()

    if not namespace:
        return {
            "status": "skipped",
            "status_label": "已跳过",
            "message": "当前扩展未声明迁移命名空间。",
            "details": {
                "migration_namespace": "",
                "applied_steps": [],
                "migration_files": [],
            },
        }

    if not migration_dir.exists():
        return {
            "status": "skipped",
            "status_label": "已跳过",
            "message": "已声明迁移命名空间，但迁移目录不存在。",
            "details": {
                "migration_namespace": namespace,
                "applied_steps": [],
                "migration_files": [],
            },
        }

    executed_steps: list[str] = list(applied_steps or [])
    migration_files: list[str] = []
    skipped_files: list[str] = []
    already_applied_files = set(applied_migration_files or [])

    for file_path in sorted(migration_dir.glob("*.py")):
        if file_path.name == "__init__.py":
            continue

        step_key = file_path.stem
        if file_path.name in already_applied_files:
            skipped_files.append(file_path.name)
            continue
        migration_files.append(file_path.name)
        module = _load_migration_module(extension_definition.id, file_path)
        runner = _resolve_migration_runner(module)
        if runner is None:
            continue

        result = runner()
        executed_steps.append(step_key)
        if isinstance(result, str) and result.strip():
            executed_steps.append(result.strip())

    message = (
        f"{extension_definition.name} 的扩展迁移已执行。"
        if migration_files
        else f"{extension_definition.name} 当前没有可执行的扩展迁移文件。"
    )
    return {
        "status": "ok",
        "status_label": "已执行",
        "message": message,
        "details": {
            "migration_namespace": namespace,
            "applied_steps": executed_steps,
            "migration_files": migration_files,
            "skipped_migration_files": skipped_files,
        },
    }


def _load_migration_module(extension_id: str, file_path: Path):
    module_name = f"bias_extension_migration_{extension_id.replace('-', '_')}_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载扩展迁移文件: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_migration_runner(module):
    for name in MIGRATION_FUNCTION_NAMES:
        runner = getattr(module, name, None)
        if callable(runner):
            return runner
    return None
