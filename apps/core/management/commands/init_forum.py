from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command
from django.core.management.base import CommandParser
from django.core.management.utils import get_random_secret_key

from apps.users.models import Group, User


ENV_DEFAULTS = {
    "DEBUG": "True",
    "SECRET_KEY": "",
    "ALLOWED_HOSTS": "localhost,127.0.0.1",
    "DB_MODE": "sqlite",
    "SQLITE_NAME": "db.sqlite3",
    "DB_ENGINE": "django.db.backends.postgresql",
    "DB_NAME": "pyflarum",
    "DB_USER": "postgres",
    "DB_PASSWORD": "postgres",
    "DB_HOST": "localhost",
    "DB_PORT": "5432",
    "USE_REDIS": "False",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_DB": "0",
    "CELERY_BROKER_URL": "",
    "CELERY_RESULT_BACKEND": "",
    "EMAIL_BACKEND": "django.core.mail.backends.console.EmailBackend",
    "EMAIL_HOST": "smtp.gmail.com",
    "EMAIL_PORT": "587",
    "EMAIL_USE_TLS": "True",
    "EMAIL_HOST_USER": "",
    "EMAIL_HOST_PASSWORD": "",
    "DEFAULT_FROM_EMAIL": "noreply@pyflarum.com",
    "JWT_SECRET_KEY": "",
    "JWT_ALGORITHM": "HS256",
    "JWT_ACCESS_TOKEN_LIFETIME": "3600",
    "JWT_REFRESH_TOKEN_LIFETIME": "86400",
    "CORS_ALLOWED_ORIGINS": "http://localhost:3000,http://localhost:5173",
    "MEDIA_URL": "/media/",
    "STATIC_URL": "/static/",
    "FRONTEND_URL": "http://localhost:5173",
}

ENV_ORDER = [
    "DEBUG",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "DB_MODE",
    "SQLITE_NAME",
    "DB_ENGINE",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "USE_REDIS",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_DB",
    "CELERY_BROKER_URL",
    "CELERY_RESULT_BACKEND",
    "EMAIL_BACKEND",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_USE_TLS",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
    "DEFAULT_FROM_EMAIL",
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "JWT_ACCESS_TOKEN_LIFETIME",
    "JWT_REFRESH_TOKEN_LIFETIME",
    "CORS_ALLOWED_ORIGINS",
    "MEDIA_URL",
    "STATIC_URL",
    "FRONTEND_URL",
]


class Command(BaseCommand):
    help = "初始化论坛环境：写入 .env、执行迁移、初始化默认用户组并创建管理员。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--database",
            choices=["sqlite", "postgres"],
            help="数据库模式。sqlite 适合快速启动，postgres 适合正式部署。",
        )
        parser.add_argument("--env-file", default=".env", help="环境文件路径，默认写入项目根目录 .env")
        parser.add_argument("--skip-env-write", action="store_true", help="跳过写入 .env 文件")
        parser.add_argument("--skip-migrate", action="store_true", help="跳过执行 migrate")
        parser.add_argument("--skip-admin", action="store_true", help="跳过创建或更新管理员账号")
        parser.add_argument("--admin-username", help="管理员用户名")
        parser.add_argument("--admin-email", help="管理员邮箱")
        parser.add_argument("--admin-password", help="管理员密码")
        parser.add_argument("--frontend-url", help="前端访问地址，默认 http://localhost:5173")
        parser.add_argument("--sqlite-name", default="db.sqlite3", help="SQLite 数据库文件名或路径")
        parser.add_argument("--db-name", help="PostgreSQL 数据库名")
        parser.add_argument("--db-user", help="PostgreSQL 用户名")
        parser.add_argument("--db-password", help="PostgreSQL 密码")
        parser.add_argument("--db-host", help="PostgreSQL 主机")
        parser.add_argument("--db-port", help="PostgreSQL 端口")
        parser.add_argument(
            "--redis",
            choices=["auto", "on", "off"],
            default="auto",
            help="Redis 使用策略。auto: sqlite 默认关闭，postgres 默认开启。",
        )
        parser.add_argument("--redis-host", help="Redis 主机")
        parser.add_argument("--redis-port", help="Redis 端口")
        parser.add_argument("--redis-db", help="Redis 数据库编号")
        parser.add_argument("--non-interactive", action="store_true", help="使用非交互模式执行")

    def handle(self, *args, **options):
        non_interactive = bool(options["non_interactive"])
        database = options.get("database") or self._prompt_database(non_interactive)
        env_path = self._resolve_env_path(options["env_file"])
        env_values = self._build_env_values(database, options)

        self.stdout.write(self.style.MIGRATE_HEADING("开始初始化 PyFlarum"))
        self.stdout.write(f"数据库模式: {database}")
        self.stdout.write(f"Redis: {'开启' if env_values['USE_REDIS'] == 'True' else '关闭'}")
        self.stdout.write(f"环境文件: {env_path}")

        if not options["skip_env_write"]:
            self._write_env_file(env_path, env_values)
            self.stdout.write(self.style.SUCCESS(f"[OK] 已写入环境文件: {env_path}"))
        else:
            self.stdout.write("[SKIP] 已跳过环境文件写入")

        self._apply_process_env(env_values)

        if not options["skip_migrate"]:
            self.stdout.write("执行数据库迁移...")
            call_command("migrate", interactive=not non_interactive)
        else:
            self.stdout.write("[SKIP] 已跳过 migrate")

        self.stdout.write("初始化默认用户组与权限...")
        call_command("init_groups")

        if not options["skip_admin"]:
            admin_user = self._ensure_admin(options, non_interactive)
            self.stdout.write(self.style.SUCCESS(f"[OK] 管理员账号已就绪: {admin_user.username}"))
        else:
            self.stdout.write("[SKIP] 已跳过管理员创建")

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] 初始化完成"))
        self.stdout.write(f"- 前端地址: {env_values['FRONTEND_URL']}")
        if env_values["USE_REDIS"] == "True":
            self.stdout.write("- Redis 已启用，缓存、Channel Layer 与 Celery 默认走 Redis")
        else:
            self.stdout.write("- Redis 已关闭，当前使用进程内缓存/队列，适合本地单机开发")
        self.stdout.write("- 下一步可以执行: python manage.py runserver")

    def _resolve_env_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _prompt_database(self, non_interactive: bool) -> str:
        if non_interactive:
            return "sqlite"

        answer = input("选择数据库模式 [sqlite/postgres] (默认 sqlite): ").strip().lower()
        if answer in {"", "sqlite", "sqlite3"}:
            return "sqlite"
        if answer in {"postgres", "postgresql"}:
            return "postgres"
        raise CommandError("无效的数据库模式，请选择 sqlite 或 postgres")

    def _build_env_values(self, database: str, options: Dict[str, str]) -> Dict[str, str]:
        values = dict(ENV_DEFAULTS)
        values["SECRET_KEY"] = get_random_secret_key()
        values["JWT_SECRET_KEY"] = get_random_secret_key()
        values["FRONTEND_URL"] = options.get("frontend_url") or ENV_DEFAULTS["FRONTEND_URL"]
        values["DB_MODE"] = database
        values["REDIS_HOST"] = options.get("redis_host") or ENV_DEFAULTS["REDIS_HOST"]
        values["REDIS_PORT"] = options.get("redis_port") or ENV_DEFAULTS["REDIS_PORT"]
        values["REDIS_DB"] = options.get("redis_db") or ENV_DEFAULTS["REDIS_DB"]
        values["USE_REDIS"] = "True" if self._resolve_redis_enabled(database, options.get("redis")) else "False"

        if database == "sqlite":
            values["SQLITE_NAME"] = options.get("sqlite_name") or ENV_DEFAULTS["SQLITE_NAME"]
        else:
            values["DEBUG"] = "False"
            values["DB_NAME"] = options.get("db_name") or ENV_DEFAULTS["DB_NAME"]
            values["DB_USER"] = options.get("db_user") or ENV_DEFAULTS["DB_USER"]
            values["DB_PASSWORD"] = options.get("db_password") or ENV_DEFAULTS["DB_PASSWORD"]
            values["DB_HOST"] = options.get("db_host") or ENV_DEFAULTS["DB_HOST"]
            values["DB_PORT"] = options.get("db_port") or ENV_DEFAULTS["DB_PORT"]

        return values

    def _resolve_redis_enabled(self, database: str, redis_mode: str | None) -> bool:
        if redis_mode == "on":
            return True
        if redis_mode == "off":
            return False
        return database == "postgres"

    def _write_env_file(self, env_path: Path, values: Dict[str, str]) -> None:
        lines = [
            "# Generated by: python manage.py init_forum",
            f"# Database mode: {values['DB_MODE']}",
            f"# Redis enabled: {values['USE_REDIS']}",
            "",
        ]
        for key in ENV_ORDER:
            lines.append(f"{key}={values.get(key, '')}")
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _apply_process_env(self, values: Dict[str, str]) -> None:
        for key, value in values.items():
            os.environ[key] = value

    def _ensure_admin(self, options: Dict[str, str], non_interactive: bool) -> User:
        username = options.get("admin_username")
        email = options.get("admin_email")
        password = options.get("admin_password")

        if not non_interactive:
            username = username or input("管理员用户名 [admin]: ").strip() or "admin"
            email = email or input("管理员邮箱 [admin@example.com]: ").strip() or "admin@example.com"
            if not password:
                password = input("管理员密码 [admin123456]: ").strip() or "admin123456"

        if not username or not email or not password:
            raise CommandError("非交互模式下必须同时提供 --admin-username、--admin-email 和 --admin-password")

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
            self.stdout.write(self.style.SUCCESS("[OK] 已创建管理员账号"))
        else:
            self.stdout.write("[OK] 已更新现有管理员账号")
        return user
