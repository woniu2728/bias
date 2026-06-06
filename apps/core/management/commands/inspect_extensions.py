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
from apps.core.extensions.module_extension_view import resolve_module_extension_definition
from apps.core.extensions import get_extension_registry
from apps.core.extensions.exceptions import ExtensionNotFoundError
from apps.core.forum_registry import get_forum_registry


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
                module_extension = _resolve_core_module_extension(extension_id)
                if module_extension is None:
                    raise CommandError(str(exc)) from exc
                extensions = [module_extension]
        else:
            extensions = _resolve_inspection_extensions(registry.get_extensions())

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
        payload["package_lock"] = registry.inspect_extension_packages(force=True)
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2))


def _resolve_inspection_extensions(filesystem_extensions):
    extensions = list(filesystem_extensions)
    existing_ids = {extension.id for extension in extensions}
    core_module_extensions = [
        resolve_module_extension_definition(module)
        for module in get_forum_registry().get_modules()
        if module.module_id not in existing_ids
    ]
    return sorted(
        [*extensions, *core_module_extensions],
        key=lambda item: (
            0 if item.id == "core" else 1,
            0 if item.source == "core-module" else 1,
            item.id,
        ),
    )


def _resolve_core_module_extension(extension_id: str):
    normalized = str(extension_id or "").strip()
    if not normalized:
        return None
    module = next(
        (item for item in get_forum_registry().get_modules() if item.module_id == normalized),
        None,
    )
    if module is None:
        return None
    return resolve_module_extension_definition(module)
