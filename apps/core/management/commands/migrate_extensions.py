from __future__ import annotations

import json

from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extension_service import ExtensionService
from apps.core.extensions.exceptions import ExtensionNotFoundError, ExtensionStateError
from apps.core.extensions.manager import get_extension_manager
from apps.core.extensions.migrations import (
    has_django_extension_migrations,
    list_applied_django_extension_migration_files,
    list_unapplied_django_extension_migration_files,
    resolve_django_extension_app_label,
    resolve_django_extension_migration_module,
)
from apps.core.extensions.runtime_probe import inspect_extension_runtime


class Command(BaseCommand):
    help = "同步 Bias 扩展的 Django 迁移运行时摘要。数据库迁移请先执行 manage.py migrate。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("extension_id", nargs="?", help="要迁移的扩展 ID。")
        parser.add_argument("--all", action="store_true", help="同步所有已安装且提供 Django 迁移资源的扩展。")
        parser.add_argument("--dry-run", action="store_true", help="只输出将要同步的扩展迁移摘要，不修改安装状态。")
        parser.add_argument(
            "--skip-db-check",
            action="store_true",
            help="跳过 Django 迁移表校验，直接同步 Bias 扩展运行时摘要。",
        )
        parser.add_argument("--format", choices=("text", "json"), default="text")

    def handle(self, *args, **options):
        extension_id = str(options.get("extension_id") or "").strip()
        migrate_all = bool(options.get("all"))
        dry_run = bool(options.get("dry_run"))
        skip_db_check = bool(options.get("skip_db_check"))
        output_format = str(options.get("format") or "text")

        if migrate_all == bool(extension_id):
            raise CommandError("请提供一个扩展 ID，或使用 --all。")

        manager = get_extension_manager()
        manager.load(force=True)
        targets = self._resolve_targets(manager, extension_id=extension_id, migrate_all=migrate_all)

        if dry_run:
            results = [self._build_dry_run_result(extension) for extension in targets]
        else:
            results = [
                self._run_extension_migrations(
                    extension,
                    fail_fast=not migrate_all,
                    skip_db_check=skip_db_check,
                )
                for extension in targets
            ]

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
            and has_django_extension_migrations(extension)
        ]

    def _build_dry_run_result(self, extension) -> dict:
        probe = inspect_extension_runtime(extension)
        migration_plan = dict(probe.get("migration_plan") or {})
        django_pending_files = list_unapplied_django_extension_migration_files(extension)
        if not extension.runtime.installed:
            status = "error"
            message = "扩展尚未安装，无法执行迁移。"
        elif not has_django_extension_migrations(extension):
            status = "skipped"
            message = "扩展未声明 Django 迁移资源。"
        elif django_pending_files:
            status = "error"
            message = "Django 数据库迁移尚未应用，无法同步 Bias 扩展迁移摘要。请先执行 python manage.py migrate。"
        else:
            status = "ok"
            pending_count = len(migration_plan.get("pending_files") or [])
            message = f"将同步 {pending_count} 个待记录 Django 迁移摘要文件。"

        return {
            "id": extension.id,
            "name": extension.name,
            "status": status,
            "message": message,
            "django_app_label": resolve_django_extension_app_label(extension),
            "django_migration_module": resolve_django_extension_migration_module(extension),
            "django_applied_files": list_applied_django_extension_migration_files(extension),
            "django_pending_files": django_pending_files,
            "migration_plan": migration_plan,
        }

    def _run_extension_migrations(self, extension, *, fail_fast: bool, skip_db_check: bool) -> dict:
        extension_id = extension.id
        if not skip_db_check and extension.runtime.installed:
            django_pending_files = list_unapplied_django_extension_migration_files(extension)
            if django_pending_files:
                payload = {
                    "id": extension_id,
                    "name": extension.name,
                    "status": "error",
                    "message": "Django 数据库迁移尚未应用，无法同步 Bias 扩展迁移摘要。请先执行 python manage.py migrate。",
                    "code": "extension_django_migrations_unapplied",
                    "django_app_label": resolve_django_extension_app_label(extension),
                    "django_migration_module": resolve_django_extension_migration_module(extension),
                    "details": {
                        "django_pending_files": django_pending_files,
                        "django_applied_files": list_applied_django_extension_migration_files(extension),
                    },
                }
                if fail_fast:
                    raise CommandError(payload["message"])
                return payload

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
            "django_app_label": resolve_django_extension_app_label(extension),
            "django_migration_module": resolve_django_extension_migration_module(extension),
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
        self.stdout.write(self.style.SUCCESS("[OK] 扩展迁移摘要同步完成"))
