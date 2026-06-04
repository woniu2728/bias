from __future__ import annotations

import json

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extension_diagnostics import (
    classify_extension_diagnostics,
    summarize_extension_delivery,
    summarize_extension_diagnostics,
)
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
            "--only-blocking",
            action="store_true",
            help="仅输出会阻断发布或需要优先处理的扩展",
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
        only_blocking = bool(options.get("only_blocking"))
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
                    "filesystem_count": sum(1 for item in serialized_extensions if item["source"] == "filesystem"),
                },
            }

        serialized_extensions = [
            {
                **item,
                "diagnostics": classify_extension_diagnostics(item),
            }
            for item in serialized_extensions
        ]

        if only_blocking:
            serialized_extensions = [
                item for item in serialized_extensions
                if item["diagnostics"]["blocking"]
            ]

        elif only_attention:
            serialized_extensions = [
                item for item in serialized_extensions
                if item["diagnostics"]["has_attention"]
            ]

        diagnostics_summary = summarize_extension_diagnostics(serialized_extensions)
        delivery_summary = summarize_extension_delivery(serialized_extensions)
        payload = {
            **payload,
            "extensions": serialized_extensions,
            "summary": {
                **payload["summary"],
                "extension_count": len(serialized_extensions),
                "enabled_count": sum(1 for item in serialized_extensions if item["enabled"]),
                "healthy_count": sum(1 for item in serialized_extensions if item["healthy"]),
                "filesystem_count": sum(1 for item in serialized_extensions if item["source"] == "filesystem"),
                **diagnostics_summary,
                **delivery_summary,
            },
        }

        payload["meta"] = {
            "base_dir": str(settings.BASE_DIR),
            "extension_id": extension_id,
            "only_attention": only_attention,
            "only_blocking": only_blocking,
            "include_permissions": include_permissions,
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))
