from apps.core.tests.common import *

class ExtensionManagementCommandTests(TestCase):
    def test_extension_management_commands_skip_django_system_checks(self):
        from apps.core.management.commands.create_extension import Command as CreateExtensionCommand
        from apps.core.management.commands.extension_console import Command as ExtensionConsoleCommand
        from apps.core.management.commands.inspect_extensions import Command as InspectExtensionsCommand
        from apps.core.management.commands.validate_extensions import Command as ValidateExtensionsCommand

        self.assertEqual(CreateExtensionCommand.requires_system_checks, [])
        self.assertEqual(ExtensionConsoleCommand.requires_system_checks, [])
        self.assertEqual(InspectExtensionsCommand.requires_system_checks, [])
        self.assertEqual(ValidateExtensionsCommand.requires_system_checks, [])

    def test_extension_console_command_lists_and_runs_runtime_commands(self):
        commands = [{
            "name": "alpha:refresh",
            "description": "Refresh alpha",
            "handler": lambda options: {"ok": True, "scope": options.get("scope")},
        }]

        with patch("apps.core.management.commands.extension_console.list_runtime_console_commands", return_value=commands):
            stdout = StringIO()
            call_command("extension_console", "--list", "--format", "json", stdout=stdout)
            payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["commands"][0]["name"], "alpha:refresh")

        with patch("apps.core.management.commands.extension_console.list_runtime_console_schedules", return_value=[{
            "name": "alpha:refresh",
            "description": "Refresh alpha",
            "schedule": "hourly",
            "args": {"scope": "all"},
        }]):
            stdout = StringIO()
            call_command("extension_console", "--scheduled", "--format", "json", stdout=stdout)
            payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["schedules"][0]["schedule"], "hourly")

        with patch(
            "apps.core.management.commands.extension_console.run_runtime_console_command",
            return_value={"ok": True, "scope": "all"},
        ):
            stdout = StringIO()
            call_command(
                "extension_console",
                "alpha:refresh",
                "--payload",
                '{"scope":"all"}',
                "--format",
                "json",
                stdout=stdout,
            )
            payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["result"], {"ok": True, "scope": "all"})

    @patch("apps.core.management.commands.validate_extensions.get_core_module_ids", return_value=("core",))
    def test_validate_extensions_command_uses_core_and_filesystem_extension_ids(self, get_core_module_ids_mock):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly("create_extension", "alpha-tools")
                call_command_quietly("create_extension", "beta-tools")
                beta_manifest_path = Path(temp_dir) / "extensions" / "beta_tools" / "extension.json"
                beta_manifest = json.loads(beta_manifest_path.read_text(encoding="utf-8"))
                beta_manifest["dependencies"] = ["alpha-tools"]
                beta_manifest_path.write_text(json.dumps(beta_manifest, ensure_ascii=False), encoding="utf-8")
                call_command_quietly(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--strict",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        get_core_module_ids_mock.assert_called_once_with()

    def test_create_extension_command_scaffolds_minimal_extension_entry(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly(
                    "create_extension",
                    "alpha-tools",
                    "--name",
                    "Alpha Tools",
                    "--description",
                    "用于测试脚手架",
                )

                extension_dir = Path(temp_dir) / "extensions" / "alpha_tools"
                manifest = json.loads((extension_dir / "extension.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["id"], "alpha-tools")
                self.assertEqual(manifest["name"], "Alpha Tools")
                self.assertEqual(manifest["backend_entry"], "extensions.alpha_tools.backend.ext")
                self.assertEqual(
                    manifest["django_app_config"],
                    "extensions.alpha_tools.backend.apps.AlphaToolsExtensionConfig",
                )
                self.assertEqual(manifest["django_app_label"], "alpha_tools")
                self.assertNotIn("frontend_admin_entry", manifest)
                self.assertNotIn("frontend_forum_entry", manifest)
                self.assertNotIn("migration_namespace", manifest)
                self.assertEqual(manifest["compatibility"]["bias_version"], "^1.0.0")
                self.assertEqual(manifest["compatibility"]["api_stability"], "experimental")
                self.assertEqual(manifest["distribution"]["channel"], "private")
                self.assertEqual(manifest["security"]["support_email"], "security@example.com")
                self.assertTrue((extension_dir / "frontend" / "admin" / "index.js").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "DetailPage.vue").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "SettingsPage.vue").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "PermissionsPage.vue").exists())
                self.assertFalse((extension_dir / "frontend" / "admin" / "OperationsPage.vue").exists())
                self.assertTrue((extension_dir / "frontend" / "forum" / "index.js").exists())
                self.assertTrue((extension_dir / "backend" / "ext.py").exists())
                self.assertTrue((extension_dir / "backend" / "apps.py").exists())
                self.assertTrue((extension_dir / "backend" / "django_migrations" / "__init__.py").exists())
                self.assertFalse((extension_dir / "backend" / "migrations").exists())
                self.assertTrue((extension_dir / "README.md").exists())
                self.assertTrue((extension_dir / "docs" / "README.md").exists())
                self.assertTrue((extension_dir / "locale" / "zh-CN.json").exists())
                backend_source = (extension_dir / "backend" / "ext.py").read_text(encoding="utf-8")
                self.assertIn("def extend():", backend_source)
                self.assertIn("FrontendExtender()", backend_source)
                self.assertIn("extensions/alpha_tools/frontend/admin/index.js", backend_source)
                self.assertNotIn("from apps.core.", backend_source.replace("from apps.core.extensions", ""))
                apps_source = (extension_dir / "backend" / "apps.py").read_text(encoding="utf-8")
                self.assertIn("class AlphaToolsExtensionConfig(AppConfig):", apps_source)
                self.assertIn('label = "alpha_tools"', apps_source)
                self.assertNotIn("LifecycleExtender", backend_source)
                self.assertNotIn("def install(context):", backend_source)
                self.assertNotIn("def run_migrations(context):", backend_source)
                self.assertNotIn("def rollback_migrations(context):", backend_source)
                self.assertNotIn("def uninstall(context):", backend_source)
                self.assertNotIn("SettingsExtender", backend_source)
                self.assertNotIn("ApiResourceExtender", backend_source)
                self.assertNotIn("RuntimeActionsExtender", backend_source)
                self.assertNotIn("AdminNavigationExtender", backend_source)
                admin_source = (extension_dir / "frontend" / "admin" / "index.js").read_text(encoding="utf-8")
                forum_source = (extension_dir / "frontend" / "forum" / "index.js").read_text(encoding="utf-8")
                self.assertIn("from '@bias/admin'", admin_source)
                self.assertIn("export const extend", admin_source)
                self.assertIn("extendAdmin(admin => admin", admin_source)
                self.assertIn("export function resolveDetailPage()", admin_source)
                self.assertIn("return null", admin_source)
                self.assertNotIn(".page({", admin_source)
                self.assertIn("from '@bias/forum'", forum_source)
                self.assertIn("extendForum(forum => forum", forum_source)
                self.assertNotIn(".navItem({", forum_source)
                readme_source = (extension_dir / "README.md").read_text(encoding="utf-8")
                self.assertIn("backend/ext.py", readme_source)
                self.assertIn("validate_extensions --strict", readme_source)
                self.assertIn("build_extension_frontend --rebuild", readme_source)
                self.assertIn("ApiResourceExtender(...)", readme_source)
                self.assertIn("apps.core.extensions.runtime", readme_source)
                self.assertIn("apps.core.extensions.platform", readme_source)
                self.assertIn("apps.core.extensions.forum", readme_source)
                self.assertIn("backend/apps.py", readme_source)
                self.assertIn("backend/django_migrations", readme_source)
                self.assertNotIn("migration_namespace", readme_source)
                docs_readme_source = (extension_dir / "docs" / "README.md").read_text(encoding="utf-8")
                self.assertEqual(docs_readme_source, readme_source)

                from apps.core.extension_django_apps import (
                    discover_extension_django_apps,
                    discover_extension_django_migration_modules,
                )

                self.assertEqual(
                    discover_extension_django_apps(Path(temp_dir)),
                    ["extensions.alpha_tools.backend.apps.AlphaToolsExtensionConfig"],
                )
                self.assertEqual(
                    discover_extension_django_migration_modules(Path(temp_dir)),
                    {"alpha_tools": "extensions.alpha_tools.backend.django_migrations"},
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_extension_command_frontend_entries_use_public_sdks(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly("create_extension", "alpha-tools")

                entry_source = (Path(temp_dir) / "extensions" / "alpha_tools" / "frontend" / "admin" / "index.js").read_text(encoding="utf-8")
                self.assertIn("export function resolveDetailPage()", entry_source)
                self.assertIn("return null", entry_source)
                self.assertNotIn("import DetailPage", entry_source)
                self.assertNotIn("export function resolvePermissionsPage()", entry_source)
                self.assertIn("extendAdmin(admin => admin", entry_source)
                forum_entry_source = (Path(temp_dir) / "extensions" / "alpha_tools" / "frontend" / "forum" / "index.js").read_text(encoding="utf-8")
                self.assertIn("export const extend", forum_entry_source)
                self.assertIn("extendForum(forum => forum", forum_entry_source)
                self.assertNotIn(".navItem({", forum_entry_source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_create_extension_command_rejects_existing_directory_without_force(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extension_dir = Path(temp_dir) / "extensions" / "alpha_tools"
            extension_dir.mkdir(parents=True, exist_ok=False)
            with override_settings(BASE_DIR=Path(temp_dir)):
                with self.assertRaisesMessage(CommandError, f"扩展目录已存在: {extension_dir}。如需覆盖，请传 --force"):
                    call_command_quietly("create_extension", "alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_reports_manifest_errors(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["missing-one"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 2 个错误"):
                call_command_quietly("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_can_pass_in_strict_mode(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly("create_extension", "alpha-tools")
                call_command_quietly(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--strict",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_low_level_resource_extender_in_extension_source(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly("create_extension", "alpha-tools")
                backend_path = Path(temp_dir) / "extensions" / "alpha_tools" / "backend" / "ext.py"
                backend_path.write_text(
                    backend_path.read_text(encoding="utf-8")
                    + "\nfrom apps.core.extensions.extenders import ResourceExtender\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败"):
                    call_command_quietly(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_reports_optional_dependency_top_level_import_before_backend_load(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.models import BetaThing\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            output = StringIO()
            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                call_command(
                    "validate_extensions",
                    "--extensions-path",
                    str(extensions_dir),
                    stdout=output,
                    stderr=StringIO(),
                )

            self.assertIn("forbidden_cross_extension_internal_import", output.getvalue())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_external_project_name_residue_in_extension_source(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly("create_extension", "alpha-tools")
                backend_path = Path(temp_dir) / "extensions" / "alpha_tools" / "backend" / "ext.py"
                external_project_name = "fla" + "rum"
                backend_path.write_text(
                    backend_path.read_text(encoding="utf-8")
                    + f"\n# {external_project_name} naming residue must not enter Bias extensions\n",
                    encoding="utf-8",
                )

                with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                    call_command_quietly(
                        "validate_extensions",
                        "--extensions-path",
                        str(Path(temp_dir) / "extensions"),
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_allows_direct_admin_frontend_extender(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly("create_extension", "alpha-tools")
                admin_path = Path(temp_dir) / "extensions" / "alpha_tools" / "frontend" / "admin" / "index.js"
                admin_path.write_text(
                    "export const extend = [\n"
                    "  new AdminExtender().page({ path: '/admin/direct' }),\n"
                    "]\n"
                    "export function resolveDetailPage() { return null }\n",
                    encoding="utf-8",
                )

                call_command_quietly(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_rejects_core_internal_imports_by_default(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.models import Setting\n"
                "from apps.core.extensions.backend import _build_runtime_action_definition\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "扩展校验失败"):
                call_command_quietly("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_allows_public_extension_facades_by_default(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender, runtime_action\n"
                "from apps.core.extensions.runtime import get_runtime_user_by_id\n"
                "from apps.core.extensions.platform import api_error\n"
                "from apps.core.extensions.forum import get_forum_registry\n"
                "from apps.core.extensions.contracts import PermissionDefinition\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            call_command_quietly("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_internal_mode_allows_core_internal_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.models import Setting\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            call_command_quietly("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"), "--internal")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_reports_missing_frontend_admin_exports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveSettingsPage() { return null }\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                call_command_quietly("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_allows_generated_permissions_and_operations_surfaces(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "permissions_pages": ["/admin/extensions/alpha-tools/permissions"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
                "admin_actions": [
                    {
                        "key": "details",
                        "label": "查看详情",
                        "kind": "route",
                        "target": "/admin/extensions/alpha-tools",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveDetailPage() { return null }\n",
                encoding="utf-8",
            )

            call_command_quietly("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_reports_missing_frontend_admin_entry_declaration(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                call_command_quietly("validate_extensions", "--extensions-path", str(Path(temp_dir) / "extensions"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_can_emit_json_payload(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command_quietly("create_extension", "alpha-tools")
                stdout = StringIO()
                call_command_quietly(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--format",
                    "json",
                    stdout=stdout,
                )

                payload = json.loads(stdout.getvalue())
                self.assertEqual(payload["summary"]["manifest_count"], 1)
                self.assertEqual(payload["summary"]["error_count"], 0)
                self.assertEqual(payload["summary"]["warning_count"], 0)
                self.assertTrue(payload["summary"]["ok"])
                self.assertEqual(payload["manifests"][0]["id"], "alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_json_payload_still_fails_on_errors(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["missing-one"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            stdout = StringIO()
            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 2 个错误"):
                call_command_quietly(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--format",
                    "json",
                    stdout=stdout,
                )

            payload = json.loads(stdout.getvalue())
            self.assertEqual(payload["summary"]["error_count"], 2)
            self.assertFalse(payload["summary"]["ok"])
            self.assertTrue(any(item["code"] == "missing_dependency" for item in payload["issues"]))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extensions_command_strict_reports_missing_backend_hook(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "runtime_actions": [
                    {
                        "key": "rebuild-cache",
                        "label": "刷新缓存",
                        "hook": "run_rebuild_cache",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "扩展校验失败，共 1 个错误"):
                call_command_quietly(
                    "validate_extensions",
                    "--extensions-path",
                    str(Path(temp_dir) / "extensions"),
                    "--strict",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_inspect_extensions_command_outputs_extension_snapshot(self):
        stdout = StringIO()
        call_command("inspect_extensions", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertIn("summary", payload)
        self.assertIn("extensions", payload)
        self.assertIn("meta", payload)
        self.assertGreaterEqual(payload["summary"]["extension_count"], 1)
        self.assertIn("attention_count", payload["summary"])
        self.assertIn("blocking_count", payload["summary"])
        self.assertIn("warning_count", payload["summary"])
        self.assertIn("frontend_bundle_count", payload["summary"])
        self.assertIn("migration_bundle_count", payload["summary"])
        self.assertIn("package_lock", payload["runtime"])
        self.assertIn("summary", payload["runtime"]["package_lock"])
        self.assertIn("packages", payload["runtime"]["package_lock"])
        self.assertIn("diagnostics", payload["extensions"][0])
        self.assertTrue(any(item["id"] == "core" for item in payload["extensions"]))
        self.assertTrue(any(item["id"] == "tags" for item in payload["extensions"]))
        alpha_extension = next((item for item in payload["extensions"] if item["id"] == "alpha-tools"), None)
        if alpha_extension is not None:
            self.assertFalse(alpha_extension["product_visible"])

    def test_inspect_extensions_command_can_focus_single_extension_with_permissions(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "tags",
            "--include-permissions",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["summary"]["extension_count"], 1)
        self.assertEqual(payload["meta"]["extension_id"], "tags")
        self.assertEqual(payload["extensions"][0]["id"], "tags")
        self.assertIn("permission_sections", payload["extensions"][0])
        self.assertIn("package_lock", payload)
        self.assertIn("summary", payload["package_lock"])
        self.assertIn("packages", payload["package_lock"])
        self.assertIn("dependency_resolution", payload["package_lock"])
        self.assertIn("boot_order", payload["package_lock"]["dependency_resolution"])
        self.assertIn("graph", payload["package_lock"]["dependency_resolution"])

    def test_inspect_extensions_command_reports_model_ownership_audit(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "tags",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]

        self.assertEqual(extension["id"], "tags")
        self.assertIn("owned_model_count", audit)
        self.assertIn("items", audit)
        self.assertIn("target_app_label", audit)
        self.assertIn("model_package_migration_required_count", extension["capability_summary"])

    def test_inspect_extensions_command_can_filter_attention_only(self):
        ExtensionInstallation.objects.create(
            extension_id="notifications",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
            meta={
                "migration_execution": {
                    "status": "error",
                    "status_label": "失败",
                    "message": "迁移执行失败",
                },
            },
        )

        stdout = StringIO()
        call_command("inspect_extensions", "--only-attention", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertGreaterEqual(payload["summary"]["attention_count"], 1)
        self.assertTrue(any(item["id"] == "notifications" for item in payload["extensions"]))
        self.assertTrue(all("django_app_label" in item for item in payload["extensions"]))

    def test_inspect_extensions_command_can_filter_blocking_only(self):
        ExtensionInstallation.objects.create(
            extension_id="notifications",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
            meta={
                "migration_execution": {
                    "status": "error",
                    "status_label": "失败",
                    "message": "迁移执行失败",
                },
            },
        )

        stdout = StringIO()
        call_command("inspect_extensions", "--only-blocking", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertGreaterEqual(payload["summary"]["blocking_count"], 1)
        self.assertTrue(all(item["diagnostics"]["blocking"] for item in payload["extensions"]))

    def test_inspect_extensions_command_reports_missing_extension(self):
        with self.assertRaisesMessage(CommandError, "扩展不存在: missing-extension"):
            call_command("inspect_extensions", "--extension-id", "missing-extension")
