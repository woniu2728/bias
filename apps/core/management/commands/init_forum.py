from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser
from django.core.management.utils import get_random_secret_key

from apps.core.bootstrap_config import (
    DEFAULT_SITE_CONFIG_PATH,
    SiteBootstrapConfig,
    read_site_config,
    write_site_config,
)
from apps.core.management.command_utils import build_manage_env, run_manage_py


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists()


def _first_env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip():
            return value.strip()
    return default


class Command(BaseCommand):
    help = "初始化论坛：写入站点配置、执行迁移、初始化默认用户组并创建管理员。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--database",
            choices=["sqlite", "postgres"],
            help="数据库模式。sqlite 适合本地快速启动，postgres 适合正式部署。",
        )
        parser.add_argument(
            "--config",
            default=str(DEFAULT_SITE_CONFIG_PATH),
            help="站点配置文件路径，默认写入 instance/site.json",
        )
        parser.add_argument("--overwrite", action="store_true", help="覆盖已有站点配置")
        parser.add_argument("--skip-migrate", action="store_true", help="跳过执行 migrate")
        parser.add_argument("--skip-admin", action="store_true", help="跳过创建或更新管理员账号")
        parser.add_argument("--skip-collectstatic", action="store_true", help="跳过执行 collectstatic")
        parser.add_argument("--admin-username", help="管理员用户名")
        parser.add_argument("--admin-email", help="管理员邮箱")
        parser.add_argument("--admin-password", help="管理员密码")
        parser.add_argument("--site-domains", help="站点访问域名，多个域名用逗号分隔，例如 bias.chat,www.bias.chat")
        parser.add_argument("--site-scheme", choices=["http", "https"], help="站点默认协议，默认 https")
        parser.add_argument("--frontend-url", help="前端访问地址；不填时按域名自动推导")
        parser.add_argument("--sqlite-name", help="SQLite 数据库文件名或路径")
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
        config_path = self._resolve_config_path(options["config"])
        existing_content = config_path.read_text(encoding="utf-8") if config_path.exists() else None
        existing_config = read_site_config(config_path) if config_path.exists() else None

        if existing_content is not None and not options["overwrite"]:
            raise CommandError(f"站点配置已存在: {config_path}。如需覆盖，请显式传入 --overwrite")

        database = options.get("database") or (existing_config.database_mode if existing_config else self._prompt_database(non_interactive))
        config = self._build_site_config(database, options, existing_config)

        self.stdout.write(self.style.MIGRATE_HEADING("开始初始化 Bias"))
        self.stdout.write(f"站点配置: {config_path}")
        self.stdout.write(f"数据库模式: {config.database_mode}")
        self.stdout.write(f"Redis: {'开启' if config.use_redis else '关闭'}")
        self.stdout.write(
            f"站点域名: {', '.join(config.site_domains) if config.site_domains else '未配置，保持本地默认'}"
        )

        write_site_config(config_path, config)
        command_env = build_manage_env(config_path=config_path)

        try:
            if not options["skip_migrate"]:
                self._run_manage_step("数据库迁移", ["migrate", "--noinput"], command_env)
            else:
                self.stdout.write("[SKIP] 已跳过 migrate")

            self._run_manage_step("默认用户组与权限初始化", ["init_groups"], command_env)
            self._run_manage_step("写入安装版本", ["sync_forum_version"], command_env)

            if not options["skip_collectstatic"]:
                self._run_manage_step("静态资源收集", ["collectstatic", "--noinput"], command_env)
            else:
                self.stdout.write("[SKIP] 已跳过 collectstatic")

            if not options["skip_admin"]:
                admin_args = self._build_admin_command_args(options, non_interactive)
                self._run_manage_step("管理员创建", ["ensure_admin", *admin_args], command_env)
                self.stdout.write(self.style.SUCCESS(f"[OK] 管理员账号已就绪: {admin_args[1]}"))
            else:
                self.stdout.write("[SKIP] 已跳过管理员创建")
        except Exception:
            if existing_content is None:
                config_path.unlink(missing_ok=True)
            else:
                config_path.write_text(existing_content, encoding="utf-8")
            raise

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] 初始化完成"))
        self.stdout.write(f"- 前端地址: {config.resolved_frontend_url() or 'http://localhost:5173'}")
        self.stdout.write(f"- 站点配置文件: {config_path}")
        if _running_in_docker():
            self.stdout.write("- 如果 web/celery 已经在运行，请执行 docker compose restart web celery 让新配置生效")

    def _resolve_config_path(self, raw_path: str) -> Path:
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

    def _build_site_config(
        self,
        database: str,
        options: Dict[str, str],
        existing_config: SiteBootstrapConfig | None = None,
    ) -> SiteBootstrapConfig:
        site_domains_input = options.get("site_domains")
        site_domains = (
            [item.strip() for item in site_domains_input.split(",") if item.strip()]
            if site_domains_input is not None
            else list(existing_config.site_domains) if existing_config else []
        )
        site_scheme = options.get("site_scheme") or (
            existing_config.site_scheme if existing_config else ("http" if database == "sqlite" else "https")
        )
        docker_defaults = _running_in_docker()
        frontend_default = (
            ""
            if site_domains_input is not None
            else existing_config.frontend_url
            if existing_config and existing_config.frontend_url
            else "http://localhost:5173" if database == "sqlite" else ""
        )

        db_host_default = "db" if docker_defaults else "localhost"
        redis_host_default = "redis" if docker_defaults else "localhost"

        config = SiteBootstrapConfig(
            installed=True,
            source="file",
            debug=existing_config.debug if existing_config else database == "sqlite",
            secret_key=existing_config.secret_key if existing_config else get_random_secret_key(),
            jwt_secret_key=existing_config.jwt_secret_key if existing_config else get_random_secret_key(),
            site_domains=site_domains,
            site_scheme=site_scheme,
            frontend_url=(options.get("frontend_url") or _first_env("FRONTEND_URL", default=frontend_default)).strip(),
            database_mode=database,
            sqlite_name=options.get("sqlite_name") or (existing_config.sqlite_name if existing_config else "db.sqlite3"),
            db_engine=existing_config.db_engine if existing_config else "django.db.backends.postgresql",
            db_name=options.get("db_name") or (
                existing_config.db_name
                if existing_config else _first_env("BIAS_INSTALL_DB_NAME", "DB_NAME", "POSTGRES_DB", default="bias")
            ),
            db_user=options.get("db_user") or (
                existing_config.db_user
                if existing_config else _first_env("BIAS_INSTALL_DB_USER", "DB_USER", "POSTGRES_USER", default="postgres")
            ),
            db_password=options.get("db_password") or _first_env(
                "BIAS_INSTALL_DB_PASSWORD",
                "DB_PASSWORD",
                "POSTGRES_PASSWORD",
                default=existing_config.db_password if existing_config else "postgres",
            ),
            db_host=options.get("db_host") or _first_env(
                "BIAS_INSTALL_DB_HOST",
                "DB_HOST",
                default=existing_config.db_host if existing_config else db_host_default,
            ),
            db_port=options.get("db_port") or _first_env(
                "BIAS_INSTALL_DB_PORT",
                "DB_PORT",
                default=existing_config.db_port if existing_config else "5432",
            ),
            use_redis=self._resolve_redis_enabled(database, options.get("redis"), existing_config),
            redis_host=options.get("redis_host") or _first_env(
                "BIAS_INSTALL_REDIS_HOST",
                "REDIS_HOST",
                default=existing_config.redis_host if existing_config else redis_host_default,
            ),
            redis_port=options.get("redis_port") or _first_env(
                "BIAS_INSTALL_REDIS_PORT",
                "REDIS_PORT",
                default=existing_config.redis_port if existing_config else "6379",
            ),
            redis_db=options.get("redis_db") or _first_env(
                "BIAS_INSTALL_REDIS_DB",
                "REDIS_DB",
                default=existing_config.redis_db if existing_config else "0",
            ),
            celery_broker_url=existing_config.celery_broker_url if existing_config else "",
            celery_result_backend=existing_config.celery_result_backend if existing_config else "",
            email_backend=existing_config.email_backend if existing_config else "django.core.mail.backends.console.EmailBackend",
            email_host=existing_config.email_host if existing_config else "smtp.gmail.com",
            email_port=existing_config.email_port if existing_config else 587,
            email_use_tls=existing_config.email_use_tls if existing_config else True,
            email_host_user=existing_config.email_host_user if existing_config else "",
            email_host_password=existing_config.email_host_password if existing_config else "",
            default_from_email=existing_config.default_from_email if existing_config else "noreply@bias.local",
            media_url=existing_config.media_url if existing_config else "/media/",
            static_url=existing_config.static_url if existing_config else "/static/",
        )
        config.frontend_url = config.resolved_frontend_url()
        return config

    def _resolve_redis_enabled(
        self,
        database: str,
        redis_mode: str | None,
        existing_config: SiteBootstrapConfig | None = None,
    ) -> bool:
        if redis_mode == "on":
            return True
        if redis_mode == "off":
            return False
        if existing_config is not None:
            return existing_config.use_redis
        return database == "postgres"

    def _build_admin_command_args(self, options: Dict[str, str], non_interactive: bool) -> list[str]:
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

        return [
            "--username",
            username,
            "--email",
            email,
            "--password",
            password,
        ]

    def _run_manage_step(self, label: str, args: list[str], env: Dict[str, str]) -> None:
        self.stdout.write(f"执行{label}...")
        try:
            result = run_manage_py(args, env)
        except Exception as exc:
            stdout = getattr(exc, "stdout", "")
            stderr = getattr(exc, "stderr", "")
            if stdout:
                self.stdout.write(stdout.rstrip())
            if stderr:
                self.stderr.write(stderr.rstrip())
            raise CommandError(f"{label}失败，请检查数据库、Redis 和站点配置后重试") from exc

        if result.stdout:
            self.stdout.write(result.stdout.rstrip())
        if result.stderr:
            self.stderr.write(result.stderr.rstrip())
