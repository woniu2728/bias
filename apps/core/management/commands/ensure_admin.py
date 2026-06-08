from __future__ import annotations

from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from extensions.users.backend.models import Group, User


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

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_email_confirmed": True,
            },
        )

        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_email_confirmed = True
        user.set_password(password)
        user.save()

        admin_group = Group.objects.filter(name="Admin").first()
        if admin_group is not None:
            user.user_groups.add(admin_group)

        if created:
            self.stdout.write(self.style.SUCCESS(f"[OK] 已创建管理员账号: {user.username}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"[OK] 已更新管理员账号: {user.username}"))
