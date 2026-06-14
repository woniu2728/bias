from __future__ import annotations

from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.extensions.runtime import ensure_runtime_admin_user


class Command(BaseCommand):
    help = "创建或更新论坛管理员账号。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--username", required=True, help="管理员用户名")
        parser.add_argument("--email", required=True, help="管理员邮箱")
        parser.add_argument("--password", required=True, help="管理员密码")

    def handle(self, *args, **options):
        username = (options.get("username") or "").strip()
        email = (options.get("email") or "").strip()
        password = options.get("password") or ""

        if not username or not email or not password:
            raise CommandError("必须同时提供 --username、--email 和 --password")

        try:
            result = ensure_runtime_admin_user(username=username, email=email, password=password)
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc

        if result.get("created"):
            self.stdout.write(self.style.SUCCESS(f"[OK] 已创建管理员账号: {result.get('username') or username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] 已更新管理员账号: {result.get('username') or username}"))
