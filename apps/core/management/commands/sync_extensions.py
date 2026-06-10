from __future__ import annotations

import json

from django.core.management import BaseCommand
from django.core.management.base import CommandParser

from apps.core.extensions.manager import get_extension_manager


class Command(BaseCommand):
    help = "同步已发现的文件系统/Python package 扩展状态。"
    requires_system_checks = []

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--no-prune",
            action="store_true",
            help="不禁用已经无法发现的扩展安装记录。",
        )
        parser.add_argument(
            "--format",
            choices=("text", "json"),
            default="text",
        )

    def handle(self, *args, **options):
        result = get_extension_manager().sync_extension_packages(
            prune_missing=not bool(options.get("no_prune")),
        )
        if options.get("format") == "json":
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
            return

        self.stdout.write(f"已发现扩展: {len(result['discovered'])}")
        if result.get("created"):
            self.stdout.write(f"已创建安装记录: {', '.join(result['created'])}")
        if result["updated"]:
            self.stdout.write(f"已更新安装记录: {', '.join(result['updated'])}")
        if result["pruned"]:
            self.stdout.write(f"已禁用缺失扩展: {', '.join(result['pruned'])}")
        package_summary = dict((result.get("package_inspection") or {}).get("summary") or {})
        if package_summary:
            self.stdout.write(
                "包锁定: "
                f"{package_summary.get('locked_count', 0)} 个，"
                f"缺失 {package_summary.get('missing_count', 0)} 个，"
                f"版本漂移 {package_summary.get('version_drift_count', 0)} 个"
            )
        self.stdout.write(self.style.SUCCESS("[OK] 扩展状态同步完成"))
