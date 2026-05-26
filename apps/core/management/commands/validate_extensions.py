from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extensions.exceptions import ExtensionManifestError
from apps.core.extensions.manifest import ExtensionManifestLoader
from apps.core.extensions.validation import validate_extension_manifests_with_available_ids
from apps.core.forum_registry import get_builtin_module_ids


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

    def handle(self, *args, **options):
        extensions_path = Path(options.get("extensions_path") or (Path(settings.BASE_DIR) / "extensions"))
        strict = bool(options.get("strict"))

        loader = ExtensionManifestLoader(extensions_path)
        try:
            manifests = [item.manifest for item in loader.discover()]
        except ExtensionManifestError as exc:
            raise CommandError(str(exc)) from exc

        builtin_extension_ids = set(get_builtin_module_ids())
        result = validate_extension_manifests_with_available_ids(
            manifests,
            available_extension_ids=builtin_extension_ids,
            extensions_base_path=extensions_path,
            strict_runtime_hooks=strict,
        )

        self.stdout.write(f"已扫描扩展: {len(result.manifests)}")
        for issue in result.issues:
            prefix = "[ERROR]" if issue.level == "error" else "[WARN]"
            target = f"{issue.extension_id}" if issue.extension_id else "-"
            field = f" ({issue.field})" if issue.field else ""
            self.stdout.write(f"{prefix} {target}{field} {issue.message}")

        if result.error_count:
            raise CommandError(f"扩展校验失败，共 {result.error_count} 个错误")
        if strict and result.warning_count:
            raise CommandError(f"扩展严格校验失败，共 {result.warning_count} 个警告")

        self.stdout.write(self.style.SUCCESS(
            f"[OK] 扩展校验通过，错误 {result.error_count}，警告 {result.warning_count}"
        ))
