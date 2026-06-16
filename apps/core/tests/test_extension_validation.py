from apps.core.tests.common import *

class ExtensionValidationTests(TestCase):
    def test_resolve_bias_version_compatibility_supports_simple_ranges(self):
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            self.assertTrue(resolve_bias_version_compatibility(extension.manifest, current_version="1.0.0")["compatible"])
            self.assertTrue(resolve_bias_version_compatibility(extension.manifest, current_version="1.2.3")["compatible"])
            self.assertFalse(resolve_bias_version_compatibility(extension.manifest, current_version="2.0.0")["compatible"])
            self.assertFalse(resolve_bias_version_compatibility(extension.manifest, current_version="0.9.9")["compatible"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_inspect_frontend_admin_entry_reports_available_exports(self):
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            payload = inspect_frontend_admin_entry(
                extension.manifest,
                extensions_base_path=registry.extensions_path,
            )

            self.assertEqual(payload["entry_type"], "filesystem")
            self.assertTrue(payload["exists"])
            self.assertIn("resolveDetailPage", payload["available_exports"])
            self.assertIn("resolveSettingsPage", payload["available_exports"])
            self.assertIn("resolveOperationsPage", payload["available_exports"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_inspect_backend_entry_reports_available_hooks(self):
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            payload = inspect_backend_entry(
                extension.manifest,
                extensions_base_path=registry.extensions_path,
            )

            self.assertEqual(payload["entry_type"], "filesystem")
            self.assertTrue(payload["exists"])
            self.assertIn("install", payload["available_hooks"])
            self.assertIn("run_rebuild_cache", payload["available_hooks"])
            self.assertNotIn("run_migrations", payload["available_hooks"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_inspect_frontend_forum_entry_reports_available_exports(self):
        temp_dir = make_extension_test_base_dir()
        try:
            registry = ExtensionRegistry(extensions_path=temp_dir / "extensions")
            extension = registry.get_extension("alpha-tools")

            payload = inspect_frontend_forum_entry(
                extension.manifest,
                extensions_base_path=registry.extensions_path,
            )

            self.assertEqual(payload["entry_type"], "filesystem")
            self.assertTrue(payload["exists"])
            self.assertIn("available_exports", payload)
            self.assertTrue(payload["resolved_path"].endswith("extensions/alpha-tools/frontend/forum/index.js"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_requires_frontend_admin_entry_for_admin_pages(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_frontend_admin_entry_declaration" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
