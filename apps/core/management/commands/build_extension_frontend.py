from __future__ import annotations

import json
from pathlib import Path

from django.core.management import BaseCommand
from django.core.management.base import CommandParser

from apps.core.extensions.frontend_compiler import (
    flush_extension_frontend_assets,
    recompile_extension_frontend_assets,
)
from apps.core.extensions.manager import get_extension_manager
from apps.core.extensions.lifecycle import mark_extension_runtime_requires_rebuild


class Command(BaseCommand):
    help = "生成扩展前端构建 manifest，供 Vite/部署流程消费。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--include-disabled",
            action="store_true",
            help="包含已安装但未启用的扩展。",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
        )
        parser.add_argument(
            "--rebuild",
            action="store_true",
            help="调用 frontend 目录下的 npm run build，生成真实 Vite 产物。默认只生成扩展构建清单。",
        )
        parser.add_argument(
            "--flush",
            action="store_true",
            help="清理扩展前端构建清单和生成的 import map。",
        )
        parser.add_argument(
            "--publish",
            action="store_true",
            help="在 rebuild 成功后把 frontend/dist 发布到 static/frontend。",
        )
        parser.add_argument(
            "--flush-published",
            action="store_true",
            help="配合 --flush 清理 static/frontend 中已发布的前端 dist。",
        )

    def handle(self, *args, **options):
        include_disabled = bool(options.get("include_disabled"))
        output_format = str(options.get("format") or "text")
        rebuild = bool(options.get("rebuild"))
        flush = bool(options.get("flush"))
        publish = bool(options.get("publish"))
        flush_published = bool(options.get("flush_published"))

        if flush:
            result = flush_extension_frontend_assets(include_published=flush_published)
            if output_format == "json":
                self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
                return
            self.stdout.write(self.style.SUCCESS(f"[OK] {result['message']}"))
            return

        manager = get_extension_manager()
        manager.load(force=True)
        extensions = [
            extension
            for extension in manager.get_extensions()
            if extension.source != "builtin-module"
            and extension.runtime.installed
            and (include_disabled or extension.runtime.enabled)
        ]
        result = recompile_extension_frontend_assets(
            extensions,
            run_build=rebuild,
            clear_marker=rebuild,
            publish_dist=publish,
        )
        if not rebuild:
            mark_extension_runtime_requires_rebuild("extension_frontend_manifest_built")

        if output_format == "json":
            self.stdout.write(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
            return

        if result.status == "error":
            self.stdout.write(self.style.ERROR(
                f"[ERROR] {result.message} returncode={result.returncode}"
            ))
            return

        path = Path(result.manifest_path)
        suffix = "并完成 Vite 编译" if rebuild else "，未执行 Vite 编译"
        self.stdout.write(self.style.SUCCESS(
            f"[OK] 已生成扩展前端构建 manifest: {path}，扩展 {result.extension_count} 个{suffix}"
        ))
