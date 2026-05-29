from __future__ import annotations

import json
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management import call_command
from django.core.management.base import CommandParser

from apps.core.release import (
    ensure_release_versions_aligned,
    run_git_command,
    update_frontend_versions,
    validate_release_tag,
    validate_semver,
    version_from_tag,
)


class Command(BaseCommand):
    help = "准备发布版本：统一 VERSION/前端版本，并强制校验 Git tag 与工作区状态。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--set-version", help="要发布的语义化版本号，例如 1.2.3")
        parser.add_argument("--tag", help="要发布的 Git tag，例如 v1.2.3")
        parser.add_argument("--allow-dirty", action="store_true", help="允许 Git 工作区存在未提交改动")
        parser.add_argument("--dry-run", action="store_true", help="只输出检查结果，不写入任何文件")
        parser.add_argument("--extension-report", help="可选：把扩展诊断快照写入指定 JSON 文件")
        parser.add_argument(
            "--allow-extension-attention",
            action="store_true",
            help="允许存在扩展关注项继续发布；默认存在关注项就阻止发布",
        )

    def handle(self, *args, **options):
        version = (options.get("set_version") or "").strip()
        tag = (options.get("tag") or "").strip()
        dry_run = bool(options.get("dry_run"))
        allow_dirty = bool(options.get("allow_dirty"))
        extension_report = (options.get("extension_report") or "").strip()
        allow_extension_attention = bool(options.get("allow_extension_attention"))

        if not version and not tag:
            raise CommandError("必须至少提供 --set-version 或 --tag")

        if version:
            validate_semver(version)
        if tag:
            validate_release_tag(tag)

        resolved_version = version_from_tag(tag) if tag else version
        if version and tag and resolved_version != version:
            raise CommandError("--set-version 与 --tag 不一致")

        base_dir = settings.BASE_DIR
        version_file = base_dir / "VERSION"

        if not allow_dirty:
            self._ensure_clean_git_state()

        call_command("validate_extensions", "--strict")
        inspection_payload = self._inspect_extensions()
        attention_count = int((inspection_payload.get("summary") or {}).get("attention_count") or 0)
        if attention_count and not allow_extension_attention:
            raise CommandError(
                f"扩展诊断存在 {attention_count} 个关注项，请先处理；如需继续请传 --allow-extension-attention"
            )
        if extension_report:
            self._write_extension_report(extension_report, inspection_payload)

        current_version = version_file.read_text(encoding="utf-8").strip()
        validate_semver(current_version, field_name="VERSION")

        if not dry_run:
            version_file.write_text(f"{resolved_version}\n", encoding="utf-8")
            update_frontend_versions(base_dir, resolved_version)

        try:
            state = ensure_release_versions_aligned(base_dir)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if tag and state.version != version_from_tag(tag):
            raise CommandError("VERSION 与 Git tag 不一致")

        self.stdout.write(self.style.SUCCESS("[OK] 版本文件一致性检查通过"))
        self.stdout.write(f"- VERSION: {state.version}")
        self.stdout.write(f"- frontend/package.json: {state.frontend_version}")
        self.stdout.write(f"- 扩展关注项: {attention_count}")
        if extension_report:
            self.stdout.write(f"- 扩展报告: {extension_report}")
        if tag:
            self.stdout.write(f"- Git tag: {tag}")
        if dry_run:
            self.stdout.write(self.style.SUCCESS("[DRY-RUN] 未写入文件"))
        else:
            self.stdout.write(self.style.SUCCESS("[OK] 已同步 VERSION 与前端版本号"))

    def _ensure_clean_git_state(self) -> None:
        result = run_git_command(settings.BASE_DIR, "status", "--short")
        output = result.stdout.strip()
        if output:
            raise CommandError("Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty")

    def _inspect_extensions(self) -> dict:
        from io import StringIO

        stdout = StringIO()
        call_command("inspect_extensions", "--format", "json", stdout=stdout)
        return json.loads(stdout.getvalue())

    def _write_extension_report(self, output_path: str, payload: dict) -> None:
        report_path = Path(output_path)
        if not report_path.is_absolute():
            report_path = settings.BASE_DIR / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
