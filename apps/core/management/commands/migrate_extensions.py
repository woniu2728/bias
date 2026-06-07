from __future__ import annotations

import json

from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extension_service import ExtensionService
from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.manager import get_extension_manager
from apps.core.extensions.runtime_probe import inspect_extension_runtime


class Command(BaseCommand):
    help = "执行 Bias 扩展声明的 lifecycle 迁移。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("extension_id", nargs="?", help="要迁移的扩展 ID。")
        parser.add_argument("--all", action="store_true", help="迁移所有已安装且声明迁移命名空间的扩展。")
        parser.add_argument("--dry-run", action="store_true", help="只输出将要执行的扩展迁移，不修改安装状态。")
        parser.add_argument("--format", choices=("text", "json"), default="text")

    def handle(self, *args, **options):
        extension_id = str(options.get("extension_id") or "").strip()
        migrate_all = bool(options.get("all"))
        dry_run = bool(options.get("dry_run"))
        output_format = str(options.get("format") or "text")

        if migrate_all == bool(extension_id):
            raise CommandError("请提供一个扩展 ID，或使用 --all。")

        manager = get_extension_manager()
        manager.load(force=True)
        targets = self._resolve_targets(manager, extension_id=extension_id, migrate_all=migrate_all)

        if dry_run:
            results = [self._build_dry_run_result(extension) for extension in targets]
        else:
            results = [self._run_extension_migrations(extension.id, fail_fast=not migrate_all) for extension in targets]

        payload = {
            "dry_run": dry_run,
            "summary": {
                "target_count": len(results),
                "executed_count": sum(1 for item in results if item["status"] == "ok"),
                "skipped_count": sum(1 for item in results if item["status"] == "skipped"),
                "error_count": sum(1 for item in results if item["status"] == "error"),
            },
            "extensions": results,
        }
        self._write_payload(payload, output_format=output_format)

        if payload["summary"]["error_count"]:
            raise CommandError(f"扩展迁移失败，共 {payload['summary']['error_count']} 个错误")

    def _resolve_targets(self, manager, *, extension_id: str, migrate_all: bool):
        if extension_id:
            try:
                return [manager.get_extension(extension_id)]
            except ExtensionNotFoundError as exc:
                raise CommandError(str(exc)) from exc

        return [
            extension
            for extension in manager.get_extensions()
            if extension.runtime.installed
            and str(extension.manifest.migration_namespace or "").strip()
        ]

    def _build_dry_run_result(self, extension) -> dict:
        probe = inspect_extension_runtime(extension)
        migration_plan = dict(probe.get("migration_plan") or {})
        if not extension.runtime.installed:
            status = "error"
            message = "扩展尚未安装，无法执行迁移。"
        elif not str(extension.manifest.migration_namespace or "").strip():
            status = "skipped"
            message = "扩展未声明迁移命名空间。"
        else:
            status = "ok"
            pending_count = len(migration_plan.get("pending_files") or [])
            message = f"将检查 {pending_count} 个待执行迁移文件。"

        return {
            "id": extension.id,
            "name": extension.name,
            "status": status,
            "message": message,
            "migration_namespace": str(extension.manifest.migration_namespace or ""),
            "migration_plan": migration_plan,
        }

    def _run_extension_migrations(self, extension_id: str, *, fail_fast: bool) -> dict:
        try:
            extension = ExtensionService.run_extension_migrations(extension_id)
        except ExtensionStateError as exc:
            if fail_fast:
                raise CommandError(str(exc)) from exc
            return {
                "id": extension_id,
                "name": extension_id,
                "status": "error",
                "message": str(exc),
                "code": exc.code,
                "details": exc.details,
            }

        hook = dict(extension.runtime.backend_hooks or {}).get("run_migrations") or {}
        return {
            "id": extension.id,
            "name": extension.name,
            "status": str(hook.get("status") or "ok"),
            "message": str(hook.get("message") or ""),
            "migration_namespace": str(extension.manifest.migration_namespace or ""),
            "details": dict(hook.get("details") or {}),
        }

    def _write_payload(self, payload: dict, *, output_format: str) -> None:
        if output_format == "json":
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        self.stdout.write(f"目标扩展: {payload['summary']['target_count']}")
        for item in payload["extensions"]:
            self.stdout.write(f"[{item['status']}] {item['id']} - {item['message']}")
        if payload["summary"]["error_count"]:
            return
        self.stdout.write(self.style.SUCCESS("[OK] 扩展迁移执行完成"))
