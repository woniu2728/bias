from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extensions.exceptions import ExtensionManifestError
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.validation import validate_extension_manifests_with_available_ids
from apps.core.forum_registry import get_core_module_ids


def resolve_available_extension_ids(manifests) -> set[str]:
    return set(get_core_module_ids()) | {manifest.id for manifest in manifests}


class Command(BaseCommand):
    help = "校验扩展 manifest、依赖关系与后台入口约束。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--extensions-path",
            help="扩展目录路径，默认使用 BASE_DIR/extensions",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="将 warning 也视为失败",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
            help="输出格式，默认 text，可选 json 便于 CI 消费",
        )

    def handle(self, *args, **options):
        extensions_path = Path(options.get("extensions_path") or (Path(settings.BASE_DIR) / "extensions"))
        strict = bool(options.get("strict"))
        output_format = str(options.get("format") or "text").strip() or "text"

        loader = ExtensionManifestLoader(extensions_path)
        try:
            manifests = loader.discover_manifests()
        except ExtensionManifestError as exc:
            raise CommandError(str(exc)) from exc

        available_extension_ids = resolve_available_extension_ids(manifests)
        result = validate_extension_manifests_with_available_ids(
            manifests,
            available_extension_ids=available_extension_ids,
            extensions_base_path=extensions_path,
            strict_runtime_hooks=strict,
        )
        if result.error_count == 0:
            try:
                manifests = [item.manifest for item in loader.discover()]
            except ExtensionManifestError as exc:
                raise CommandError(str(exc)) from exc
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids=available_extension_ids,
                extensions_base_path=extensions_path,
                strict_runtime_hooks=strict,
            )

        payload = {
            "extensions_path": str(extensions_path),
            "strict": strict,
            "summary": {
                "manifest_count": len(result.manifests),
                "error_count": result.error_count,
                "warning_count": result.warning_count,
                "ok": result.ok and not (strict and _has_blocking_warnings(result.issues)),
            },
            "manifests": [
                {
                    "id": manifest.id,
                    "name": manifest.name,
                    "version": manifest.version,
                    "source": manifest.source,
                    "path": manifest.path,
                }
                for manifest in result.manifests
            ],
            "issues": [
                {
                    "level": issue.level,
                    "code": issue.code,
                    "field": issue.field,
                    "message": issue.message,
                    "extension_id": issue.extension_id,
                }
                for issue in result.issues
            ],
        }

        if output_format == "json":
            self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
            if result.error_count:
                raise CommandError(f"扩展校验失败，共 {result.error_count} 个错误")
            if strict and _has_blocking_warnings(result.issues):
                raise CommandError("扩展严格校验失败，存在阻断性警告")
            return

        self.stdout.write(f"已扫描扩展: {len(result.manifests)}")
        for issue in result.issues:
            prefix = "[ERROR]" if issue.level == "error" else "[WARN]"
            target = f"{issue.extension_id}" if issue.extension_id else "-"
            field = f" ({issue.field})" if issue.field else ""
            self.stdout.write(f"{prefix} {issue.code} {target}{field} {issue.message}")

        if result.error_count:
            raise CommandError(f"扩展校验失败，共 {result.error_count} 个错误")
        if strict and _has_blocking_warnings(result.issues):
            raise CommandError("扩展严格校验失败，存在阻断性警告")

        self.stdout.write(self.style.SUCCESS(
            f"[OK] 扩展校验通过，错误 {result.error_count}，警告 {result.warning_count}"
        ))


def _has_blocking_warnings(issues) -> bool:
    return any(
        item.level == "warning"
        for item in issues
    )
