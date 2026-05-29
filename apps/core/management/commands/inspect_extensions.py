from __future__ import annotations

import json

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extension_serialization import (
    serialize_admin_extension,
    serialize_admin_extensions_payload,
)
from apps.core.extensions import get_extension_registry
from apps.core.extensions.exceptions import ExtensionNotFoundError


class Command(BaseCommand):
    help = "导出扩展清单与诊断快照，供 CI、发布脚本和运维巡检消费。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--extension-id",
            help="只导出指定扩展",
        )
        parser.add_argument(
            "--only-attention",
            action="store_true",
            help="仅输出存在风险、异常或待处理项的扩展",
        )
        parser.add_argument(
            "--include-permissions",
            action="store_true",
            help="附带权限分组明细，默认仅输出权限摘要",
        )
        parser.add_argument(
            "--format",
            choices=("json",),
            default="json",
            help="输出格式，当前仅支持 json",
        )

    def handle(self, *args, **options):
        extension_id = str(options.get("extension_id") or "").strip()
        only_attention = bool(options.get("only_attention"))
        include_permissions = bool(options.get("include_permissions"))

        registry = get_extension_registry()
        registry.load(force=True)

        if extension_id:
            try:
                extensions = [registry.get_extension(extension_id)]
            except ExtensionNotFoundError as exc:
                raise CommandError(str(exc)) from exc
        else:
            extensions = registry.get_extensions()

        payload = serialize_admin_extensions_payload(extensions)
        serialized_extensions = payload["extensions"]

        if include_permissions or extension_id:
            serialized_extensions = [
                serialize_admin_extension(
                    extension,
                    include_permission_details=include_permissions or bool(extension_id),
                )
                for extension in extensions
            ]
            payload = {
                **payload,
                "extensions": serialized_extensions,
                "summary": {
                    **payload["summary"],
                    "extension_count": len(serialized_extensions),
                    "enabled_count": sum(1 for item in serialized_extensions if item["enabled"]),
                    "healthy_count": sum(1 for item in serialized_extensions if item["healthy"]),
                    "builtin_count": sum(1 for item in serialized_extensions if item["source"] == "builtin-module"),
                    "filesystem_count": sum(1 for item in serialized_extensions if item["source"] == "filesystem"),
                },
            }

        if only_attention:
            serialized_extensions = [
                item for item in serialized_extensions
                if self._needs_attention(item)
            ]
            payload = {
                **payload,
                "extensions": serialized_extensions,
                "summary": {
                    **payload["summary"],
                    "extension_count": len(serialized_extensions),
                    "enabled_count": sum(1 for item in serialized_extensions if item["enabled"]),
                    "healthy_count": sum(1 for item in serialized_extensions if item["healthy"]),
                    "builtin_count": sum(1 for item in serialized_extensions if item["source"] == "builtin-module"),
                    "filesystem_count": sum(1 for item in serialized_extensions if item["source"] == "filesystem"),
                    "attention_count": len(serialized_extensions),
                },
            }
        else:
            payload["summary"]["attention_count"] = sum(
                1 for item in serialized_extensions if self._needs_attention(item)
            )

        payload["meta"] = {
            "base_dir": str(settings.BASE_DIR),
            "extension_id": extension_id,
            "only_attention": only_attention,
            "include_permissions": include_permissions,
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))

    def _needs_attention(self, item: dict) -> bool:
        if not item.get("healthy", True):
            return True
        if item.get("runtime_issues"):
            return True
        if item.get("migration_state") in {"attention"}:
            return True
        if item.get("dependency_state") not in {"", "healthy"}:
            return True

        delivery_checks = item.get("delivery_checks") or []
        return any(check.get("status") == "attention" for check in delivery_checks)
