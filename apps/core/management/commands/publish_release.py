from __future__ import annotations

import subprocess

from django.conf import settings
from django.core.management import BaseCommand, call_command
from django.core.management.base import CommandParser

from apps.core.release import run_git_command


class Command(BaseCommand):
    help = "一键准备版本、提交发布 commit，并创建 Git tag。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--set-version", required=True, help="要发布的语义化版本号，例如 1.2.3")
        parser.add_argument("--tag", help="要发布的 Git tag，例如 v1.2.3；不传时自动推导为 v<version>")
        parser.add_argument("--message", help="可选的 tag 注释内容")
        parser.add_argument("--allow-dirty", action="store_true", help="允许 Git 工作区存在未提交改动")
        parser.add_argument("--commit-message", help="可选的发布 commit 信息，默认使用“发布 X.Y.Z”")
        parser.add_argument("--push", action="store_true", help="创建 tag 后自动 push 到 origin main --tags")
        parser.add_argument("--dry-run", action="store_true", help="只做校验和预演，不写文件、不创建 tag")

    def handle(self, *args, **options):
        version = str(options["set_version"]).strip()
        tag = str(options.get("tag") or f"v{version}").strip()
        message = options.get("message")
        commit_message = str(options.get("commit_message") or f"发布 {version}").strip()
        allow_dirty = bool(options.get("allow_dirty"))
        push = bool(options.get("push"))
        dry_run = bool(options.get("dry_run"))

        self.stdout.write(self.style.MIGRATE_HEADING("开始准备发布 Bias"))

        prepare_args = [
            "--set-version",
            version,
            "--tag",
            tag,
        ]
        finalize_args = [
            "--tag",
            tag,
        ]

        if allow_dirty:
            prepare_args.append("--allow-dirty")
        if dry_run:
            prepare_args.append("--dry-run")
            finalize_args.append("--dry-run")
        if message:
            finalize_args.extend(["--message", str(message)])

        call_command("prepare_release", *prepare_args)

        if not dry_run:
            self._run_git_command(["git", "add", "VERSION", "frontend/package.json", "frontend/package-lock.json"])
            self._run_git_command(["git", "commit", "-m", commit_message])

        call_command("finalize_release", *finalize_args)

        if push and not dry_run:
            self._run_git_command(["git", "push", "origin", "main", "--tags"])

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] 发布预检完成"))
        self.stdout.write(f"- VERSION: {version}")
        self.stdout.write(f"- Git tag: {tag}")
        if dry_run:
            self.stdout.write("- 当前为 dry-run，未写入文件、未创建 tag")
        else:
            self.stdout.write(f"- 发布 commit: {commit_message}")
            if push:
                self.stdout.write("- 已自动 push 到 origin main --tags")
            else:
                self.stdout.write("- 下一步请执行 git push origin main --tags")

    def _run_git_command(self, command: list[str]) -> None:
        run_git_command(settings.BASE_DIR, *command[1:])
