from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values
from django.conf import settings
from django.core.management import BaseCommand, CommandError
from django.core.management.base import CommandParser

from apps.core.management.command_utils import build_manage_env, run_manage_py


def _env_flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Command(BaseCommand):
    help = "执行论坛版本升级：环境检查、迁移、默认组同步与缓存清理。"

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--env-file", default=".env", help="环境文件路径，默认读取项目根目录 .env")
        parser.add_argument("--skip-check", action="store_true", help="跳过 Django 系统检查")
        parser.add_argument("--skip-migrate", action="store_true", help="跳过数据库迁移")
        parser.add_argument("--skip-init-groups", action="store_true", help="跳过默认用户组与权限同步")
        parser.add_argument("--skip-clear-cache", action="store_true", help="跳过运行时缓存清理")
        parser.add_argument("--collectstatic", action="store_true", help="升级后执行 collectstatic")
        parser.add_argument("--dry-run", action="store_true", help="只输出升级计划，不实际执行")
        parser.add_argument("--non-interactive", action="store_true", help="不询问备份确认，直接执行")

    def handle(self, *args, **options):
        env_path = self._resolve_env_path(options["env_file"])
        env_values = self._load_env_values(env_path)
        db_mode = self._validate_env_values(env_path, env_values)
        use_redis = _env_flag(env_values.get("USE_REDIS"), default=db_mode == "postgres")

        self.stdout.write(self.style.MIGRATE_HEADING("开始升级 Bias"))
        self.stdout.write(f"环境文件: {env_path}")
        self.stdout.write(f"数据库模式: {db_mode}")
        self.stdout.write(f"Redis: {'开启' if use_redis else '关闭'}")

        self._confirm_backup(options, env_path, db_mode)

        steps: list[tuple[str, list[str]]] = []
        if not options["skip_check"]:
            steps.append(("Django 系统检查", ["check"]))
        if not options["skip_migrate"]:
            steps.append(("数据库迁移", ["migrate", "--noinput"]))
        if not options["skip_init_groups"]:
            steps.append(("默认用户组与权限同步", ["init_groups"]))
        if not options["skip_clear_cache"]:
            steps.append(("运行时缓存清理", ["clear_runtime_cache"]))
        if options["collectstatic"]:
            steps.append(("静态资源收集", ["collectstatic", "--noinput"]))

        self.stdout.write("升级计划:")
        for label, args in steps:
            self.stdout.write(f"- {label}: python manage.py {' '.join(args)}")

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS("[DRY-RUN] 仅输出计划，未执行任何升级步骤"))
            return

        command_env = build_manage_env(env_values, env_path)
        for label, args in steps:
            self._run_manage_step(label, args, command_env)

        self.stdout.write(self.style.SUCCESS("\n[SUCCESS] 升级完成"))
        self.stdout.write("- 建议确认站点首页、后台仪表盘、审核队列和标签页是否可正常访问")
        self.stdout.write("- 若前端资源有改动，请同步执行 npm install / npm run build 或重启前端开发服务")

    def _resolve_env_path(self, raw_path: str) -> Path:
        path = Path(raw_path)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        return path

    def _load_env_values(self, env_path: Path) -> dict[str, str]:
        if not env_path.exists():
            raise CommandError(f"环境文件不存在: {env_path}")

        values = {
            key: value
            for key, value in dotenv_values(env_path).items()
            if value is not None
        }
        return {key: str(value) for key, value in values.items()}

    def _validate_env_values(self, env_path: Path, env_values: dict[str, str]) -> str:
        db_mode = (env_values.get("DB_MODE") or "sqlite").strip().lower()
        if db_mode not in {"sqlite", "sqlite3", "postgres", "postgresql"}:
            raise CommandError(f"环境文件中的 DB_MODE 无效: {env_path}")

        normalized = "sqlite" if db_mode.startswith("sqlite") else "postgres"
        if normalized == "sqlite":
            if not (env_values.get("SQLITE_NAME") or "").strip():
                raise CommandError("SQLite 模式下必须提供 SQLITE_NAME")
        else:
            missing = [key for key in ("DB_NAME", "DB_USER", "DB_HOST", "DB_PORT") if not (env_values.get(key) or "").strip()]
            if missing:
                raise CommandError(f"PostgreSQL 模式缺少必要配置: {', '.join(missing)}")

        if _env_flag(env_values.get("USE_REDIS"), default=normalized == "postgres"):
            missing_redis = [key for key in ("REDIS_HOST", "REDIS_PORT") if not (env_values.get(key) or "").strip()]
            if missing_redis:
                raise CommandError(f"Redis 已启用，但缺少配置: {', '.join(missing_redis)}")

        return normalized

    def _confirm_backup(self, options: dict, env_path: Path, db_mode: str) -> None:
        if options["dry_run"] or options["non_interactive"]:
            return

        answer = input(
            f"升级前请确认已备份 {env_path.name}、media/ 和 {'数据库文件' if db_mode == 'sqlite' else 'PostgreSQL 数据库'} [y/N]: "
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
            raise CommandError(
                f"{label}失败。请先检查依赖安装、环境变量和数据库状态；如已执行备份，可按备份方案恢复后重试"
            ) from exc

        if result.stdout:
            self.stdout.write(result.stdout.rstrip())
        if result.stderr:
            self.stderr.write(result.stderr.rstrip())
