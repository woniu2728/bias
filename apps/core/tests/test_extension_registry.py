from apps.core.tests.common import *

@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
class ExtensionRegistryTests(TestCase):
    def test_safe_mode_filters_enabled_filesystem_extensions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            for extension_id in ("alpha-tools", "beta-tools"):
                manifest_dir = extensions_dir / extension_id
                manifest_dir.mkdir(parents=True, exist_ok=True)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": extension_id,
                    "name": extension_id,
                    "version": "1.0.0",
                }, ensure_ascii=False), encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id=extension_id,
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode",
                defaults={"value": json.dumps(True)},
            )
            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode_extensions",
                defaults={"value": json.dumps(["alpha-tools"])},
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            enabled_ids = [extension.id for extension in registry.get_enabled_extensions()]

            self.assertEqual(enabled_ids, ["alpha-tools"])
            recovery_state = serialize_extension_recovery_state()
            self.assertEqual(recovery_state["safe_mode"], True)
            self.assertEqual(recovery_state["safe_mode_extensions"], ["alpha-tools"])
            self.assertEqual(recovery_state["bisect"]["active"], False)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_safe_mode_filters_all_extension_runtime_surfaces(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            for extension_id in ("alpha-tools", "beta-tools"):
                manifest_dir = extensions_dir / extension_id
                backend_dir = manifest_dir / "backend"
                backend_dir.mkdir(parents=True, exist_ok=True)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": extension_id,
                    "name": extension_id,
                    "version": "1.0.0",
                    "backend_entry": f"extensions.{extension_id.replace('-', '_')}.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text(
                    "from apps.core.extensions import ApiResourceExtender, EventListenersExtender, FrontendExtender, MiddlewareExtender\n"
                    "from apps.core.extensions import ExtensionEventListenerDefinition, ResourceEndpointDefinition\n"
                    "\n"
                    "class RuntimeEvent:\n"
                    "    pass\n"
                    "\n"
                    "def handle_event(event):\n"
                    "    return None\n"
                    "\n"
                    "def handle_endpoint(context):\n"
                    "    return {'ok': True}\n"
                    "\n"
                    "def demo_middleware(request):\n"
                    "    return request\n"
                    "\n"
                    "def extend():\n"
                    "    return [\n"
                    f"        FrontendExtender(forum_entry='extensions/{extension_id}/frontend/forum/index.js').route('/{extension_id}', '{extension_id}.route', './Page.vue'),\n"
                    f"        ApiResourceExtender('forum').endpoint(ResourceEndpointDefinition(resource='forum', endpoint='{extension_id}.endpoint', module_id='', handler=handle_endpoint)),\n"
                    "        EventListenersExtender((ExtensionEventListenerDefinition(RuntimeEvent, handle_event),)),\n"
                    "        MiddlewareExtender(mounts=(('api', demo_middleware, 30),)),\n"
                    "    ]\n",
                    encoding="utf-8",
                )
                ExtensionInstallation.objects.create(
                    extension_id=extension_id,
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode",
                defaults={"value": json.dumps(True)},
            )
            Setting.objects.update_or_create(
                key="advanced.extension_safe_mode_extensions",
                defaults={"value": json.dumps(["alpha-tools"])},
            )

            app = build_extension_application(
                manager=ExtensionRegistry(extensions_path=extensions_dir),
                forum_registry=ForumRegistry(),
                resource_registry=ResourceRegistry(),
                event_bus=DomainEventBus(),
                force=True,
            )

            self.assertEqual([view.extension_id for view in app.get_runtime_views()], ["alpha-tools"])
            self.assertIsNotNone(app.get_frontend_extension("alpha-tools"))
            self.assertIsNone(app.get_frontend_extension("beta-tools"))
            self.assertEqual(
                [endpoint.endpoint for endpoint in app.resources.get_endpoints("forum")],
                ["alpha-tools.endpoint"],
            )
            self.assertEqual(len(app.events.get_listeners(extension_id="alpha-tools")), 1)
            self.assertEqual(app.events.get_listeners(extension_id="beta-tools"), [])
            self.assertEqual(len(app.get_middleware_mounts(target="api")), 1)
            self.assertEqual(app.get_middleware_mounts(target="api")[0].middleware.__name__, "demo_middleware")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_bisect_state_advances_to_candidate(self):
        from apps.core.extensions.recovery import (
            advance_extension_bisect,
            start_extension_bisect,
            stop_extension_bisect,
        )

        try:
            state = start_extension_bisect(["alpha", "beta", "gamma", "delta"])
            self.assertEqual(state["active"], True)
            self.assertEqual(state["current"], ["alpha", "beta"])

            state = advance_extension_bisect(issue_present=True)
            self.assertEqual(state["active"], True)
            self.assertEqual(state["current"], ["alpha"])

            state = advance_extension_bisect(issue_present=False)
            self.assertEqual(state["active"], False)
            self.assertEqual(state["culprit"], "beta")
        finally:
            stop_extension_bisect()

    def test_extension_bisect_rotates_enabled_extensions_and_restores_original_state(self):
        from apps.core.extensions.recovery import (
            advance_extension_bisect,
            start_extension_bisect,
            stop_extension_bisect,
        )

        for extension_id in ["alpha", "beta", "gamma", "delta"]:
            ExtensionInstallation.objects.create(
                extension_id=extension_id,
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

        try:
            state = start_extension_bisect(["alpha", "beta", "gamma", "delta"])
            enabled_ids = sorted(ExtensionInstallation.objects.filter(enabled=True).values_list("extension_id", flat=True))
            self.assertEqual(state["current"], ["alpha", "beta"])
            self.assertEqual(enabled_ids, ["alpha", "beta"])
            self.assertEqual(Setting.objects.get(key="advanced.maintenance_mode_key").value, '"low"')

            state = advance_extension_bisect(issue_present=True)
            enabled_ids = sorted(ExtensionInstallation.objects.filter(enabled=True).values_list("extension_id", flat=True))
            self.assertEqual(state["current"], ["alpha"])
            self.assertEqual(enabled_ids, ["alpha"])

            state = advance_extension_bisect(issue_present=False)
            enabled_ids = sorted(ExtensionInstallation.objects.filter(enabled=True).values_list("extension_id", flat=True))
            self.assertEqual(state["culprit"], "beta")
            self.assertEqual(enabled_ids, ["alpha", "beta", "delta", "gamma"])
            self.assertEqual(Setting.objects.get(key="advanced.maintenance_mode_key").value, '"none"')
        finally:
            stop_extension_bisect()

    def test_routes_extender_rejects_frontend_route_apps(self):
        from apps.core.extensions import RoutesExtender

        with self.assertRaisesMessage(ValueError, "FrontendExtender.route"):
            RoutesExtender("forum")

        with self.assertRaisesMessage(ValueError, "FrontendExtender.route"):
            RoutesExtender("admin")

    def test_runtime_invalidation_resets_runtime_and_url_caches(self):
        from apps.core.extensions.events import ExtensionDisabledEvent
        from apps.core.extensions.runtime_event_listeners import handle_extension_runtime_invalidation

        with patch("apps.core.extensions.frontend_runtime_service.clear_extension_frontend_runtime_cache") as clear_frontend, patch(
            "apps.core.extensions.locale_service.clear_extension_locale_cache"
        ) as clear_locale, patch(
            "apps.core.extensions.formatter_service.clear_extension_formatter_cache"
        ) as clear_formatter, patch(
            "apps.core.extensions.template_loader.clear_extension_template_caches"
        ) as clear_templates, patch(
            "apps.core.extensions.runtime_event_listeners.invalidate_extension_frontend_assets"
        ) as invalidate_assets, patch(
            "apps.core.extensions.lifecycle.reset_extension_runtime_state"
        ) as reset_runtime, patch(
            "apps.core.extensions.lifecycle.rebuild_runtime_urlconf"
        ) as rebuild_urlconf:
            handle_extension_runtime_invalidation(ExtensionDisabledEvent(extension_id="alpha-tools"))

        clear_frontend.assert_called_once_with()
        clear_locale.assert_called_once_with()
        clear_formatter.assert_called_once_with()
        clear_templates.assert_called_once_with()
        invalidate_assets.assert_called_once_with("extension_disabled", extension_id="alpha-tools")
        reset_runtime.assert_called_once_with()
        rebuild_urlconf.assert_called_once_with()

    def test_extension_frontend_listener_invalidates_assets_from_lifecycle_event(self):
        from apps.core.extensions.event_bus import get_extension_event_bus
        from apps.core.extensions.events import ExtensionEnabledEvent
        from apps.core.extensions import formatter_service, frontend_runtime_service, locale_service

        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const staleExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text('{"stale": true}', encoding="utf-8")
                build_manifest.write_text('{"stale": true}', encoding="utf-8")
                frontend_runtime_service._frontend_runtime_catalog = {"stale": {}}
                frontend_runtime_service._frontend_runtime_bootstrapped = True
                locale_service._extension_locale_cache = [{"stale": True}]
                formatter_service._extension_formatter_pipeline_cache = {"render": [lambda value: value]}

                bootstrap_extension_runtime_event_listeners()
                get_extension_event_bus().dispatch(ExtensionEnabledEvent(extension_id="alpha-tools"))

                marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("extension_enabled", marker.value)
                self.assertIn("alpha-tools", marker.value)
                self.assertTrue(output_manifest.exists())
                self.assertTrue(build_manifest.exists())
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
                self.assertEqual(frontend_runtime_service._frontend_runtime_catalog, {})
                self.assertFalse(frontend_runtime_service._frontend_runtime_bootstrapped)
                self.assertIsNone(locale_service._extension_locale_cache)
                self.assertEqual(formatter_service._extension_formatter_pipeline_cache, {})
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_runtime_cache_clear_event_refreshes_extension_frontend_assets(self):
        from apps.core.extensions.event_bus import get_extension_event_bus
        from apps.core.extensions.events import RuntimeCacheClearedEvent

        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const staleExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text('{"stale": true}', encoding="utf-8")
                build_manifest.write_text('{"stale": true}', encoding="utf-8")

                bootstrap_extension_runtime_event_listeners()
                get_extension_event_bus().dispatch(RuntimeCacheClearedEvent())

                marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("runtime_cache_cleared", marker.value)
                self.assertTrue(output_manifest.exists())
                self.assertTrue(build_manifest.exists())
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_clear_runtime_cache_command_refreshes_extension_frontend_assets(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const staleExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text('{"stale": true}', encoding="utf-8")
                build_manifest.write_text('{"stale": true}', encoding="utf-8")

                stdout = StringIO()
                call_command("clear_runtime_cache", stdout=stdout)

                self.assertIn("[OK] 已清理运行时缓存", stdout.getvalue())
                marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("runtime_cache_cleared", marker.value)
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_enabling_event_can_block_install_before_side_effects(self):
        from apps.core.domain_events import DomainEventBus
        from apps.core.extensions import event_bus as extension_event_bus_module
        from apps.core.extensions.events import ExtensionEnablingEvent

        previous_bus = extension_event_bus_module._extension_event_bus
        extension_event_bus_module._extension_event_bus = DomainEventBus()
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                assets_dir = manifest_dir / "assets"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                assets_dir.mkdir(parents=True, exist_ok=False)
                (assets_dir / "logo.txt").write_text("asset", encoding="utf-8")
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

                def block_enable(event):
                    if event.extension_id == "alpha-tools":
                        raise ExtensionStateError(
                            "blocked by pre-enable listener",
                            code="extension_enable_blocked_by_listener",
                        )

                extension_event_bus_module.get_extension_event_bus().register(ExtensionEnablingEvent, block_enable)
                registry = ExtensionRegistry(extensions_path=extensions_dir)

                with self.assertRaises(ExtensionStateError):
                    registry.install_extension("alpha-tools")

                self.assertFalse(ExtensionInstallation.objects.filter(extension_id="alpha-tools").exists())
                self.assertFalse((Path(temp_dir) / "static" / "extensions" / "alpha-tools" / "logo.txt").exists())
                self.assertFalse(Setting.objects.filter(key="extensions_runtime_rebuild_required").exists())
        finally:
            extension_event_bus_module._extension_event_bus = previous_bus
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_disabling_event_can_block_disable_before_side_effects(self):
        from apps.core.domain_events import DomainEventBus
        from apps.core.extensions import event_bus as extension_event_bus_module
        from apps.core.extensions.events import ExtensionDisablingEvent

        previous_bus = extension_event_bus_module._extension_event_bus
        extension_event_bus_module._extension_event_bus = DomainEventBus()
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                assets_dir = manifest_dir / "assets"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                assets_dir.mkdir(parents=True, exist_ok=False)
                (assets_dir / "logo.txt").write_text("asset", encoding="utf-8")
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

                registry = ExtensionRegistry(extensions_path=extensions_dir)
                registry.install_extension("alpha-tools")
                published_file = Path(temp_dir) / "static" / "extensions" / "alpha-tools" / "logo.txt"
                self.assertTrue(published_file.exists())

                def block_disable(event):
                    if event.extension_id == "alpha-tools":
                        raise ExtensionStateError(
                            "blocked by pre-disable listener",
                            code="extension_disable_blocked_by_listener",
                        )

                extension_event_bus_module.get_extension_event_bus().register(ExtensionDisablingEvent, block_disable)

                with self.assertRaises(ExtensionStateError):
                    registry.set_extension_enabled("alpha-tools", False)

                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                self.assertTrue(installation.enabled)
                self.assertTrue(installation.booted)
                self.assertTrue(published_file.exists())
        finally:
            extension_event_bus_module._extension_event_bus = previous_bus
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_uninstall_clears_django_migration_summary(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                migrations_dir = backend_dir / "django_migrations"
                migrations_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                    "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                    "django_app_label": "alpha_tools",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")
                (backend_dir / "apps.py").write_text(
                    "from django.apps import AppConfig\n"
                    "\n"
                    "\n"
                    "class AlphaToolsConfig(AppConfig):\n"
                    "    default_auto_field = 'django.db.models.BigAutoField'\n"
                    "    name = 'extensions.alpha_tools.backend'\n"
                    "    label = 'alpha_tools'\n",
                    encoding="utf-8",
                )
                (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
                (migrations_dir / "0001_bootstrap.py").write_text(
                    "from django.db import migrations\n"
                    "\n"
                    "\n"
                    "class Migration(migrations.Migration):\n"
                    "    initial = True\n"
                    "    dependencies = []\n"
                    "    operations = []\n",
                    encoding="utf-8",
                )

                registry = ExtensionRegistry(extensions_path=extensions_dir)
                installed = registry.install_extension("alpha-tools")
                self.assertEqual(installed.runtime.backend_hooks["run_migrations"]["details"]["direction"], "up")

                registry.set_extension_enabled("alpha-tools", False)
                reenabled = registry.set_extension_enabled("alpha-tools", True)
                self.assertEqual(reenabled.runtime.backend_hooks["run_migrations"]["details"]["direction"], "up")
                self.assertEqual(
                    reenabled.runtime.backend_hooks["run_migrations"]["details"]["skipped_migration_files"],
                    ["0001_bootstrap.py"],
                )

                uninstalled = registry.uninstall_extension("alpha-tools")

                self.assertFalse(uninstalled.runtime.installed)
                self.assertEqual(uninstalled.runtime.backend_hooks["run_disable"]["status"], "skipped")
                self.assertEqual(uninstalled.runtime.backend_hooks["rollback_migrations"]["details"]["direction"], "down")
                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                self.assertEqual(installation.meta["applied_migration_files"], [])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_registry_exposes_filesystem_extensions_only(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extensions = registry.get_extensions()

        extension_ids = {item.id for item in extensions}
        self.assertNotIn("core", extension_ids)
        self.assertNotIn("alpha-tools", extension_ids)
        self.assertIn("posts", extension_ids)
        self.assertIn("discussions", extension_ids)
        self.assertIn("users", extension_ids)
        self.assertIn("emoji", extension_ids)
        self.assertTrue(all(item.source == "filesystem" for item in extensions))

        emoji_extension = next(item for item in extensions if item.id == "emoji")
        self.assertEqual(emoji_extension.source, "filesystem")
        self.assertTrue(emoji_extension.runtime.installed)
        self.assertTrue(emoji_extension.runtime.enabled)
        self.assertEqual(emoji_extension.runtime.status_key, "active")

    def test_runtime_probe_prefers_contract_frontend_entries(self):
        manifest = ExtensionManifest(
            id="contract-first",
            name="Contract First",
            version="1.0.0",
            frontend_admin_entry="",
            frontend_forum_entry="",
            path=str(Path.cwd() / "extensions" / "alpha-tools"),
        )
        extension = Extension(
            manifest=ExtensionManifest(
                id="contract-first",
                name="Contract First",
                version="1.0.0",
                frontend_admin_entry="extensions/contract-first/frontend/admin/index.js",
                frontend_forum_entry="extensions/contract-first/frontend/forum/index.js",
                path=str(Path.cwd() / "extensions" / "tags"),
            ),
            source="filesystem",
        )

        payload = inspect_extension_runtime(extension)

        checks = {item.key: item for item in payload["delivery_checks"]}
        self.assertEqual(checks["frontend-admin-entry"].status, "ready")
        self.assertEqual(checks["frontend-forum-entry"].status, "ready")

    def test_registry_applies_persisted_installation_state(self):
        ExtensionInstallation.objects.create(
            extension_id="emoji",
            version="0.1.0",
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("emoji")

        self.assertFalse(extension.runtime.enabled)
        self.assertFalse(extension.runtime.booted)
        self.assertTrue(extension.runtime.installed)

    def test_registry_merges_filesystem_extension_contract_capabilities(self):
        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("emoji")

        self.assertEqual(extension.module_ids, ("emoji",))
        self.assertEqual(extension.settings_schema[0].key, "cdn_url")

    def test_runtime_service_exposes_enabled_extension_runtime_entries(self):
        entries = get_enabled_extension_runtime_entries(product_visible_only=True)

        emoji = next(item for item in entries if item["id"] == "emoji")
        self.assertEqual(emoji["frontend_forum_entry"], "extensions/emoji/frontend/forum/index.js")
        self.assertEqual(emoji["module_ids"], ["emoji"])
        self.assertEqual(emoji["forum_settings"], {"cdn_url": "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/"})
        self.assertIn("extensions/emoji/locale", emoji["locale_paths"])
        self.assertFalse(any(item["id"] == "alpha-tools" for item in entries))

    def test_frontend_runtime_bootstrap_builds_enabled_extension_entries(self):
        from apps.core.extensions import frontend_runtime_service

        frontend_runtime_service._frontend_runtime_catalog = {}
        frontend_runtime_service._frontend_runtime_bootstrapped = False
        bootstrap_extension_frontend_runtime()

        entries = frontend_runtime_service.get_enabled_extension_runtime_entries(product_visible_only=True)
        emoji = next(item for item in entries if item["id"] == "emoji")
        self.assertEqual(emoji["frontend_forum_entry"], "extensions/emoji/frontend/forum/index.js")
        self.assertEqual(emoji["forum_settings"], {"cdn_url": "https://cdn.jsdelivr.net/gh/jdecked/twemoji@15.1.0/assets/"})

    def test_frontend_runtime_bootstrap_registers_static_catalog_without_settings_query(self):
        from apps.core.extensions import frontend_runtime_service

        frontend_runtime_service._frontend_runtime_catalog = {}
        frontend_runtime_service._frontend_runtime_bootstrapped = False

        with patch("apps.core.extensions.frontend_runtime_service.get_extension_settings") as get_extension_settings_mock:
            bootstrap_extension_frontend_runtime()

        get_extension_settings_mock.assert_not_called()
        self.assertIn("emoji", frontend_runtime_service._frontend_runtime_catalog)

    def test_extension_runtime_state_refreshes_after_enable_toggle(self):
        reset_extension_runtime_state()
        entries = get_enabled_extension_runtime_entries(product_visible_only=True)
        self.assertTrue(any(item["id"] == "ai" for item in entries))

        with patch("apps.core.extension_service.reset_extension_runtime_state") as reset_runtime_mock, patch(
            "apps.core.extension_service.rebuild_runtime_urlconf"
        ) as rebuild_urlconf_mock:
            ExtensionService.set_extension_enabled("ai", False)

        reset_runtime_mock.assert_called_once()
        rebuild_urlconf_mock.assert_called_once()

    def test_extension_assembly_service_orders_enabled_extensions_by_dependency(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"

            alpha_dir = extensions_dir / "alpha-base"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-base",
                "name": "Alpha Base",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_base.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            beta_dir = extensions_dir / "beta-addon"
            beta_backend_dir = beta_dir / "backend"
            beta_backend_dir.mkdir(parents=True, exist_ok=False)
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-addon",
                "name": "Beta Addon",
                "version": "1.0.0",
                "dependencies": ["alpha-base"],
                "backend_entry": "extensions.beta_addon.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (beta_backend_dir / "ext.py").write_text(
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-base",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )
            ExtensionInstallation.objects.create(
                extension_id="beta-addon",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            ordered = get_enabled_extension_assemblies(force=True, registry=registry)

            ordered_ids = [item.extension_id for item in ordered if item.extension_id in {"alpha-base", "beta-addon"}]
            self.assertEqual(ordered_ids, ["alpha-base", "beta-addon"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.extensions.runtime_probe.resolve_bias_version_compatibility")
    def test_registry_marks_extension_unhealthy_when_bias_version_incompatible(self, resolve_bias_version_compatibility_mock):
        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }

        registry = ExtensionRegistry(extensions_path=Path.cwd() / "extensions")
        extension = registry.get_extension("emoji")

        self.assertFalse(extension.runtime.healthy)
        self.assertIn("当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。", extension.runtime.runtime_issues)
        self.assertTrue(any(
            item.key == "bias-compatibility" and item.status == "attention"
            for item in extension.runtime.delivery_checks
        ))

    def test_registry_filters_module_capabilities_when_extension_disabled(self):
        ExtensionInstallation.objects.create(
            extension_id="approval",
            version="1.0.0",
            source="filesystem",
            enabled=False,
            installed=True,
            booted=False,
        )

        registry = get_forum_registry()
        approval_module = registry.get_module("approval")

        self.assertFalse(approval_module.enabled)
        self.assertFalse(any(item.module_id == "approval" for item in registry.get_admin_pages()))
        self.assertFalse(any(item.module_id == "approval" for item in registry.get_search_filters()))
