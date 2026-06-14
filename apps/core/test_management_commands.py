from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from apps.core.bootstrap_config import read_site_config
from apps.core.release import build_git_command, ensure_release_versions_aligned


def make_workspace_temp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix=f"bias-test-{uuid.uuid4().hex}-"))


class InstallForumCommandTests(TestCase):
    def _success_result(self, args):
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_writes_site_config_and_invokes_manage_steps(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "sqlite",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--admin-username",
                        "forum-admin",
                        "--admin-email",
                        "forum-admin@example.com",
                        "--admin-password",
                        "password123",
                        "--non-interactive",
                    )

            self.assertTrue(config_path.exists())
            config = read_site_config(config_path)
            self.assertEqual(config.database_mode, "sqlite")
            self.assertEqual(config.sqlite_name, "db.sqlite3")
            self.assertFalse(config.use_redis)
            self.assertEqual(config.resolved_frontend_url(), "http://localhost:5173")
            self.assertTrue(config.secret_key)
            self.assertTrue(config.jwt_secret_key)

            self.assertEqual(mock_run_manage_py.call_count, 7)
            invoked_steps = [call.args[0] for call in mock_run_manage_py.call_args_list]
            self.assertEqual(
                invoked_steps,
                [
                    ["sync_extensions"],
                    ["migrate_extensions", "--all"],
                    ["init_groups"],
                    ["sync_forum_version"],
                    ["build_extension_frontend"],
                    ["collectstatic", "--noinput"],
                    [
                        "ensure_admin",
                        "--username",
                        "forum-admin",
                        "--email",
                        "forum-admin@example.com",
                        "--password",
                        "password123",
                    ],
                ],
            )

            first_args, first_env = mock_run_manage_py.call_args_list[0].args
            self.assertEqual(first_args, ["sync_extensions"])
            self.assertEqual(
                first_env["BIAS_SITE_CONFIG"],
                str(config_path),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_writes_postgres_site_config_values(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--skip-admin",
                        "--db-name",
                        "community",
                        "--db-user",
                        "community_user",
                        "--db-password",
                        "community_pass",
                        "--db-host",
                        "db.internal",
                        "--db-port",
                        "5433",
                        "--frontend-url",
                        "http://forum.example.com",
                        "--non-interactive",
                    )

            self.assertTrue(config_path.exists())
            config = read_site_config(config_path)
            self.assertEqual(config.database_mode, "postgres")
            self.assertFalse(config.debug)
            self.assertTrue(config.use_redis)
            self.assertEqual(config.db_name, "community")
            self.assertEqual(config.db_user, "community_user")
            self.assertEqual(config.db_password, "community_pass")
            self.assertEqual(config.db_host, "db.internal")
            self.assertEqual(config.db_port, "5433")
            self.assertEqual(config.resolved_frontend_url(), "http://forum.example.com")

            self.assertEqual(mock_run_manage_py.call_count, 6)
            group_args, group_env = mock_run_manage_py.call_args_list[2].args
            self.assertEqual(group_args, ["init_groups"])
            self.assertEqual(group_env["BIAS_SITE_CONFIG"], str(config_path))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_allows_explicit_redis_override(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "sqlite",
                        "--redis",
                        "on",
                        "--redis-host",
                        "cache.internal",
                        "--redis-port",
                        "6380",
                        "--redis-db",
                        "5",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )

            config = read_site_config(config_path)
            self.assertTrue(config.use_redis)
            self.assertEqual(config.redis_host, "cache.internal")
            self.assertEqual(config.redis_port, "6380")
            self.assertEqual(config.redis_db, "5")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_overwrite_preserves_existing_secrets(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "secret_key": "secret-1",
                        "jwt_secret_key": "jwt-secret-1",
                        "database_mode": "postgres",
                        "db_name": "bias",
                        "db_user": "postgres",
                        "db_password": "postgres",
                        "db_host": "db",
                        "db_port": "5432",
                        "use_redis": True,
                        "redis_host": "redis",
                        "redis_port": "6379",
                        "redis_db": "0",
                        "site_domains": ["old.example.com"],
                        "site_scheme": "https",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command(
                    "install_forum",
                    "--config",
                    str(config_path),
                    "--site-domains",
                    "bias.chat,www.bias.chat",
                    "--skip-migrate",
                    "--skip-admin",
                    "--overwrite",
                    "--non-interactive",
                )

            config = read_site_config(config_path)
            self.assertEqual(config.secret_key, "secret-1")
            self.assertEqual(config.jwt_secret_key, "jwt-secret-1")
            self.assertEqual(config.site_domains, ["bias.chat", "www.bias.chat"])
            self.assertEqual(config.db_host, "db")
            self.assertEqual(config.resolved_frontend_url(), "https://bias.chat")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_install_forum_validates_postgres_required_fields(self):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaisesMessage(
                CommandError,
                "PostgreSQL 模式缺少必要配置: db_name, db_user, db_password",
            ):
                with patch.dict(
                    os.environ,
                    {
                        "DB_NAME": "",
                        "DB_USER": "",
                        "DB_PASSWORD": "",
                        "BIAS_SITE_CONFIG": "",
                    },
                    clear=False,
                ), override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--db-host",
                        "db.internal",
                        "--db-port",
                        "5432",
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=True)
    def test_install_forum_surfaces_old_volume_hint_when_role_missing(self, mock_running_in_docker, mock_connect):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  role "woniu" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(
                os.environ,
                {
                    "DB_NAME": "bias",
                    "DB_USER": "woniu",
                    "DB_PASSWORD": "woniu@woniu",
                },
                clear=False,
            ):
                with self.assertRaisesMessage(CommandError, "Docker 复用了旧的 postgres_data 卷"):
                    with override_settings(BASE_DIR=Path(temp_dir)):
                        call_command(
                            "install_forum",
                            "--database",
                            "postgres",
                            "--config",
                            str(config_path),
                            "--db-host",
                            "db",
                            "--db-port",
                            "5432",
                            "--skip-migrate",
                            "--skip-admin",
                            "--non-interactive",
                        )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=False)
    def test_install_forum_surfaces_native_postgres_hint_when_role_missing(
        self,
        mock_running_in_docker,
        mock_connect,
    ):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  role "bias_user" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaises(CommandError) as captured:
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--db-name",
                        "bias",
                        "--db-user",
                        "bias_user",
                        "--db-password",
                        "secret",
                        "--db-host",
                        "127.0.0.1",
                        "--db-port",
                        "5432",
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )

            message = str(captured.exception)
            self.assertIn("请先在 PostgreSQL 中创建对应用户", message)
            self.assertNotIn("postgres_data", message)
            self.assertNotIn(".env", message)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=True)
    def test_install_forum_surfaces_old_volume_hint_when_database_missing(
        self,
        mock_running_in_docker,
        mock_connect,
    ):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  database "bias" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(
                os.environ,
                {
                    "DB_NAME": "bias",
                    "DB_USER": "woniu",
                    "DB_PASSWORD": "woniu@woniu",
                },
                clear=False,
            ):
                with self.assertRaises(CommandError) as captured:
                    with override_settings(BASE_DIR=Path(temp_dir)):
                        call_command(
                            "install_forum",
                            "--database",
                            "postgres",
                            "--config",
                            str(config_path),
                            "--db-host",
                            "db",
                            "--db-port",
                            "5432",
                            "--skip-migrate",
                            "--skip-admin",
                            "--non-interactive",
                        )

            message = str(captured.exception)
            self.assertIn("postgres_data 卷", message)
            self.assertIn("旧数据库名", message)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

class UpgradeForumCommandTests(TestCase):
    def _success_result(self, args):
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    @patch("apps.core.management.commands.upgrade_forum.ensure_release_versions_aligned")
    @patch("apps.core.management.commands.upgrade_forum.run_manage_py")
    def test_upgrade_forum_runs_default_upgrade_steps(self, mock_run_manage_py, mock_ensure_versions):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_ensure_versions.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "upgrade_forum",
                "--config",
                str(config_path),
                "--non-interactive",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(mock_run_manage_py.call_count, 9)
        invoked_steps = [call.args[0] for call in mock_run_manage_py.call_args_list]
        self.assertEqual(
            invoked_steps,
            [
                ["check"],
                ["migrate", "--noinput"],
                ["sync_extensions"],
                ["migrate_extensions", "--all"],
                ["init_groups"],
                ["sync_forum_version"],
                ["clear_runtime_cache"],
                ["build_extension_frontend"],
                ["collectstatic", "--noinput"],
            ],
        )
        self.assertEqual(mock_run_manage_py.call_args_list[0].args[1]["BIAS_SITE_CONFIG"], str(config_path))

    @patch(
        "apps.core.management.commands.upgrade_forum.ensure_release_versions_aligned",
        side_effect=ValueError("版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致"),
    )
    def test_upgrade_forum_requires_aligned_release_versions(self, mock_ensure_versions):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(
                CommandError,
                "版本校验失败: 版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致",
            ):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.upgrade_forum.run_manage_py")
    def test_upgrade_forum_dry_run_does_not_execute_steps(self, mock_run_manage_py):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "upgrade_forum",
                "--config",
                str(config_path),
                "--dry-run",
                "--non-interactive",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        mock_run_manage_py.assert_not_called()

    def test_upgrade_forum_requires_existing_site_config(self):
        temp_dir = make_workspace_temp_dir()
        try:
            missing_config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaisesMessage(CommandError, f"站点配置不存在: {missing_config_path}。请先执行 python manage.py install_forum"):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(missing_config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_upgrade_forum_validates_postgres_required_fields(self):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "postgres",
                        "db_name": "",
                        "db_user": "",
                        "db_host": "",
                        "db_port": "",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "PostgreSQL 模式缺少必要配置: db_name, db_user, db_host, db_port"):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ReleaseVersionControlTests(TestCase):
    def test_ensure_release_versions_aligned_raises_when_version_mismatch(self):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(
                ValueError,
                "版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致",
            ):
                ensure_release_versions_aligned(base_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.prepare_release.subprocess.run")
    def test_prepare_release_syncs_version_and_frontend_package_files(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout="",
            stderr="",
        )

        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps(
                    {
                        "name": "bias-frontend",
                        "version": "1.0.0",
                        "packages": {
                            "": {
                                "name": "bias-frontend",
                                "version": "1.0.0",
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            with patch("apps.core.management.commands.prepare_release.call_command") as validate_mock, patch(
                "apps.core.management.commands.prepare_release.Command._inspect_extensions"
            ) as inspect_mock:
                inspect_mock.return_value = {
                    "summary": {
                        "attention_count": 0,
                    },
                    "extensions": [],
                }
                with override_settings(BASE_DIR=base_dir):
                    call_command("prepare_release", "--tag", "v1.2.3")
                validate_mock.assert_called_once_with("validate_extensions", "--strict", "--internal")

            self.assertEqual((base_dir / "VERSION").read_text(encoding="utf-8").strip(), "1.2.3")
            package_json = json.loads((base_dir / "frontend" / "package.json").read_text(encoding="utf-8"))
            package_lock = json.loads((base_dir / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
            self.assertEqual(package_json["version"], "1.2.3")
            self.assertEqual(package_lock["version"], "1.2.3")
            self.assertEqual(package_lock["packages"][""]["version"], "1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_prepare_release_rejects_mismatched_version_and_tag(self):
        with self.assertRaisesMessage(CommandError, "--set-version 与 --tag 不一致"):
            call_command("prepare_release", "--set-version", "1.0.1", "--tag", "v1.0.2", "--allow-dirty")

    def test_prepare_release_rejects_extension_attention_by_default(self):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0", "packages": {"": {"version": "1.0.0"}}}) + "\n",
                encoding="utf-8",
            )

            with patch("apps.core.management.commands.prepare_release.call_command") as validate_mock, patch(
                "apps.core.management.commands.prepare_release.Command._inspect_extensions"
            ) as inspect_mock:
                inspect_mock.return_value = {
                    "summary": {
                        "blocking_count": 2,
                        "warning_count": 0,
                        "attention_count": 2,
                    },
                    "extensions": [],
                }
                with override_settings(BASE_DIR=base_dir):
                    with self.assertRaisesMessage(CommandError, "扩展诊断存在 2 个阻断项"):
                        call_command("prepare_release", "--set-version", "1.0.0", "--allow-dirty")
                validate_mock.assert_called_once_with("validate_extensions", "--strict", "--internal")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_prepare_release_can_write_extension_report(self):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0", "packages": {"": {"version": "1.0.0"}}}) + "\n",
                encoding="utf-8",
            )
            report_path = base_dir / "artifacts" / "extensions-report.json"

            with patch("apps.core.management.commands.prepare_release.call_command") as validate_mock, patch(
                "apps.core.management.commands.prepare_release.Command._inspect_extensions"
            ) as inspect_mock:
                inspect_mock.return_value = {
                    "summary": {
                        "blocking_count": 0,
                        "warning_count": 0,
                        "attention_count": 0,
                        "asset_count": 5,
                        "frontend_bundle_count": 2,
                        "migration_bundle_count": 1,
                        "locale_bundle_count": 1,
                        "signed_extension_count": 0,
                    },
                    "extensions": [{"id": "core"}],
                }
                with override_settings(BASE_DIR=base_dir):
                    call_command(
                        "prepare_release",
                        "--set-version",
                        "1.0.0",
                        "--allow-dirty",
                        "--extension-report",
                        str(report_path),
                    )
                validate_mock.assert_called_once_with("validate_extensions", "--strict", "--internal")

            payload = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["attention_count"], 0)
            self.assertEqual(payload["summary"]["asset_count"], 5)
            self.assertEqual(payload["summary"]["frontend_bundle_count"], 2)
            self.assertEqual(payload["extensions"][0]["id"], "core")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.prepare_release.subprocess.run")
    def test_prepare_release_requires_clean_git_state_by_default(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout=" M README.md\n",
            stderr="",
        )
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0", "packages": {"": {"version": "1.0.0"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty",
                ):
                    call_command("prepare_release", "--set-version", "1.0.1")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_creates_git_tag_when_versions_match(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        base_dir = Path(temp_dir)
        mock_run.side_effect = [
            CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
            CompletedProcess(args=build_git_command(base_dir, "tag", "--list", "v1.2.3"), returncode=0, stdout="", stderr=""),
            CompletedProcess(
                args=build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
                returncode=0,
                stdout="",
                stderr="",
            ),
        ]
        try:
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                call_command("finalize_release", "--tag", "v1.2.3")

            self.assertEqual(
                mock_run.call_args_list[2].args[0],
                build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_rejects_mismatched_tag_and_version(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git tag 与代码版本不一致：tag=v1.2.4，VERSION=1.2.3",
                ):
                    call_command("finalize_release", "--tag", "v1.2.4", "--allow-dirty")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        mock_run.assert_not_called()

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_requires_clean_git_state_by_default(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout=" M VERSION\n",
            stderr="",
        )
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty",
                ):
                    call_command("finalize_release", "--tag", "v1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_rejects_existing_git_tag(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        base_dir = Path(temp_dir)
        mock_run.side_effect = [
            CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
            CompletedProcess(
                args=build_git_command(base_dir, "tag", "--list", "v1.2.3"),
                returncode=0,
                stdout="v1.2.3\n",
                stderr="",
            ),
        ]
        try:
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(CommandError, "Git tag 已存在: v1.2.3"):
                    call_command("finalize_release", "--tag", "v1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.publish_release.subprocess.run")
    @patch("apps.core.management.commands.publish_release.call_command")
    def test_publish_release_runs_prepare_then_finalize_in_dry_run(self, mock_call_command, mock_subprocess_run):
        call_command(
            "publish_release",
            "--set-version",
            "1.2.3",
            "--dry-run",
            "--allow-dirty",
            "--allow-extension-attention",
            "--extension-report",
            "artifacts/extensions.json",
        )

        self.assertEqual(
            [call.args for call in mock_call_command.call_args_list],
            [
                ("prepare_release", "--set-version", "1.2.3", "--tag", "v1.2.3", "--allow-dirty", "--allow-extension-attention", "--dry-run", "--extension-report", "artifacts/extensions.json"),
                ("finalize_release", "--tag", "v1.2.3", "--dry-run"),
            ],
        )
        mock_subprocess_run.assert_not_called()

    @patch("apps.core.management.commands.publish_release.subprocess.run")
    @patch("apps.core.management.commands.publish_release.call_command")
    def test_publish_release_commits_then_tags_and_pushes(self, mock_call_command, mock_subprocess_run):
        base_dir = settings.BASE_DIR
        call_command(
            "publish_release",
            "--set-version",
            "1.2.3",
            "--push",
        )

        self.assertEqual(
            [call.args for call in mock_call_command.call_args_list],
            [
                ("prepare_release", "--set-version", "1.2.3", "--tag", "v1.2.3"),
                ("finalize_release", "--tag", "v1.2.3"),
            ],
        )
        self.assertEqual(
            [call.args[0] for call in mock_subprocess_run.call_args_list],
            [
                build_git_command(base_dir, "add", "VERSION", "frontend/package.json", "frontend/package-lock.json"),
                build_git_command(base_dir, "commit", "-m", "发布 1.2.3"),
                build_git_command(base_dir, "push", "origin", "main", "--tags"),
            ],
        )

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_uses_safe_directory_git_commands(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )
            mock_run.side_effect = [
                CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
                CompletedProcess(args=build_git_command(base_dir, "tag", "--list", "v1.2.3"), returncode=0, stdout="", stderr=""),
                CompletedProcess(args=build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"), returncode=0, stdout="", stderr=""),
            ]

            with override_settings(BASE_DIR=base_dir):
                call_command("finalize_release", "--tag", "v1.2.3")

            self.assertEqual(mock_run.call_args_list[0].args[0], build_git_command(base_dir, "status", "--short"))
            self.assertEqual(mock_run.call_args_list[1].args[0], build_git_command(base_dir, "tag", "--list", "v1.2.3"))
            self.assertEqual(
                mock_run.call_args_list[2].args[0],
                build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

class DoctorCommandTests(TestCase):
    def test_doctor_command_reports_ok_payload_as_json(self):
        stdout = StringIO()

        call_command(
            "doctor",
            "--format",
            "json",
            "--skip-frontend",
            "--skip-extensions",
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["summary"]["error_count"], 0)
        check_names = {item["name"] for item in payload["checks"]}
        self.assertIn("runtime_status", check_names)
        self.assertIn("database", check_names)
        self.assertIn("migrations", check_names)
        self.assertIn("cache", check_names)

    @patch("apps.core.management.commands.doctor.MigrationExecutor")
    def test_doctor_command_fails_when_migrations_are_pending(self, executor_mock):
        migration = SimpleNamespace(app_label="core", name="9999_pending")
        executor = executor_mock.return_value
        executor.loader.graph.leaf_nodes.return_value = [("core", "9999_pending")]
        executor.migration_plan.return_value = [(migration, False)]

        with self.assertRaisesMessage(CommandError, "doctor 检查失败"):
            call_command(
                "doctor",
                "--skip-frontend",
                "--skip-extensions",
                stdout=StringIO(),
            )

    @patch("apps.core.management.commands.doctor.get_extension_manager")
    def test_doctor_command_reports_extension_drift(self, get_manager):
        manager = get_manager.return_value
        manager.inspect_extension_packages.return_value = {
            "summary": {
                "discovered_count": 1,
                "installed_count": 1,
                "installation_record_count": 1,
            },
            "missing": [],
            "version_drift": ["alpha-tools"],
            "source_drift": [],
            "unmanaged_discovered": [],
            "lock": {"stale_ids": []},
        }

        with self.assertRaisesMessage(CommandError, "doctor 检查失败"):
            call_command(
                "doctor",
                "--skip-frontend",
                stdout=StringIO(),
            )

    @patch("apps.core.management.commands.doctor.get_extension_manager")
    def test_doctor_command_warns_when_extension_installation_records_drift(self, get_manager):
        manager = get_manager.return_value
        manager.inspect_extension_packages.return_value = {
            "summary": {
                "discovered_count": 2,
                "installed_count": 2,
                "installation_record_count": 1,
            },
            "missing": [],
            "version_drift": [],
            "source_drift": [],
            "unmanaged_discovered": [],
            "lock": {"stale_ids": []},
        }
        stdout = StringIO()

        call_command(
            "doctor",
            "--format",
            "json",
            "--skip-frontend",
            stdout=stdout,
        )

        payload = json.loads(stdout.getvalue())
        extension_check = next(item for item in payload["checks"] if item["name"] == "extensions")
        self.assertTrue(payload["ok"])
        self.assertEqual(extension_check["status"], "warning")
        self.assertEqual(
            extension_check["details"]["installation_record_drift"],
            {
                "installed_count": 2,
                "installation_record_count": 1,
            },
        )

    @patch("apps.core.management.commands.doctor.inspect_extension_frontend_output_manifest")
    @patch("apps.core.management.commands.doctor.get_frontend_vite_manifest_path")
    @patch("apps.core.management.commands.doctor.get_frontend_dist_root")
    def test_doctor_command_reports_missing_frontend_dist(self, get_dist_root, get_vite_manifest_path, inspect_manifest):
        temp_dir = make_workspace_temp_dir()
        try:
            dist_root = Path(temp_dir) / "frontend" / "dist"
            get_dist_root.return_value = dist_root
            get_vite_manifest_path.return_value = dist_root / ".vite" / "manifest.json"
            inspect_manifest.return_value = {
                "exists": True,
                "input_stale": False,
                "vite_manifest_exists": True,
            }

            with self.assertRaisesMessage(CommandError, "doctor 检查失败"):
                call_command(
                    "doctor",
                    "--skip-extensions",
                    stdout=StringIO(),
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

