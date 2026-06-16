from __future__ import annotations

import json
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
from apps.core.models import Setting


def _running_in_docker() -> bool:
    return Path("/.dockerenv").exists()


def _first_env(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key)
        if value is not None and value.strip():
            return value.strip()
    return ""


def _build_db_connection_mismatch_message(
    config: SiteBootstrapConfig,
    *,
    missing_role: bool = False,
    auth_failed: bool = False,
    missing_database: bool = False,
) -> str:
    details = (
        f" 当前尝试连接的配置是 db_name={config.db_name}, db_user={config.db_user},"
        f" db_host={config.db_host}, db_port={config.db_port}。"
    )

    if _running_in_docker():
        if missing_role:
            return (
                "数据库连接预检查失败。PostgreSQL 中不存在当前配置的用户。"
                f"{details}"
                " 如果你是首次安装但遇到这个错误，通常说明 Docker 复用了旧的 postgres_data 卷，"
                " 数据库并不是按当前 .env 初始化的。"
                " 无需保留数据时请执行 `docker compose down -v` 后重新 `docker compose up -d --build`；"
                " 如需保留数据，请让 .env 中的 DB_NAME/DB_USER/DB_PASSWORD 与现有 PostgreSQL 实例保持一致。"
            )
        if auth_failed or missing_database:
            return (
                "数据库连接预检查失败。当前 PostgreSQL 凭据与容器内实际数据库状态不一致。"
                f"{details}"
                " 如果你是首次安装但这台机器或这个目录之前跑过 Bias，很可能是旧的 postgres_data 卷仍在使用旧账号、旧密码或旧数据库名。"
                " 无需保留数据时请执行 `docker compose down -v` 后重新 `docker compose up -d --build`；"
                " 如需保留数据，请让 .env 中的 DB_NAME/DB_USER/DB_PASSWORD 与现有 PostgreSQL 实例保持一致。"
            )
    else:
        if missing_role:
            return (
                "数据库连接预检查失败。PostgreSQL 中不存在当前配置的用户。"
                f"{details}"
                " 请先在 PostgreSQL 中创建对应用户，或改用实际存在的 --db-user/--db-password。"
            )
        if auth_failed:
            return (
                "数据库连接预检查失败。PostgreSQL 用户名或密码不正确。"
                f"{details}"
                " 请确认 --db-user/--db-password 与目标 PostgreSQL 实例一致。"
            )
        if missing_database:
            return (
                "数据库连接预检查失败。PostgreSQL 中不存在当前配置的数据库。"
                f"{details}"
                " 请先创建对应数据库，或改用实际存在的 --db-name。"
            )

    return f"数据库连接预检查失败。{details}"


def assert_database_connection(config: SiteBootstrapConfig) -> None:
    db_mode = (config.database_mode or "sqlite").strip().lower()
    if db_mode.startswith("sqlite"):
        return

    import psycopg2

    try:
        connection = psycopg2.connect(
            dbname=config.db_name,
            user=config.db_user,
            password=config.db_password,
            host=config.db_host,
            port=config.db_port,
            connect_timeout=5,
        )
    except psycopg2.OperationalError as exc:
        raw_message = str(exc).strip()
        lowered = raw_message.lower()

        if "role" in lowered and "does not exist" in lowered:
            raise CommandError(_build_db_connection_mismatch_message(config, missing_role=True)) from exc

        if "password authentication failed" in lowered:
            raise CommandError(_build_db_connection_mismatch_message(config, auth_failed=True)) from exc

        if "database" in lowered and "does not exist" in lowered:
            raise CommandError(_build_db_connection_mismatch_message(config, missing_database=True)) from exc

        raise CommandError(f"数据库连接预检查失败: {raw_message}") from exc
    else:
        connection.close()


class Command(BaseCommand):
    help = "初始化论坛：写入站点配置、执行迁移、同步扩展、初始化默认用户组并创建管理员。"

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
        parser.add_argument("--skip-sync-extensions", action="store_true", help="跳过同步扩展安装记录")
        parser.add_argument("--skip-extension-migrations", action="store_true", help="跳过同步扩展迁移摘要")
        parser.add_argument("--skip-extension-frontend", action="store_true", help="跳过生成扩展前端构建清单")
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
        parser.add_argument("--email-backend", help="Django 邮件后端")
        parser.add_argument("--email-host", help="SMTP 主机")
        parser.add_argument("--email-port", type=int, help="SMTP 端口")
        parser.add_argument("--email-use-tls", choices=["auto", "on", "off"], default="auto", help="是否启用 SMTP TLS")
        parser.add_argument("--email-host-user", help="SMTP 用户名")
        parser.add_argument("--email-host-password", help="SMTP 密码")
        parser.add_argument("--default-from-email", help="默认发件人邮箱")
        parser.add_argument("--non-interactive", action="store_true", help="使用非交互模式执行")

    def handle(self, *args, **options):
        non_interactive = bool(options["non_interactive"])
        config_path = self._resolve_config_path(options["config"])
        existing_content = config_path.read_text(encoding="utf-8") if config_path.exists() else None
        existing_config = read_site_config(config_path) if config_path.exists() else None

        if existing_content is not None and not options["overwrite"]:
            raise CommandError(f"站点配置已存在: {config_path}。如需覆盖，请显式传入 --overwrite")

        database = options.get("database") or (
            existing_config.database_mode if existing_config else self._prompt_database(non_interactive)
        )
        config = self._build_site_config(database, options, existing_config)
        self._validate_config(config)
        assert_database_connection(config)

        self.stdout.write(self.style.MIGRATE_HEADING("开始初始化 Bias"))
        self.stdout.write(f"站点配置: {config_path}")
        self.stdout.write(f"数据库模式: {config.database_mode}")
        self.stdout.write(f"Redis: {'开启' if config.use_redis else '关闭'}")
        self.stdout.write(
            f"站点域名: {', '.join(config.site_domains) if config.site_domains else '未配置，保持本地默认'}"
        )

        write_site_config(config_path, config)
        install_settings = self._build_advanced_runtime_defaults(config)
        command_env = build_manage_env({"BIAS_INSTALLING": "1"}, config_path=config_path)

        try:
            if not options["skip_migrate"]:
                self._run_manage_step("数据库迁移", ["migrate", "--noinput"], command_env)
            else:
                self.stdout.write("[SKIP] 已跳过 migrate")

            self._write_install_settings(install_settings)

            if not options["skip_sync_extensions"]:
                self._run_manage_step("扩展状态同步", ["sync_extensions"], command_env)
            else:
                self.stdout.write("[SKIP] 已跳过 sync_extensions")

            if not options["skip_extension_migrations"]:
                self._run_manage_step("扩展迁移摘要同步", ["migrate_extensions", "--all"], command_env)
            else:
                self.stdout.write("[SKIP] 已跳过 migrate_extensions --all")

            self._run_manage_step("默认用户组与权限初始化", ["init_groups"], command_env)
            self._run_manage_step("写入安装版本", ["sync_forum_version"], command_env)

            if not options["skip_extension_frontend"]:
                self._run_manage_step("扩展前端构建清单生成", ["build_extension_frontend"], command_env)
            else:
                self.stdout.write("[SKIP] 已跳过 build_extension_frontend")

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

        db_name_default = ""
        db_user_default = ""
        db_password_default = ""
        db_host_default = "db" if docker_defaults else "localhost"
        db_port_default = "5432"
        redis_host_default = "redis" if docker_defaults else "localhost"

        config = SiteBootstrapConfig(
            installed=True,
            source="file",
            debug=existing_config.debug if existing_config else database == "sqlite",
            secret_key=existing_config.secret_key if existing_config else get_random_secret_key(),
            jwt_secret_key=existing_config.jwt_secret_key if existing_config else get_random_secret_key(),
            site_domains=site_domains,
            site_scheme=site_scheme,
            frontend_url=(options.get("frontend_url") or frontend_default).strip(),
            database_mode=database,
            sqlite_name=options.get("sqlite_name") or (existing_config.sqlite_name if existing_config else "db.sqlite3"),
            db_engine=existing_config.db_engine if existing_config else "django.db.backends.postgresql",
            db_name=options.get("db_name") or (
                existing_config.db_name if existing_config else _first_env("DB_NAME") or db_name_default
            ),
            db_user=options.get("db_user") or (
                existing_config.db_user if existing_config else _first_env("DB_USER") or db_user_default
            ),
            db_password=options.get("db_password") or (
                existing_config.db_password if existing_config else _first_env("DB_PASSWORD") or db_password_default
            ),
            db_host=options.get("db_host") or (
                existing_config.db_host if existing_config else _first_env("DB_HOST") or db_host_default
            ),
            db_port=options.get("db_port") or (
                existing_config.db_port if existing_config else _first_env("DB_PORT") or db_port_default
            ),
            use_redis=self._resolve_redis_enabled(database, options.get("redis"), existing_config),
            redis_host=options.get("redis_host") or (
                existing_config.redis_host if existing_config else _first_env("REDIS_HOST") or redis_host_default
            ),
            redis_port=options.get("redis_port") or (
                existing_config.redis_port if existing_config else _first_env("REDIS_PORT") or "6379"
            ),
            redis_db=options.get("redis_db") or (
                existing_config.redis_db if existing_config else _first_env("REDIS_DB") or "0"
            ),
            celery_broker_url=existing_config.celery_broker_url if existing_config else "",
            celery_result_backend=existing_config.celery_result_backend if existing_config else "",
            email_backend=options.get("email_backend") or (
                existing_config.email_backend
                if existing_config
                else _first_env("EMAIL_BACKEND") or "django.core.mail.backends.console.EmailBackend"
            ),
            email_host=options.get("email_host") or (
                existing_config.email_host if existing_config else _first_env("EMAIL_HOST") or "smtp.gmail.com"
            ),
            email_port=options.get("email_port") or (
                existing_config.email_port if existing_config else int(_first_env("EMAIL_PORT") or 587)
            ),
            email_use_tls=self._resolve_email_use_tls(options.get("email_use_tls"), existing_config),
            email_host_user=options.get("email_host_user") or (
                existing_config.email_host_user if existing_config else _first_env("EMAIL_HOST_USER")
            ),
            email_host_password=options.get("email_host_password") or (
                existing_config.email_host_password if existing_config else _first_env("EMAIL_HOST_PASSWORD")
            ),
            default_from_email=options.get("default_from_email") or (
                existing_config.default_from_email
                if existing_config
                else _first_env("DEFAULT_FROM_EMAIL") or "noreply@bias.local"
            ),
            media_url=existing_config.media_url if existing_config else "/media/",
            static_url=existing_config.static_url if existing_config else "/static/",
        )
        config.frontend_url = config.resolved_frontend_url()
        return config

    def _validate_config(self, config: SiteBootstrapConfig) -> None:
        db_mode = (config.database_mode or "sqlite").strip().lower()
        normalized = "sqlite" if db_mode.startswith("sqlite") else "postgres"

        if normalized == "sqlite":
            if not (config.sqlite_name or "").strip():
                raise CommandError("SQLite 模式下必须提供 --sqlite-name 或有效默认值")
            return

        missing = [
            field for field, value in (
                ("db_name", config.db_name),
                ("db_user", config.db_user),
                ("db_password", config.db_password),
                ("db_host", config.db_host),
                ("db_port", config.db_port),
            )
            if not (value or "").strip()
        ]
        if missing:
            raise CommandError(f"PostgreSQL 模式缺少必要配置: {', '.join(missing)}")

        # Postgres 生产模式下，console 邮件后端会导致 startup_guard 拒绝启动，
        # 提醒用户通过 EMAIL_BACKEND 环境变量或 --email-backend 参数配置真实邮件后端
        if "console" in (config.email_backend or ""):
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  生产模式(postgres)下邮件后端仍为 console，启动自检会拒绝启动。\n"
                    "    请设置环境变量 EMAIL_BACKEND=smtp 或通过 --email-backend 参数指定。\n"
                    "    安装阶段已通过 BIAS_INSTALLING 标志暂时放行，但安装完成后必须配置。"
                )
            )

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

    def _resolve_email_use_tls(
        self,
        email_use_tls: str | None,
        existing_config: SiteBootstrapConfig | None = None,
    ) -> bool:
        if email_use_tls == "on":
            return True
        if email_use_tls == "off":
            return False
        if existing_config is not None:
            return existing_config.email_use_tls
        raw_env = _first_env("EMAIL_USE_TLS")
        if raw_env:
            return raw_env.lower() in {"1", "true", "yes", "on"}
        return True

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

    def _build_advanced_runtime_defaults(self, config: SiteBootstrapConfig) -> dict[str, str]:
        if config.database_mode != "postgres" or not config.use_redis:
            return {}
        return {
            "advanced.queue_enabled": json.dumps(True, ensure_ascii=False),
            "advanced.queue_driver": json.dumps("redis", ensure_ascii=False),
        }

    def _write_install_settings(self, settings_map: dict[str, str]) -> None:
        for key, value in settings_map.items():
            Setting.objects.update_or_create(key=key, defaults={"value": value})

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
