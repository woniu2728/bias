from apps.core.tests.common import *

class ExtensionServiceTests(TestCase):
    def setUp(self):
        self.extension_base_dir = make_extension_test_base_dir()
        self.settings_override = override_settings(BASE_DIR=self.extension_base_dir)
        self.settings_override.enable()
        reset_extension_runtime_state()
        self.addCleanup(self._cleanup_extension_base_dir)

    def _cleanup_extension_base_dir(self):
        reset_extension_runtime_state()
        self.settings_override.disable()
        reset_extension_runtime_state()
        shutil.rmtree(self.extension_base_dir, ignore_errors=True)

    def _record_alpha_tools_django_migration(self):
        MigrationRecorder(connection).record_applied("alpha_tools", "0001_bootstrap")

    def test_install_and_uninstall_transition_filesystem_extension(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.installed)
        self.assertTrue(installed.runtime.enabled)
        self.assertEqual(installed.runtime.backend_hooks["run_install"]["status"], "ok")
        self.assertEqual(installed.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(installed.runtime.migration_state, "applied")
        self.assertEqual(installed.runtime.migration_label, "最近已执行")
        self.assertEqual(installed.runtime.migration_execution["state"], "applied")
        self.assertIn("0001_bootstrap.py", installed.runtime.migration_execution["details"]["migration_files"])
        self.assertIn("0001_bootstrap", installed.runtime.migration_execution["details"]["applied_steps"])
        installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
        self.assertIn("0001_bootstrap.py", installation.meta["applied_migration_files"])

        disabled = ExtensionService.set_extension_enabled("alpha-tools", False)
        self.assertFalse(disabled.runtime.enabled)
        self.assertEqual(disabled.runtime.backend_hooks["run_disable"]["status"], "ok")

        enabled = ExtensionService.set_extension_enabled("alpha-tools", True)
        self.assertTrue(enabled.runtime.enabled)
        self.assertEqual(enabled.runtime.backend_hooks["run_enable"]["status"], "ok")

        uninstalled = ExtensionService.uninstall_extension("alpha-tools")
        self.assertFalse(uninstalled.runtime.installed)
        self.assertFalse(uninstalled.runtime.enabled)
        self.assertEqual(uninstalled.runtime.backend_hooks["run_disable"]["status"], "ok")
        self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status"], "ok")
        installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
        self.assertEqual(installation.meta["applied_migration_files"], [])

    def test_run_extension_backend_hook_skips_when_hook_missing(self):
        registry = ExtensionRegistry(extensions_path=Path(settings.BASE_DIR) / "extensions")
        definition = registry.get_extension("alpha-tools")

        result = run_extension_backend_hook(definition, "run_reconcile")

        self.assertEqual(result["status"], "skipped")
        self.assertIn("run_reconcile", result["message"])

    def test_runtime_hook_executes_declared_extension_operation(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.enabled)

        updated = ExtensionService.run_extension_runtime_hook("alpha-tools", "run_rebuild_cache")

        self.assertEqual(updated.runtime.backend_hooks["run_rebuild_cache"]["status"], "ok")

    def test_run_extension_migrations_executes_declared_migration_hook(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.installed)

        updated = ExtensionService.run_extension_migrations("alpha-tools")

        self.assertEqual(updated.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(updated.runtime.migration_state, "applied")
        self.assertEqual(updated.runtime.migration_label, "最近已执行")
        self.assertEqual(updated.runtime.migration_execution["status"], "ok")
        self.assertEqual(updated.runtime.migration_execution["details"]["migration_files"], [])
        self.assertIn("0001_bootstrap.py", updated.runtime.migration_execution["details"]["skipped_migration_files"])

    def test_run_extension_migrations_refreshes_auto_installed_extension(self):
        updated = ExtensionService.run_extension_migrations("users")

        self.assertEqual(updated.id, "users")
        self.assertEqual(updated.runtime.backend_hooks["run_migrations"]["status"], "ok")
        self.assertEqual(updated.runtime.migration_state, "applied")

    def test_runtime_reset_keeps_full_extension_catalog_on_reload(self):
        from apps.core.extensions.manager import get_extension_manager

        manager = get_extension_manager()
        manager.load(force=True)
        before_ids = {extension.id for extension in manager.get_extensions()}

        reset_extension_runtime_state()
        manager = get_extension_manager()
        manager.load(force=True)
        after_ids = {extension.id for extension in manager.get_extensions()}

        self.assertIn("approval", before_ids)
        self.assertIn("emoji", after_ids)
        self.assertIn("flags", after_ids)
        self.assertIn("approval", after_ids)

    def test_run_extension_migrations_requires_installation(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.run_extension_migrations("alpha-tools")

        self.assertEqual(context.exception.code, "extension_migrations_not_installed")

    def test_migrate_extensions_command_requires_installation(self):
        with self.assertRaisesMessage(CommandError, "尚未安装"):
            call_command("migrate_extensions", "alpha-tools")

    def test_migrate_extensions_command_executes_single_extension(self):
        ExtensionService.install_extension("alpha-tools")
        self._record_alpha_tools_django_migration()

        stdout = StringIO()
        call_command("migrate_extensions", "alpha-tools", "--format", "json", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        self.assertEqual(payload["summary"]["target_count"], 1)
        self.assertEqual(payload["summary"]["error_count"], 0)
        self.assertEqual(payload["extensions"][0]["id"], "alpha-tools")
        self.assertEqual(payload["extensions"][0]["status"], "ok")
        self.assertIn("0001_bootstrap.py", payload["extensions"][0]["details"]["skipped_migration_files"])

    def test_migrate_extensions_command_blocks_when_django_migration_is_unapplied(self):
        ExtensionService.install_extension("alpha-tools")

        with self.assertRaisesMessage(CommandError, "Django 数据库迁移尚未应用"):
            call_command("migrate_extensions", "alpha-tools")

    def test_migrate_extensions_command_dry_run_all_does_not_persist_state(self):
        self._record_alpha_tools_django_migration()
        installation = ExtensionInstallation.objects.create(
            extension_id="alpha-tools",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
            meta={},
        )

        stdout = StringIO()
        call_command("migrate_extensions", "--all", "--dry-run", "--format", "json", stdout=stdout)
        payload = json.loads(stdout.getvalue())

        sample_extension = next(item for item in payload["extensions"] if item["id"] == "alpha-tools")
        self.assertEqual(sample_extension["status"], "ok")
        self.assertIn("0001_bootstrap.py", sample_extension["migration_plan"]["pending_files"])
        installation.refresh_from_db()
        self.assertEqual(installation.meta, {})

    def test_runtime_hook_requires_manifest_declaration(self):
        ExtensionService.install_extension("alpha-tools")

        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.run_extension_runtime_hook("alpha-tools", "run_unknown")

        self.assertEqual(context.exception.code, "extension_runtime_hook_not_declared")

    def test_enable_ignores_stale_core_installation_dependency_record(self):
        ExtensionService.install_extension("alpha-tools")
        ExtensionInstallation.objects.update_or_create(
            extension_id="core",
            defaults={
                "version": "1.0.0",
                "source": "core-module",
                "enabled": False,
                "installed": True,
                "booted": False,
            },
        )

        enabled = ExtensionService.set_extension_enabled("alpha-tools", True)

        self.assertTrue(enabled.runtime.enabled)

    def test_disable_raises_when_enabled_dependents_exist(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.set_extension_enabled("notifications", False)

        self.assertEqual(context.exception.code, "extension_disable_blocked")
        self.assertIn("approval", context.exception.details["blocking_dependents"])

    def test_disable_raises_for_protected_extension(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.set_extension_enabled("posts", False)

        self.assertEqual(context.exception.code, "extension_disable_protected_blocked")
        self.assertIn("protected_reason", context.exception.details)

    def test_uninstall_raises_for_protected_extension(self):
        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.uninstall_extension("posts")

        self.assertEqual(context.exception.code, "extension_uninstall_protected_blocked")
        self.assertIn("protected_reason", context.exception.details)

    def test_uninstall_disables_enabled_extension_first(self):
        installed = ExtensionService.install_extension("alpha-tools")
        self.assertTrue(installed.runtime.enabled)

        uninstalled = ExtensionService.uninstall_extension("alpha-tools")

        self.assertFalse(uninstalled.runtime.installed)
        self.assertFalse(uninstalled.runtime.enabled)
        self.assertEqual(uninstalled.runtime.backend_hooks["run_disable"]["status"], "ok")
        self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status"], "ok")

    @patch("apps.core.extensions.compatibility_guard.resolve_bias_version_compatibility")
    def test_install_raises_when_bias_version_incompatible(self, resolve_bias_version_compatibility_mock):
        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }

        with self.assertRaises(ExtensionStateError) as context:
            ExtensionService.install_extension("alpha-tools")

        self.assertEqual(context.exception.code, "extension_install_incompatible_bias_version")
        self.assertEqual(context.exception.details["required_bias_version"], "^2.0.0")

    @patch("apps.core.extensions.compatibility_guard.resolve_bias_version_compatibility")
    def test_bias_compatibility_guard_normalizes_enable_errors(self, resolve_bias_version_compatibility_mock):
        from apps.core.extensions.compatibility_guard import validate_bias_compatibility

        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }
        extension = SimpleNamespace(id="alpha-tools", manifest=SimpleNamespace())

        with self.assertRaises(ExtensionStateError) as context:
            validate_bias_compatibility(extension, action="enable")

        self.assertEqual(context.exception.code, "extension_enable_incompatible_bias_version")
        self.assertEqual(context.exception.details["extension_id"], "alpha-tools")
        self.assertEqual(context.exception.details["current_bias_version"], "1.0.0")
        self.assertEqual(context.exception.details["required_bias_version"], "^2.0.0")
