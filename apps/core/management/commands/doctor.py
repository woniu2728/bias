from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.cache import cache
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor

from apps.core.extensions.frontend_compiler import (
    get_frontend_dist_root,
    get_frontend_vite_manifest_path,
    inspect_extension_frontend_output_manifest,
)
from apps.core.extensions.manager import get_extension_manager
from apps.core.runtime_state import get_runtime_status


class Command(BaseCommand):
    help = "检查 Bias 安装、升级和部署状态。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--format", choices=("text", "json"), default="text")
        parser.add_argument("--skip-cache", action="store_true", help="跳过缓存读写检查")
        parser.add_argument("--skip-frontend", action="store_true", help="跳过前端 dist 和扩展前端 manifest 检查")
        parser.add_argument("--skip-extensions", action="store_true", help="跳过扩展包状态检查")

    def handle(self, *args, **options):
        payload = self._build_payload(
            skip_cache=bool(options.get("skip_cache")),
            skip_frontend=bool(options.get("skip_frontend")),
            skip_extensions=bool(options.get("skip_extensions")),
        )

        if options.get("format") == "json":
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            self._write_text(payload)

        if not payload["ok"]:
            raise CommandError(f"doctor 检查失败，共 {payload['summary']['error_count']} 个错误")

    def _build_payload(self, *, skip_cache: bool, skip_frontend: bool, skip_extensions: bool) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        checks.append(self._check_runtime_status())
        checks.append(self._check_database())
        checks.append(self._check_migrations())
        if not skip_extensions:
            checks.append(self._check_extensions())
        if not skip_frontend:
            checks.extend(self._check_frontend())
        if not skip_cache:
            checks.append(self._check_cache())

        errors = [item for item in checks if item["status"] == "error"]
        warnings = [item for item in checks if item["status"] == "warning"]
        return {
            "ok": not errors,
            "summary": {
                "check_count": len(checks),
                "error_count": len(errors),
                "warning_count": len(warnings),
            },
            "checks": checks,
        }

    def _check_runtime_status(self) -> dict[str, Any]:
        status = get_runtime_status()
        if status.state == "ready":
            return _check("runtime_status", "ok", status.message, {
                "current_version": status.current_version,
                "installed_version": status.installed_version,
                "state": status.state,
            })
        return _check("runtime_status", "error", status.message, {
            "current_version": status.current_version,
            "installed_version": status.installed_version,
            "state": status.state,
        })

    def _check_database(self) -> dict[str, Any]:
        try:
            connection = connections[DEFAULT_DB_ALIAS]
            connection.ensure_connection()
        except Exception as exc:
            return _check("database", "error", f"数据库连接失败: {exc}")

        return _check("database", "ok", "数据库连接正常。", {
            "vendor": connection.vendor,
            "alias": DEFAULT_DB_ALIAS,
        })

    def _check_migrations(self) -> dict[str, Any]:
        try:
            connection = connections[DEFAULT_DB_ALIAS]
            executor = MigrationExecutor(connection)
            targets = executor.loader.graph.leaf_nodes()
            plan = executor.migration_plan(targets)
        except Exception as exc:
            return _check("migrations", "error", f"迁移状态检查失败: {exc}")

        pending = [
            f"{migration.app_label}.{migration.name}"
            for migration, backwards in plan
            if not backwards
        ]
        if pending:
            return _check("migrations", "error", f"存在 {len(pending)} 个待执行迁移。", {
                "pending": pending,
            })
        return _check("migrations", "ok", "数据库迁移已是最新。")

    def _check_extensions(self) -> dict[str, Any]:
        try:
            payload = get_extension_manager().inspect_extension_packages(force=True)
        except Exception as exc:
            return _check("extensions", "error", f"扩展状态检查失败: {exc}")

        summary = dict(payload.get("summary") or {})
        installed_count = int(summary.get("installed_count") or 0)
        installation_record_count = int(summary.get("installation_record_count") or 0)
        record_drift = installed_count != installation_record_count
        problems = {
            "missing": list(payload.get("missing") or []),
            "version_drift": list(payload.get("version_drift") or []),
            "source_drift": list(payload.get("source_drift") or []),
            "unmanaged_discovered": list(payload.get("unmanaged_discovered") or []),
            "stale_lock_ids": list((payload.get("lock") or {}).get("stale_ids") or []),
            "installation_record_drift": {
                "installed_count": installed_count,
                "installation_record_count": installation_record_count,
            } if record_drift else {},
        }
        has_error = bool(problems["missing"] or problems["version_drift"] or problems["source_drift"])
        has_warning = bool(problems["unmanaged_discovered"] or problems["stale_lock_ids"] or record_drift)
        if has_error:
            return _check("extensions", "error", "扩展包状态存在缺失或版本漂移。", {
                "summary": summary,
                **problems,
            })
        if has_warning:
            return _check("extensions", "warning", "扩展包状态存在可同步项。", {
                "summary": summary,
                **problems,
            })
        return _check("extensions", "ok", "扩展包状态正常。", {"summary": summary})

    def _check_frontend(self) -> list[dict[str, Any]]:
        dist_root = get_frontend_dist_root()
        index_path = dist_root / "index.html"
        admin_path = dist_root / "admin.html"
        vite_manifest_path = get_frontend_vite_manifest_path()
        missing = [str(path) for path in (index_path, admin_path, vite_manifest_path) if not path.exists()]
        dist_check = _check(
            "frontend_dist",
            "error" if missing else "ok",
            "前端 dist 缺失，请重新构建 frontend 容器。" if missing else "前端 dist 已生成。",
            {
                "dist_root": str(dist_root),
                "missing": missing,
            },
        )

        manifest = inspect_extension_frontend_output_manifest()
        if not manifest.get("exists"):
            manifest_check = _check("extension_frontend_manifest", "error", "扩展前端 manifest 缺失，请执行 build_extension_frontend。", _summarize_frontend_manifest(manifest))
        elif manifest.get("input_stale"):
            manifest_check = _check("extension_frontend_manifest", "error", "扩展前端 manifest 已过期，请重新执行 build_extension_frontend。", _summarize_frontend_manifest(manifest))
        elif not manifest.get("vite_manifest_exists"):
            manifest_check = _check("extension_frontend_manifest", "warning", "扩展前端 manifest 已生成，但当前前端 dist manifest 缺失。", _summarize_frontend_manifest(manifest))
        else:
            manifest_check = _check("extension_frontend_manifest", "ok", "扩展前端 manifest 正常。", _summarize_frontend_manifest(manifest))
        return [dist_check, manifest_check]

    def _check_cache(self) -> dict[str, Any]:
        key = "bias:doctor:cache"
        try:
            cache.set(key, "ok", timeout=30)
            value = cache.get(key)
        except Exception as exc:
            return _check("cache", "error", f"缓存读写失败: {exc}")
        if value != "ok":
            return _check("cache", "error", "缓存读写结果不一致。")
        return _check("cache", "ok", "缓存读写正常。")

    def _write_text(self, payload: dict[str, Any]) -> None:
        self.stdout.write("Bias doctor:")
        for item in payload["checks"]:
            self.stdout.write(f"- [{item['status'].upper()}] {item['name']}: {item['message']}")
        summary = payload["summary"]
        line = (
            f"检查 {summary['check_count']} 项，"
            f"错误 {summary['error_count']}，"
            f"警告 {summary['warning_count']}"
        )
        if payload["ok"]:
            self.stdout.write(self.style.SUCCESS(f"[OK] {line}"))
        else:
            self.stdout.write(self.style.ERROR(f"[ERROR] {line}"))


def _check(name: str, status: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "message": message,
        "details": details or {},
    }


def _summarize_frontend_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    build = dict(payload.get("build") or {})
    return {
        "path": str(payload.get("path") or ""),
        "exists": bool(payload.get("exists")),
        "generated_at": str(payload.get("generated_at") or ""),
        "extension_count": int(payload.get("extension_count") or 0),
        "input_revision": str(payload.get("input_revision") or ""),
        "current_input_revision": str(payload.get("current_input_revision") or ""),
        "input_stale": bool(payload.get("input_stale")),
        "vite_manifest_path": str(payload.get("vite_manifest_path") or ""),
        "vite_manifest_exists": bool(payload.get("vite_manifest_exists")),
        "build_ran": bool(build.get("ran")),
        "build_compiled_at": str(build.get("compiled_at") or ""),
    }
