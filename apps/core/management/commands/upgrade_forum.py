from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.bootstrap_config import (
    DEFAULT_SITE_CONFIG_PATH,
    SiteBootstrapConfig,
    load_site_bootstrap,
    read_site_config,
    write_site_config,
)
from apps.core.management.command_utils import build_manage_env, run_manage_py


def _env_flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "执行论坛版本升级：系统检查、迁移、默认组同步、版本同步与缓存清理。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--config",
            default=str(DEFAULT_SITE_CONFIG_PATH),
            help="站点配置文件路径，默认读取 instance/site.json",
        )
        parser.add_argument("--skip-check", action="store_true", help="跳过 Django 系统检查")
        parser.add_argument("--skip-migrate", action="store_true", help="跳过数据库迁移")
        parser.add_argument("--skip-init-groups", action="store_true", help="跳过默认用户组与权限同步")
        parser.add_argument("--skip-clear-cache", action="store_true", help="跳过运行时缓存清理")
        parser.add_argument("--skip-collectstatic", action="store_true", help="跳过静态资源收集")
        parser.add_argument("--collectstatic", action="store_true", help="兼容旧参数；当前默认会执行 collectstatic")
        parser.add_argument("--dry-run", action="store_true", help="只输出升级计划，不实际执行")
        parser.add_argument("--non-interactive", action="store_true", help="不询问备份确认，直接执行")

    def handle(self, *args, **options):
        config_path = self._resolve_config_path(options["config"])
        config = self._ensure_site_config(config_path)
        self._validate_config(config)

        self.stdout.write(self.style.MIGRATE_HEADING("开始升级 Bias"))
        self.stdout.write(f"站点配置: {config_path}")
        self.stdout.write(f"数据库模式: {config.database_mode}")
        self.stdout.write(f"Redis: {'开启' if config.use_redis else '关闭'}")

        self._confirm_backup(options, config_path, config.database_mode)

        steps: list[tuple[str, list[str]]] = []
        if not options["skip_check"]:
            steps.append(("Django 系统检查", ["check"]))
        if not options["skip_migrate"]:
            steps.append(("数据库迁移", ["migrate", "--noinput"]))
        if not options["skip_init_groups"]:
            steps.append(("默认用户组与权限同步", ["init_groups"]))
        steps.append(("写入安装版本", ["sync_forum_version"]))
        if not options["skip_clear_cache"]:
            steps.append(("运行时缓存清理", ["clear_runtime_cache"]))
        if not options["skip_collectstatic"]:
            steps.append(("静态资源收集", ["collectstatic", "--noinput"]))

        self.stdout.write("升级计划:")
        for label, args in steps:
            self.stdout.write(f"- {label}: python manage.py {' '.join(args)}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("[DRY-RUN] 仅输出计划，未执行任何升级步骤"))
            return

        command_env = build_manage_env(config_path=config_path)
        for label, args in steps:
            self._run_manage_step(label, args, command_env)

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] 升级完成"))
        self.stdout.write("- 建议确认首页、后台、登录与发帖链路是否正常")

    def _resolve_config_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        return path

    def _ensure_site_config(self, config_path: Path) -> SiteBootstrapConfig:
        if config_path.exists():
            return read_site_config(config_path)

        bootstrap = load_site_bootstrap(settings.BASE_DIR)
        if bootstrap.source != "env":
            raise CommandError(f"站点配置不存在: {config_path}。请先执行 python manage.py install_forum")

        write_site_config(config_path, bootstrap)
        self.stdout.write(self.style.WARNING(f"[MIGRATE] 已将旧版环境配置迁移到: {config_path}"))
        return read_site_config(config_path)

    def _validate_config(self, config: SiteBootstrapConfig) -> None:
        db_mode = (config.database_mode or "sqlite").strip().lower()
        if db_mode not in {"sqlite", "sqlite3", "postgres", "postgresql"}:
            raise CommandError(f"站点配置中的 database_mode 无效: {config.database_mode}")

        normalized = "sqlite" if db_mode.startswith("sqlite") else "postgres"
        if normalized == "sqlite":
            if not (config.sqlite_name or "").strip():
                raise CommandError("SQLite 模式下必须提供 sqlite_name")
        else:
            missing = [
                field for field, value in (
                    ("db_name", config.db_name),
                    ("db_user", config.db_user),
                    ("db_host", config.db_host),
                    ("db_port", config.db_port),
                )
                if not (value or "").strip()
            ]
            if missing:
                raise CommandError(f"PostgreSQL 模式缺少必要配置: {', '.join(missing)}")

        if _env_flag(str(config.use_redis), default=normalized == "postgres"):
            missing_redis = [
                field for field, value in (
                    ("redis_host", config.redis_host),
                    ("redis_port", config.redis_port),
                )
                if not (value or "").strip()
            ]
            if missing_redis:
                raise CommandError(f"Redis 已启用，但缺少配置: {', '.join(missing_redis)}")

    def _confirm_backup(self, options: dict, config_path: Path, db_mode: str) -> None:
        if options["dry_run"] or options["non_interactive"]:
            return

        answer = input(
            f"升级前请确认已备份 {config_path.name}、media/ 和 {'数据库文件' if db_mode == 'sqlite' else 'PostgreSQL 数据库'} [y/N]: "
        ).strip().lower()
        if answer not in {"y", "yes"}:
            raise CommandError("已取消升级，请先完成备份后再执行")

    def _run_manage_step(self, label: str, args: list[str], env: dict[str, str]) -> None:
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
            raise CommandError(f"{label}失败。请先检查数据库、Redis 和站点配置；如已备份，可恢复后重试") from exc

        if result.stdout:
            self.stdout.write(result.stdout.rstrip())
        if result.stderr:
            self.stderr.write(result.stderr.rstrip())
