from __future__ import annotations

import subprocess

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.release import (
    ensure_release_versions_aligned,
    run_git_command,
    validate_release_tag,
    version_from_tag,
)


class Command(BaseCommand):
    help = "完成发布：校验版本一致性并创建 Git tag。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--tag", required=True, help="要创建的 Git tag，例如 v1.2.3")
        parser.add_argument("--message", help="可选的 tag 注释内容，默认使用版本号")
        parser.add_argument("--dry-run", action="store_true", help="只做校验，不创建 tag")
        parser.add_argument("--allow-dirty", action="store_true", help="允许 Git 工作区存在未提交改动")

    def handle(self, *args, **options):
        tag = validate_release_tag(str(options["tag"]))
        tag_version = version_from_tag(tag)
        dry_run = bool(options.get("dry_run"))
        allow_dirty = bool(options.get("allow_dirty"))
        message = (options.get("message") or f"Release {tag}").strip()

        try:
            state = ensure_release_versions_aligned(settings.BASE_DIR)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        if state.version != tag_version:
            raise CommandError(
                f"Git tag 与代码版本不一致：tag={tag}，VERSION={state.version}"
            )

        if not allow_dirty:
            self._ensure_clean_git_state()

        self._ensure_tag_not_exists(tag)

        self.stdout.write(self.style.SUCCESS("[OK] 发布前校验通过"))
        self.stdout.write(f"- VERSION: {state.version}")
        self.stdout.write(f"- frontend/package.json: {state.frontend_version}")
        self.stdout.write(f"- Git tag: {tag}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("[DRY-RUN] 未创建 Git tag"))
            return

        run_git_command(settings.BASE_DIR, "tag", "-a", tag, "-m", message)
        self.stdout.write(self.style.SUCCESS(f"[OK] 已创建 Git tag: {tag}"))

    def _ensure_clean_git_state(self) -> None:
        result = run_git_command(settings.BASE_DIR, "status", "--short")
        if result.stdout.strip():
            raise CommandError("Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty")

    def _ensure_tag_not_exists(self, tag: str) -> None:
        result = run_git_command(settings.BASE_DIR, "tag", "--list", tag)
        if result.stdout.strip():
            raise CommandError(f"Git tag 已存在: {tag}")
