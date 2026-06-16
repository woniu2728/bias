from apps.core.tests.common import *

@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
class ExtensionManifestLoaderTests(TestCase):
    def test_discovers_declared_extension_django_apps_and_infers_migration_modules(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
            }, ensure_ascii=False), encoding="utf-8")

            self.assertEqual(
                discover_extension_django_apps(temp_dir),
                ["extensions.alpha_tools.backend.apps.AlphaToolsConfig"],
            )
            self.assertEqual(
                discover_extension_django_migration_modules(temp_dir),
                {"alpha_tools": "extensions.alpha_tools.backend.django_migrations"},
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_discovers_explicit_extension_django_app_label(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                "django_app_label": "alpha",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifest = loader.discover_manifests()[0]

            self.assertEqual(manifest.django_app_label, "alpha")
            self.assertEqual(
                discover_extension_django_migration_modules(temp_dir),
                {"alpha": "extensions.alpha_tools.backend.django_migrations"},
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_applies_default_compatibility_and_distribution_metadata(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifest = loader.discover_manifests()[0]

            self.assertEqual(manifest.compatibility.bias_version, "^1.0.0")
            self.assertEqual(manifest.compatibility.api_version, "1.0")
            self.assertEqual(manifest.compatibility.api_stability, "experimental")
            self.assertEqual(manifest.compatibility.api_stability_label, "实验性")
            self.assertEqual(
                manifest.compatibility.breaking_change_policy,
                "扩展协议调整会随 Bias 主版本升级同步说明。",
            )
            self.assertEqual(manifest.distribution.channel, "private")
            self.assertEqual(manifest.distribution.channel_label, "私有分发")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_reads_extension_manifest_from_extensions_directory(self):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            manifest_dir = base_dir / "extensions" / "sample-extension"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "sample-extension",
                "name": "Sample Extension",
                "version": "1.0.0",
                "description": "A sample extension.",
                "dependencies": ["core"],
                "settings_pages": ["/admin/extensions/sample"],
                "permissions_pages": ["/admin/extensions/sample/permissions"],
                "operations_pages": ["/admin/extensions/sample/operations"],
                "operations_profile": {
                    "kicker": "Alpha Runtime",
                    "title": "Sample Operations",
                    "highlights": ["示例能力"],
                    "focus_panels": [
                        {
                            "key": "notification_types",
                            "title": "示例通知",
                        }
                    ],
                    "recommended_action_keys": ["details"],
                    "next_steps": ["继续补齐示例操作页。"],
                },
                "admin_actions": [
                    {
                        "key": "details",
                        "label": "查看详情",
                        "kind": "route",
                        "target": "/admin/extensions/sample-extension",
                    }
                ],
                "runtime_actions": [
                    {
                        "key": "rebuild-cache",
                        "label": "刷新缓存",
                        "hook": "run_rebuild_cache",
                        "requires_enabled": True,
                    }
                ],
                "settings_schema": [
                    {
                        "key": "theme",
                        "label": "主题",
                        "type": "select",
                        "default": "light",
                        "options": [
                            {"value": "light", "label": "浅色"},
                            {"value": "dark", "label": "深色"}
                        ]
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(base_dir / "extensions")
            results = loader.discover()

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].manifest.id, "sample-extension")
            self.assertEqual(results[0].manifest.name, "Sample Extension")
            self.assertEqual(results[0].manifest.dependencies, ("core",))
            self.assertEqual(results[0].manifest.settings_pages, ("/admin/extensions/sample",))
            self.assertEqual(results[0].manifest.permissions_pages, ("/admin/extensions/sample/permissions",))
            self.assertEqual(results[0].manifest.operations_pages, ("/admin/extensions/sample/operations",))
            self.assertEqual(results[0].manifest.operations_profile["kicker"], "Alpha Runtime")
            self.assertEqual(results[0].manifest.operations_profile["focus_panels"][0]["key"], "notification_types")
            self.assertEqual(results[0].manifest.admin_actions[0].key, "details")
            self.assertEqual(results[0].manifest.runtime_actions[0].hook, "run_rebuild_cache")
            self.assertEqual(results[0].manifest.settings_schema[0].key, "theme")
            self.assertFalse(hasattr(results[0].manifest, "migration_namespace"))
            self.assertEqual(results[0].manifest.django_app_config, "")
            self.assertEqual(results[0].manifest.compatibility.api_version, "1.0")
            self.assertEqual(results[0].manifest.compatibility.api_stability, "experimental")
            self.assertEqual(results[0].manifest.distribution.channel, "private")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


    def test_loader_merges_forum_setting_exposure_from_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import SettingsExtender, setting_field\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        SettingsExtender(\n"
                "            fields=(\n"
                "                setting_field({'key': 'cdn_url', 'label': 'CDN', 'type': 'text', 'default': ''}),\n"
                "            ),\n"
                "            expose_to_forum=('cdn_url',),\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.forum_settings_keys, ("cdn_url",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_forum_capabilities_from_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ForumCapabilitiesExtender, NotificationsExtender\n"
                "from apps.core.extensions import NotificationTypeDefinition, UserPreferenceDefinition, SearchFilterDefinition\n"
                "\n"
                "def _parse_author(token):\n"
                "    if token.startswith('author:'):\n"
                "        return token.split(':', 1)[1]\n"
                "    return None\n"
                "\n"
                "def _apply(queryset, value, context):\n"
                "    return queryset\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        NotificationsExtender(\n"
                "            notification_types=(\n"
                "                NotificationTypeDefinition(code='alphaPing', label='Alpha Ping', module_id='alpha-tools'),\n"
                "            ),\n"
                "            user_preferences=(\n"
                "                UserPreferenceDefinition(key='notify_alpha_ping', label='Alpha Ping', module_id='alpha-tools', default_value=True),\n"
                "            ),\n"
                "        ),\n"
                "        ForumCapabilitiesExtender(\n"
                "            search_filters=(\n"
                "                SearchFilterDefinition(code='author', label='作者', module_id='alpha-tools', target='discussion', parser=_parse_author, applier=_apply, syntax='author:<username>'),\n"
                "            ),\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.notification_types[0].code, "alphaPing")
            self.assertEqual(result.user_preferences[0].key, "notify_alpha_ping")
            self.assertEqual(result.search_filters[0].syntax, "author:<username>")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_language_pack_extender_into_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-lang"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-lang",
                "name": "Alpha Language",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_lang.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import LanguagePackExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        LanguagePackExtender(\n"
                "            code='en-US',\n"
                "            label='English',\n"
                "            native_label='English',\n"
                "            path='extensions/alpha-lang/locale',\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.language_packs[0].code, "en-US")
            self.assertEqual(result.language_packs[0].module_id, "alpha-lang")
            self.assertEqual(result.locale_paths, ("extensions/alpha-lang/locale",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_admin_surface_extender_into_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import AdminSurfaceExtender\n"
                "from apps.core.extensions import PermissionDefinition, AdminPageDefinition\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        AdminSurfaceExtender(\n"
                "            permissions=(\n"
                "                PermissionDefinition(code='alpha.manage', label='管理 Alpha', section='admin', section_label='后台', module_id='alpha-tools'),\n"
                "            ),\n"
                "            admin_pages=(\n"
                "                AdminPageDefinition(path='/admin/alpha-tools', label='Alpha Tools', icon='fas fa-toolbox', module_id='alpha-tools'),\n"
                "            ),\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.permissions[0].code, "alpha.manage")
            self.assertEqual(result.admin_pages[0].path, "/admin/alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_extenders_into_manifest(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import SettingsExtender, RuntimeActionsExtender, runtime_action, setting_field\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        SettingsExtender(fields=(\n"
                "            setting_field({'key': 'cdn_url', 'label': 'CDN', 'type': 'text', 'default': ''}),\n"
                "        )),\n"
                "        RuntimeActionsExtender(actions=(\n"
                "            runtime_action({'key': 'rebuild', 'label': '刷新', 'hook': 'run_rebuild_cache'}),\n"
                "        )),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            results = loader.discover()

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].manifest.settings_schema[0].key, "cdn_url")
            self.assertEqual(results[0].manifest.runtime_actions[0].hook, "run_rebuild_cache")
            self.assertEqual(results[0].manifest.settings_pages, ("/admin/extensions/alpha-tools/settings",))
            self.assertEqual(results[0].settings_pages, ("/admin/extensions/alpha-tools/settings",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_loader_merges_frontend_extender_into_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        (FrontendExtender()\n"
                "            .admin('extensions/alpha-tools/frontend/admin/index.js')\n"
                "            .forum('extensions/alpha-tools/frontend/forum/index.js')),\n"
                "    ]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            result = loader.discover()[0]

            self.assertEqual(result.frontend_admin_entry, "extensions/alpha-tools/frontend/admin/index.js")
            self.assertEqual(result.frontend_forum_entry, "extensions/alpha-tools/frontend/forum/index.js")
            self.assertEqual(result.manifest.frontend_admin_entry, "extensions/alpha-tools/frontend/admin/index.js")
            self.assertEqual(result.manifest.frontend_forum_entry, "extensions/alpha-tools/frontend/forum/index.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_api_route_mounts(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from ninja import Router\n"
                "from apps.core.extensions import ApiRoutesExtender\n"
                "\n"
                "router = Router()\n"
                "\n"
                "@router.get('/ping')\n"
                "def ping(request):\n"
                "    return {'ok': True}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ApiRoutesExtender(mounts=(('/ext/alpha-tools', router),), tags=('Alpha',)),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            mounts = application.get_route_mounts()

            self.assertEqual(len(mounts), 1)
            self.assertEqual(mounts[0].prefix, "/ext/alpha-tools")
            self.assertEqual(tuple(mounts[0].tags), ("Alpha",))
            runtime_view = application.get_runtime_view("alpha-tools")
            self.assertEqual(runtime_view.lifecycle_phase_keys, ("register", "boot", "ready"))
            self.assertEqual(runtime_view.extender_keys, ("ApiRoutesExtender",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_websocket_routes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from channels.generic.websocket import AsyncWebsocketConsumer\n"
                "from apps.core.extensions import WebSocketRoutesExtender\n"
                "\n"
                "class AlphaConsumer(AsyncWebsocketConsumer):\n"
                "    pass\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        WebSocketRoutesExtender().route(r'ws/alpha/$', 'alpha.websocket', AlphaConsumer),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            routes = application.get_websocket_routes()
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual(len(routes), 1)
            self.assertEqual(routes[0].path, "ws/alpha/$")
            self.assertEqual(routes[0].name, "alpha.websocket")
            self.assertEqual(routes[0].module_id, "alpha-tools")
            self.assertEqual(runtime_view.websocket_routes[0].name, "alpha.websocket")
            self.assertEqual(runtime_view.extender_keys, ("WebSocketRoutesExtender",))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_frontend_extender_aliases_match_runtime_registration(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        (FrontendExtender()\n"
                "            .js('forum.js')\n"
                "            .js('admin.js', frontend='admin')\n"
                "            .common('common.js')\n"
                "            .css('forum.css')\n"
                "            .jsDirectory('chunks')\n"
                "            .preload([\n"
                "                {'href': '/x.js', 'as': 'script'},\n"
                "                {'href': '/x.css', 'as': 'style'},\n"
                "            ])\n"
                "            .extraDocumentAttributes({'data-alpha': '1'})\n"
                "            .extraDocumentClasses('alpha-page')\n"
                "            .route('/alpha', 'alpha', 'AlphaPage')\n"
                "            .removeRoute('old-alpha')),\n"
                "    ]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            application = build_extension_application(manager=ExtensionRegistry(extensions_path=extensions_dir), force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual(runtime_view.frontend_forum_entry, "forum.js")
            self.assertEqual(runtime_view.frontend_admin_entry, "admin.js")
            self.assertEqual(runtime_view.frontend_common_entry, "common.js")
            self.assertEqual(runtime_view.frontend_css, ("forum.css",))
            self.assertEqual(runtime_view.frontend_js_directories, ("chunks",))
            self.assertEqual(runtime_view.frontend_preloads[0]["as"], "script")
            self.assertEqual(runtime_view.frontend_preloads[1]["as"], "style")
            self.assertEqual(runtime_view.frontend_document_attributes[0]["data-alpha"], "1")
            self.assertIn({"class": "alpha-page"}, runtime_view.frontend_document_attributes)
            self.assertEqual(runtime_view.frontend_routes[0].path, "/alpha")
            self.assertEqual(runtime_view.frontend_routes[1].name, "old-alpha")
            self.assertTrue(runtime_view.frontend_routes[1].removed)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_extenders_are_flattened_from_nested_extend_files(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        FrontendExtender(admin_entry='extensions/alpha/admin.js'),\n"
                "        [None, FrontendExtender(forum_entry='extensions/alpha/forum.js')],\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual(runtime_view.frontend_admin_entry, "extensions/alpha/admin.js")
            self.assertEqual(runtime_view.frontend_forum_entry, "extensions/alpha/forum.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_named_api_routes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import RoutesExtender\n"
                "\n"
                "def ping(request):\n"
                "    return {'ok': True}\n"
                "\n"
                "def replacement(request):\n"
                "    return {'ok': 'replacement'}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        RoutesExtender('api', tags=('Alpha',)).get('/ext/alpha-tools/ping', 'alpha.ping', ping),\n"
                "        RoutesExtender('api').remove('alpha.old').get('/ext/alpha-tools/replacement', 'alpha.old', replacement),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            named_routes = application.get_named_routes(app_name="api")

            self.assertEqual([route.name for route in named_routes], ["alpha.ping", "alpha.old"])
            self.assertEqual(named_routes[0].method, "GET")
            self.assertEqual(named_routes[0].tags, ("Alpha",))
            self.assertEqual(application.get_runtime_view("alpha-tools").named_routes[0].name, "alpha.ping")

            api = application.make("api.application")
            paths = {item[0] for item in api._routers}
            self.assertIn("/ext/alpha-tools/ping", paths)
            self.assertIn("/ext/alpha-tools/replacement", paths)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_forum_settings_exposes_extension_document_runtime(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        FrontendExtender(forum_entry='forum.js')\n"
                "            .preload({'href': '/static/alpha.css', 'as': 'style'})\n"
                "            .extra_document_attributes({'data-alpha': '1'})\n"
                "            .title('AlphaTitle')\n"
                "            .content('alpha.content', priority=120)\n"
                "            .content('alpha.late_content', priority=20),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            with patch("apps.core.extensions.frontend_runtime_service.get_extension_host", return_value=application):
                clear_runtime_setting_caches()
                payload = get_public_forum_settings()

            document = payload["extension_document"]
            self.assertEqual(document["preloads"], [{"href": "/static/alpha.css", "as": "style"}])
            self.assertEqual(document["document_attributes"], {"data-alpha": "1"})
            self.assertEqual(document["title_drivers"], [{"extension_id": "alpha-tools", "driver": "AlphaTitle"}])
            self.assertEqual(document["content_callbacks"], [
                {"extension_id": "alpha-tools", "callback": "alpha.content", "priority": 120},
                {"extension_id": "alpha-tools", "callback": "alpha.late_content", "priority": 20},
            ])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            clear_runtime_setting_caches()

    def test_extension_sources_do_not_import_replaced_private_runtime_helpers(self):
        forbidden_helpers = (
            "_broadcast_discussion_event",
            "_build_realtime_included_payload",
            "_create_timeline_from_builder",
            "_make_timeline_context",
        )
        extension_root = Path.cwd() / "extensions"
        offenders = []
        for path in extension_root.rglob("*.py"):
            content = path.read_text(encoding="utf-8")
            for helper in forbidden_helpers:
                if helper in content:
                    offenders.append(f"{path.relative_to(Path.cwd())}: {helper}")

        self.assertEqual(offenders, [])

    def test_backend_entry_namespace_controls_loaded_file(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            alternate_dir = manifest_dir / "alternate"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            alternate_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.alternate.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [FrontendExtender(forum_entry='extensions/alpha-tools/frontend/forum/wrong.js')]\n",
                encoding="utf-8",
            )
            (alternate_dir / "ext.py").write_text(
                "from apps.core.extensions import FrontendExtender\n"
                "\n"
                "def extend():\n"
                "    return [FrontendExtender(forum_entry='extensions/alpha-tools/frontend/forum/right.js')]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(extensions_dir)
            result = loader.discover()[0]

            self.assertEqual(result.frontend_forum_entry, "extensions/alpha-tools/frontend/forum/right.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.extensions.manifest.metadata.distributions")
    def test_manifest_loader_discovers_python_distribution_extensions(self, distributions_mock):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=True):
                from apps.core.extensions import manifest as manifest_module

                manifest_module._distribution_manifest_cache = None
                package_dir = Path(temp_dir) / "site-packages" / "alpha_tools" / "bias_extension"
                package_dir.mkdir(parents=True, exist_ok=False)
                manifest_path = package_dir / "extension.json"
                manifest_path.write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.2.3",
                    "backend_entry": "alpha_tools.ext",
                }, ensure_ascii=False), encoding="utf-8")

                class DemoDistribution:
                    version = "1.2.3"
                    files = ("alpha_tools/bias_extension/extension.json",)
                    metadata = {"Name": "alpha-tools"}

                    def locate_file(self, file):
                        return Path(temp_dir) / "site-packages" / str(file)

                distributions_mock.return_value = [DemoDistribution()]
                loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
                manifests = loader.discover_manifests()

            self.assertEqual(len(manifests), 1)
            self.assertEqual(manifests[0].id, "alpha-tools")
            self.assertEqual(manifests[0].source, "python-package")
            self.assertEqual(manifests[0].extra["python_distribution"]["name"], "alpha-tools")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_runs_extension_service_provider(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ServiceProviderExtender\n"
                "\n"
                "def provide(app):\n"
                "    return {'has_app': app.has('app'), 'ready': True}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ServiceProviderExtender(key='alpha.provider', provider=provide),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)

            self.assertEqual(application.get_service("alpha.provider"), {
                "has_app": True,
                "ready": True,
            })
            runtime_view = application.get_runtime_view("alpha-tools")
            self.assertIsNotNone(runtime_view)
            self.assertIn("alpha.provider", runtime_view.service_providers)
            compatibility_record = next(item for item in application.get_records() if item.extension_id == "alpha-tools")
            self.assertIn("alpha.provider", compatibility_record.service_providers)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_runs_host_service_provider_class(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ServiceProviderExtender\n"
                "\n"
                "class DemoProvider:\n"
                "    def register(self, app):\n"
                "        app.instance('alpha.provider', {'registered': app.has('app')})\n"
                "\n"
                "    def boot(self, app):\n"
                "        app.instance('alpha.provider.booted', {'booted': True})\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ServiceProviderExtender(key='alpha.provider', provider=DemoProvider),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)

            self.assertEqual(application.get_service("alpha.provider"), {
                "registered": True,
            })
            self.assertEqual(application.get_service("alpha.provider.booted"), {
                "booted": True,
            })
            self.assertEqual(application.get_service_provider_keys(extension_id="alpha-tools"), ["alpha.provider"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_supports_aliases_tags_and_bias_resource_contract(self):
        app = ExtensionApplication()
        app.instance("alpha.service", {"ready": True})
        app.alias("alpha.service", "alpha.alias")
        app.tag(["alpha.alias"], "alpha.services")

        self.assertEqual(app.make("alpha.alias"), {"ready": True})
        self.assertEqual(app.tagged("alpha.services"), [{"ready": True}])
        self.assertEqual(app.make("bias.api.resources"), [])

    def test_view_extender_registers_template_namespaces(self):
        from django.template.loader import render_to_string

        from apps.core.extensions import ViewExtender
        from apps.core.extensions.template_loader import clear_extension_template_caches

        temp_dir = make_workspace_temp_dir()
        extension_dir = Path(temp_dir) / "extensions" / "alpha-tools"
        templates_dir = extension_dir / "templates"
        overrides_dir = extension_dir / "overrides"
        prepend_dir = extension_dir / "prepend"
        templates_dir.mkdir(parents=True)
        overrides_dir.mkdir(parents=True)
        prepend_dir.mkdir(parents=True)
        (templates_dir / "hello.html").write_text("Hello {{ name }}", encoding="utf-8")
        (prepend_dir / "hello.html").write_text("Override {{ name }}", encoding="utf-8")

        app = ExtensionApplication()
        app.get_or_create_runtime_view("alpha-tools", path=str(extension_dir))
        extension = SimpleNamespace(extension_id="alpha-tools")

        try:
            ViewExtender() \
                .namespace("alpha", "templates", "overrides", description="Alpha views") \
                .extend_namespace("alpha", "prepend") \
                .extend(app, extension)
            app.make("views")

            namespaces = app.views.get_namespaces(extension_id="alpha-tools")
            runtime_view = app.get_runtime_view("alpha-tools")

            self.assertEqual(len(namespaces), 2)
            self.assertEqual(namespaces[0].namespace, "alpha")
            self.assertEqual(namespaces[0].hints, (str(prepend_dir.resolve()),))
            self.assertEqual(namespaces[0].module_id, "alpha-tools")
            self.assertTrue(namespaces[0].prepend)
            self.assertEqual(namespaces[1].hints, (str(templates_dir.resolve()), str(overrides_dir.resolve())))
            self.assertEqual(runtime_view.view_namespaces, tuple(namespaces))
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
                clear_extension_template_caches()
                self.assertEqual(app.views.render("alpha::hello.html", {"name": "Bias"}), "Override Bias")
                self.assertEqual(render_to_string("alpha::hello.html", {"name": "Bias"}), "Override Bias")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_registers_provider_through_app_register(self):
        app = ExtensionApplication()

        class DemoProvider:
            def register(self, host):
                host.instance("demo.provider.value", {"registered": True})

            def boot(self, host):
                host.instance("demo.provider.booted", {"booted": True})

        key = app.register(DemoProvider, key="demo.provider", extension_id="alpha-tools")
        app.providers.boot()

        self.assertEqual(key, "demo.provider")
        self.assertEqual(app.make("demo.provider.value"), {"registered": True})
        self.assertEqual(app.make("demo.provider.booted"), {"booted": True})

    def test_validator_and_mail_extenders_register_runtime_definitions(self):
        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def validate_title(value, context):
            return value

        def build_mail(message, context):
            return message

        ValidatorExtender().validator("title", "discussion", validate_title).extend(app, extension)
        MailExtender().driver("digest", build_mail).extend(app, extension)

        validators = app.make("validators").get_definitions(extension_id="alpha-tools")
        mailers = app.make("mail").get_definitions(extension_id="alpha-tools")
        runtime_view = app.get_runtime_view("alpha-tools")

        self.assertEqual(validators[0].key, "title")
        self.assertEqual(validators[0].target, "discussion")
        self.assertEqual(validators[0].module_id, "alpha-tools")
        self.assertEqual(mailers[0].key, "digest")
        self.assertEqual(mailers[0].module_id, "alpha-tools")
        self.assertEqual(runtime_view.validators, tuple(validators))
        self.assertEqual(runtime_view.mailers, tuple(mailers))

    def test_mail_extender_contributes_runtime_driver_definitions(self):
        from apps.core.mail_drivers import get_driver_definitions, normalize_mail_driver

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        MailExtender().driver(
            "custom",
            lambda definition, context: {
                "label": "Custom",
                "description": "Runtime mail driver",
                "fields": [{"key": "mail_custom_token", "label": "Token"}],
            },
        ).extend(app, extension)
        app.make("mail")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            definitions = get_driver_definitions()
            self.assertEqual(normalize_mail_driver("custom"), "custom")

        self.assertEqual(definitions["custom"]["label"], "Custom")
        self.assertEqual(definitions["custom"]["fields"][0]["key"], "mail_custom_token")

    def test_mail_extender_driver_can_send_runtime_message(self):
        from apps.core.mail_drivers import send_with_extension_mail_driver

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        sent = []

        def send_digest(message, context):
            sent.append((message["subject"], context["source"]))
            return True

        MailExtender().driver("digest", send_digest).extend(app, extension)
        app.make("mail")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            result = send_with_extension_mail_driver("digest", {"subject": "Digest"}, {"source": "test"})

        self.assertEqual(result, True)
        self.assertEqual(sent, [("Digest", "test")])

    def test_system_hook_extenders_register_runtime_hooks(self):
        from apps.core.extensions import (
            AuthExtender,
            ConsoleExtender,
            ErrorHandlingExtender,
            FilesystemExtender,
            SessionExtender,
            ThemeExtender,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        ErrorHandlingExtender().hook("report", lambda payload, context: "error").extend(app, extension)
        AuthExtender().hook("provider", lambda payload, context: "auth").extend(app, extension)
        FilesystemExtender().hook("driver", lambda payload, context: "fs").extend(app, extension)
        ConsoleExtender().hook("command", lambda payload, context: "console").extend(app, extension)
        SessionExtender().hook("session", lambda payload, context: "session").extend(app, extension)
        ThemeExtender().hook("theme", lambda payload, context: "theme").extend(app, extension)

        self.assertEqual(app.make("error.handling").run("report")[0], "error")
        self.assertEqual(app.make("auth").run("provider")[0], "auth")
        self.assertEqual(app.make("filesystem").run("driver")[0], "fs")
        self.assertEqual(app.make("console").run("command")[0], "console")
        self.assertEqual(app.make("session").run("session")[0], "session")
        self.assertEqual(app.make("theme").run("theme")[0], "theme")
        runtime_view = app.get_runtime_view("alpha-tools")
        self.assertEqual(runtime_view.error_handlers[0].module_id, "alpha-tools")

    def test_signal_extender_registers_and_clears_runtime_receivers(self):
        from django.dispatch import Signal
        from apps.core.extensions import SignalExtender
        from apps.core.extensions.signal_runtime import (
            disconnect_runtime_signal_receivers,
            get_runtime_signal_connections,
        )

        signal = Signal()
        received = []

        def receiver(sender, **kwargs):
            received.append(kwargs["value"])

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        try:
            SignalExtender().connect(
                signal,
                receiver,
                sender=ExtensionApplication,
                dispatch_uid="alpha.signal.receiver",
            ).extend(app, extension)
            app.make("signals")

            signal.send(sender=ExtensionApplication, value=1)

            runtime_view = app.get_runtime_view("alpha-tools")
            self.assertEqual(received, [1])
            self.assertEqual(runtime_view.signal_handlers[0].module_id, "alpha-tools")
            self.assertEqual(get_runtime_signal_connections(extension_id="alpha-tools")[0].dispatch_uid, "alpha.signal.receiver")

            disconnect_runtime_signal_receivers()
            signal.send(sender=ExtensionApplication, value=2)
            self.assertEqual(received, [1])
        finally:
            disconnect_runtime_signal_receivers()

    def test_signal_proxy_reset_disconnects_only_lazy_proxy_receivers(self):
        from django.dispatch import Signal
        from apps.core.extensions.signal_bootstrap import reset_extension_signal_proxy_bootstrap
        from apps.core.extensions.signal_runtime import (
            connect_runtime_signal,
            connect_runtime_signal_proxy,
            disconnect_runtime_signal_receivers,
            get_runtime_signal_connections,
        )
        from apps.core.extensions import ExtensionSignalDefinition

        proxy_signal = Signal()
        runtime_signal = Signal()
        received = []

        def proxy_receiver(sender=None, **kwargs):
            received.append(("proxy", kwargs["value"]))

        def runtime_receiver(sender=None, **kwargs):
            received.append(("runtime", kwargs["value"]))

        try:
            connect_runtime_signal_proxy(
                "alpha-tools",
                ExtensionSignalDefinition(
                    signal=proxy_signal,
                    receiver=proxy_receiver,
                    dispatch_uid="alpha.proxy.receiver",
                ),
                enabled_by_default=True,
            )
            connect_runtime_signal(
                "alpha-tools",
                ExtensionSignalDefinition(
                    signal=runtime_signal,
                    receiver=runtime_receiver,
                    dispatch_uid="alpha.runtime.receiver",
                ),
            )

            self.assertEqual(len(get_runtime_signal_connections(extension_id="alpha-tools")), 2)

            reset_extension_signal_proxy_bootstrap()
            proxy_signal.send(sender=ExtensionApplication, value=1)
            runtime_signal.send(sender=ExtensionApplication, value=2)

            self.assertEqual(received, [("runtime", 2)])
            remaining = get_runtime_signal_connections(extension_id="alpha-tools")
            self.assertEqual([item.dispatch_uid for item in remaining], ["alpha.runtime.receiver"])
        finally:
            disconnect_runtime_signal_receivers()

    def test_model_extender_declares_owned_models(self):
        from apps.core.extensions import ModelExtender

        class DemoOwnedModel:
            pass

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        ModelExtender().owns(
            DemoOwnedModel,
            description="Alpha owns this model.",
        ).extend(app, extension)
        app.make("models")

        runtime_view = app.get_runtime_view("alpha-tools")
        owned = app.models.get_owned_models(extension_id="alpha-tools")

        self.assertEqual(runtime_view.model_definitions[0].kind, "owner")
        self.assertEqual(runtime_view.model_definitions[0].model, DemoOwnedModel)
        self.assertEqual(owned[0].description, "Alpha owns this model.")
        self.assertEqual(app.models.get_model_owner(DemoOwnedModel), "alpha-tools")

    def test_runtime_model_reference_resolves_model_relations_and_policies(self):
        from apps.core.extensions import ModelExtender, PolicyExtender, RuntimeModel, ServiceProviderExtender
        from apps.core.extensions.policy_runtime_service import evaluate_model_policy

        class DemoModel:
            pass

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        runtime_model = RuntimeModel("alpha.model")

        ServiceProviderExtender(
            key="alpha.model",
            provider=lambda: {"model": DemoModel},
        ).extend(app, extension)
        ModelExtender(model=runtime_model).belongs_to_many(
            "followers",
            runtime_model,
            resolver=lambda instance: ["alice"],
            inject_attribute=False,
        ).extend(app, extension)
        PolicyExtender().policy(
            runtime_model,
            lambda user=None, ability="", model=None, **context: ability == "view",
        ).extend(app, extension)

        app.make("models")
        app.make("policies")

        relations = app.models.get_relations_for_model(DemoModel)
        self.assertEqual(relations[0].name, "followers")
        self.assertEqual(app.models.resolve_relation(DemoModel, "followers", DemoModel()), ["alice"])
        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            self.assertTrue(evaluate_model_policy("view", model=DemoModel(), default=False))

    def test_post_event_extender_registers_event_data_resolver(self):
        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def resolve_alpha_event(post, context):
            return {
                "kind": post.type,
                "actor": context["user"],
            }

        PostEventExtender().type(
            "alphaEvent",
            resolve_alpha_event,
            description="Alpha event data.",
        ).types(
            ("betaEvent",),
            resolve_alpha_event,
            description="Beta event data.",
        ).extend(app, extension)

        event_data = app.make("post.events").resolve(
            SimpleNamespace(type="alphaEvent", content=""),
            {"user": "tester"},
        )

        self.assertEqual(event_data, {"kind": "alphaEvent", "actor": "tester"})
        self.assertEqual(app.make("post.events").get_definitions(post_type="alphaEvent")[0].module_id, "alpha-tools")
        self.assertEqual(app.make("post.events").get_definitions(post_type="betaEvent")[0].module_id, "alpha-tools")

    def test_conditional_extender_supports_disabled_setting_and_class_callbacks(self):
        app = ExtensionApplication()
        app._booted_extensions["beta-tools"] = SimpleNamespace(runtime=SimpleNamespace(enabled=False))
        extension = SimpleNamespace(extension_id="alpha-tools")
        Setting.objects.create(key="alpha.enabled", value="1")

        class ConditionalFields:
            def __call__(self):
                return ResourceExtender(fields=(
                    ResourceFieldDefinition(
                        resource="forum",
                        field="class_conditional",
                        module_id="",
                        resolver=lambda model, context: True,
                    ),
                ))

        ConditionalExtender() \
            .when_extension_disabled("beta-tools", lambda: [
                ResourceExtender(fields=(
                    ResourceFieldDefinition(
                        resource="forum",
                        field="disabled_conditional",
                        module_id="",
                        resolver=lambda model, context: True,
                    ),
                )),
                [
                    None,
                    ResourceExtender(fields=(
                        ResourceFieldDefinition(
                            resource="forum",
                            field="nested_conditional",
                            module_id="",
                            resolver=lambda model, context: True,
                        ),
                    )),
                ],
            ]) \
            .when_setting("alpha.enabled", "1", ConditionalFields) \
            .extend(app, extension)

        fields = {item.field: item for item in app.make("resources").get_fields("forum")}

        self.assertIn("disabled_conditional", fields)
        self.assertIn("nested_conditional", fields)
        self.assertIn("class_conditional", fields)
        self.assertEqual(fields["disabled_conditional"].module_id, "alpha-tools")
        self.assertEqual(fields["nested_conditional"].module_id, "alpha-tools")
        self.assertEqual(fields["class_conditional"].module_id, "alpha-tools")

    def test_system_hook_runtime_services_drive_error_filesystem_and_console(self):
        from apps.core.extensions import ConsoleExtender, ErrorHandlingExtender, FilesystemExtender
        from apps.core.extensions.system_runtime import (
            get_runtime_error_statuses,
            list_runtime_console_commands,
            list_runtime_console_schedules,
            list_runtime_filesystem_disks,
            report_runtime_error,
            resolve_runtime_filesystem_driver,
            run_runtime_console_command,
        )
        from apps.core.storage_service import get_storage_backend

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        reports = []

        class CustomStorage:
            pass

        def report(payload, context):
            reports.append((payload["error_type"], payload["operation"]))
            return True

        def filesystem(payload, context):
            if payload["driver"] == "custom":
                return CustomStorage()
            return None

        def console(payload, context):
            return {
                "name": "alpha:refresh",
                "description": "Refresh alpha",
                "handler": lambda options: {"ok": True, "scope": options.get("scope")},
            }

        ErrorHandlingExtender().hook("report", report).status("alpha_error", 409).extend(app, extension)
        FilesystemExtender().hook("driver", filesystem).disk("alpha", {"root": "/tmp/alpha"}).extend(app, extension)
        ConsoleExtender().hook("command", console).schedule("alpha:refresh", "hourly").extend(app, extension)
        app.make("error.handling")
        app.make("filesystem")
        app.make("console")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            report_runtime_error(ValueError("broken"), operation="unit-test")
            storage = resolve_runtime_filesystem_driver("custom", {"storage_driver": "custom"})
            storage_from_service = get_storage_backend({"storage_driver": "custom"})
            commands = list_runtime_console_commands()
            schedules = list_runtime_console_schedules()
            disks = list_runtime_filesystem_disks()
            statuses = get_runtime_error_statuses()
            result = run_runtime_console_command("alpha:refresh", options={"scope": "all"})

        self.assertEqual(reports, [("ValueError", "unit-test")])
        self.assertIsInstance(storage, CustomStorage)
        self.assertIsInstance(storage_from_service, CustomStorage)
        self.assertEqual(commands[0]["name"], "alpha:refresh")
        self.assertEqual(schedules[0]["name"], "alpha:refresh")
        self.assertEqual(disks[0]["name"], "alpha")
        self.assertEqual(statuses["alpha_error"], 409)
        self.assertEqual(result, {"ok": True, "scope": "all"})

    def test_auth_and_session_extenders_register_typed_runtime_services(self):
        from apps.core.extensions import AuthExtender, SessionExtender
        from apps.core.extensions.system_runtime import (
            get_runtime_password_checkers,
            list_runtime_session_drivers,
            resolve_runtime_session_driver,
            verify_runtime_user_password,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        class CustomSessionDriver:
            def __init__(self, config):
                self.config = config

        user = SimpleNamespace(username="alpha", password="unused")

        AuthExtender() \
            .remove_password_checker("django") \
            .add_password_checker("alpha", lambda current_user, raw_password: current_user.username == raw_password) \
            .extend(app, extension)
        SessionExtender().driver("alpha", CustomSessionDriver, description="Alpha session").extend(app, extension)
        app.make("auth")
        app.make("session")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            checkers = get_runtime_password_checkers(default_checker=lambda current_user, raw_password: False)
            accepted = verify_runtime_user_password(user, "alpha", default_checker=lambda current_user, raw_password: False)
            rejected = verify_runtime_user_password(user, "wrong", default_checker=lambda current_user, raw_password: True)
            drivers = list_runtime_session_drivers()
            resolved_driver = resolve_runtime_session_driver("alpha", {"ttl": 60})

        self.assertEqual(list(checkers.keys()), ["alpha"])
        self.assertTrue(accepted)
        self.assertFalse(rejected)
        self.assertEqual(drivers[0]["name"], "alpha")
        self.assertEqual(drivers[0]["extension_id"], "alpha-tools")
        self.assertIsInstance(resolved_driver, CustomSessionDriver)
        self.assertEqual(resolved_driver.config["ttl"], 60)

    def test_csrf_throttle_and_search_index_extenders_register_runtime_services(self):
        from apps.core.extensions import CsrfExtender, SearchIndexExtender, ThrottleApiExtender
        from apps.core.extensions.system_runtime import (
            get_runtime_api_throttlers,
            get_runtime_csrf_exempt_routes,
            should_throttle_runtime_api_request,
        )

        class Item:
            pass

        class Indexer:
            pass

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        indexer = Indexer()
        request = RequestFactory().get("/api/demo")

        CsrfExtender().exempt_route("alpha-webhook").extend(app, extension)
        ThrottleApiExtender().set("alpha", lambda current_request: current_request.path == "/api/demo").extend(app, extension)
        SearchIndexExtender().indexer(Item, indexer).extend(app, extension)
        app.make("csrf")
        app.make("throttle.api")
        app.make("search")

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            routes = get_runtime_csrf_exempt_routes()
            throttlers = get_runtime_api_throttlers()
            throttled = should_throttle_runtime_api_request(request)

        self.assertEqual(routes, {"alpha-webhook"})
        self.assertEqual(list(throttlers.keys()), ["alpha"])
        self.assertTrue(throttled)
        self.assertEqual(app.search.indexers(Item), (indexer,))

    @override_settings(FRONTEND_URL="https://bias.test")
    def test_link_extender_registers_formatter_link_attribute_callbacks(self):
        from apps.core.extensions import LinkExtender
        from apps.core.extensions.formatter_service import apply_extension_formatters, clear_extension_formatter_cache

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        seen = []

        def rel(uri, site_url, attributes):
            seen.append((uri.netloc, site_url, attributes.get("href", "")))
            if uri.netloc == "external.test":
                return "nofollow sponsored"
            return ""

        def target(uri, site_url, attributes):
            if uri.netloc == "bias.test":
                return "_self"
            return "_blank"

        LinkExtender().set_rel(rel).set_target(target).extend(app, extension)
        app.make("formatters")

        clear_extension_formatter_cache()
        try:
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
                html = apply_extension_formatters(
                    '<p><a href="https://external.test/page">外部</a> '
                    '<a href="https://bias.test/d/1">内部</a></p>'
                )
        finally:
            clear_extension_formatter_cache()

        self.assertIn('href="https://external.test/page" rel="nofollow sponsored" target="_blank"', html)
        self.assertIn('href="https://bias.test/d/1" target="_self"', html)
        self.assertEqual(seen[0], ("external.test", "https://bias.test", "https://external.test/page"))

    def test_formatter_extender_registers_formatter_phases(self):
        from apps.core.extensions import FormatterExtender
        from apps.core.extensions.formatter_service import (
            apply_extension_formatter_config,
            apply_extension_formatter_parse,
            apply_extension_formatter_render,
            apply_extension_formatter_unparse,
            clear_extension_formatter_cache,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        FormatterExtender() \
            .configure(lambda config: {**config, "alpha": True}) \
            .parse(lambda text, context: text.replace(":alpha:", "alpha")) \
            .render(lambda html, context: html.replace("alpha", "<strong>alpha</strong>")) \
            .unparse(lambda text: text.replace("alpha", ":alpha:")) \
            .extend(app, extension)
        app.make("formatters")

        clear_extension_formatter_cache()
        try:
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
                self.assertTrue(apply_extension_formatter_config({})["alpha"])
                parsed = apply_extension_formatter_parse("hello :alpha:")
                rendered = apply_extension_formatter_render(parsed)
                unparsed = apply_extension_formatter_unparse("hello alpha")
        finally:
            clear_extension_formatter_cache()

        self.assertEqual(parsed, "hello alpha")
        self.assertEqual(rendered, "hello <strong>alpha</strong>")
        self.assertEqual(unparsed, "hello :alpha:")

    def test_language_pack_extender_registers_runtime_locale_metadata(self):
        from apps.core.extensions import LanguagePackExtender

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-lang")

        LanguagePackExtender(
            code="en-US",
            label="English",
            native_label="English",
            path="extensions/alpha-lang/locale",
        ).extend(app, extension)
        app.make("forum")
        app.make("locales")

        packs = app.forum_registry.get_language_packs(module_id="alpha-lang")

        self.assertEqual(packs[0].code, "en-US")
        self.assertEqual(packs[0].label, "English")
        self.assertEqual(app.locales.get_paths(extension_id="alpha-lang"), ["extensions/alpha-lang/locale"])

    def test_post_user_and_model_private_extenders_register_core_runtime(self):
        from apps.core.extensions import ModelPrivateExtender, PostExtender, UserExtender
        from apps.core.extensions.system_runtime import (
            apply_runtime_user_group_processors,
            get_runtime_user_avatar_drivers,
            get_runtime_user_display_name_drivers,
            get_runtime_user_preference_transformers,
        )

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        class DemoPost:
            type = "alphaEvent"
            label = "Alpha Event"

        class DemoModel:
            pass

        def group_processor(user, group_ids):
            return [*group_ids, user.extra_group_id]

        def preference_transformer(value):
            return value == "yes"

        PostExtender().type(DemoPost, description="Alpha post event").extend(app, extension)
        UserExtender() \
            .display_name_driver("alpha", "alpha.display") \
            .avatar_driver("alpha", "alpha.avatar") \
            .permission_groups(group_processor) \
            .register_preference("alpha_pref", preference_transformer, False, label="Alpha Pref") \
            .extend(app, extension)
        ModelPrivateExtender(DemoModel).checker(lambda instance: instance.is_private).extend(app, extension)

        app.make("forum")
        app.make("user")
        app.make("models")

        with patch("apps.core.extensions.system_runtime.get_runtime_system_service", side_effect=lambda key: app.make(key)):
            self.assertEqual(get_runtime_user_display_name_drivers()["alpha"], "alpha.display")
            self.assertEqual(get_runtime_user_avatar_drivers()["alpha"], "alpha.avatar")
            self.assertEqual(apply_runtime_user_group_processors(SimpleNamespace(extra_group_id=9), [1, 2]), [1, 2, 9])
            self.assertTrue(get_runtime_user_preference_transformers()["alpha_pref"]["transformer"]("yes"))

        post_type = app.forum.get_post_type("alphaEvent")
        runtime_view = app.get_runtime_view("alpha-tools")

        self.assertEqual(post_type.label, "Alpha Event")
        self.assertEqual(post_type.module_id, "alpha-tools")
        self.assertEqual(runtime_view.user_preferences[0].key, "alpha_pref")
        self.assertEqual(runtime_view.user_handlers[0].key, "display_name_driver")
        self.assertEqual(runtime_view.model_definitions[-1].kind, "private_checker")
        self.assertTrue(app.models.is_private(DemoModel, SimpleNamespace(is_private=True)))

    def test_model_visibility_scoper_matches_subclasses(self):
        from apps.core.extensions import ExtensionModelVisibilityDefinition

        class BaseModel:
            pass

        class ChildModel(BaseModel):
            pass

        app = ExtensionApplication()
        app.models.register_visibility(
            "alpha-tools",
            ExtensionModelVisibilityDefinition(
                model=BaseModel,
                ability="view",
                scope=lambda queryset, context: (*queryset, context["ability"]),
            ),
        )

        self.assertTrue(app.models.has_visibility(ChildModel, ability="view"))
        self.assertEqual(
            app.models.apply_visibility(ChildModel, ("base",), {"ability": "view"}),
            ("base", "view"),
        )

    def test_model_visibility_scopers_follow_parent_wildcard_ability_order(self):
        from apps.core.extensions import ExtensionModelVisibilityDefinition

        class BaseModel:
            pass

        class ChildModel(BaseModel):
            pass

        def append(name):
            return lambda queryset, context: (*queryset, name)

        app = ExtensionApplication()
        for name, model, ability in (
            ("child-view", ChildModel, "view"),
            ("base-view", BaseModel, "view"),
            ("child-any", ChildModel, "*"),
            ("base-any", BaseModel, "*"),
        ):
            app.models.register_visibility(
                "alpha-tools",
                ExtensionModelVisibilityDefinition(
                    model=model,
                    ability=ability,
                    scope=append(name),
                ),
            )

        self.assertEqual(
            app.models.apply_visibility(ChildModel, (), {"ability": "view"}),
            ("base-any", "base-view", "child-any", "child-view"),
        )

    def test_core_model_visibility_scopers_follow_parent_wildcard_ability_order(self):
        from apps.core.visibility import get_core_model_visibility_scopers, register_core_model_visibility_scoper

        class BaseModel:
            pass

        class ChildModel(BaseModel):
            pass

        calls = []
        for name, model, ability in (
            ("child-view", ChildModel, "view"),
            ("base-view", BaseModel, "view"),
            ("child-any", ChildModel, "*"),
            ("base-any", BaseModel, "*"),
        ):
            register_core_model_visibility_scoper(
                model,
                lambda queryset, context, marker=name: calls.append(marker) or queryset,
                ability=ability,
            )

        for scoper in get_core_model_visibility_scopers(ChildModel, ability="view"):
            scoper([], {"ability": "view"})

        self.assertEqual(calls, ["base-any", "base-view", "child-any", "child-view"])

    def test_model_visibility_query_policy_deny_returns_empty_queryset(self):
        from apps.core.visibility import apply_model_visibility_scope

        discussion_model = Discussion.model

        app = ExtensionApplication()
        app.policies.query_model_policy(
            "alpha-tools",
            discussion_model,
            lambda **context: False if context["ability"] == "view" else None,
        )

        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            queryset = apply_model_visibility_scope(
                discussion_model,
                discussion_model.objects.all(),
                user=AnonymousUser(),
                ability="view",
            )

        self.assertFalse(queryset.exists())

    def test_theme_extender_contributes_frontend_document_payload(self):
        from apps.core.extensions import SettingsExtender, ThemeExtender, setting_field
        from apps.core.extensions.frontend_runtime_service import build_enabled_frontend_document_payload

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        runtime_view = app.get_or_create_runtime_view("alpha-tools", name="Alpha Tools")

        ThemeExtender() \
            .variable("bias-alpha-color", "#123456") \
            .document_classes(["theme-alpha"]) \
            .head_tag("meta", {"name": "theme-alpha", "content": "1"}) \
            .extend(app, extension)
        SettingsExtender(fields=(
            setting_field({
                "key": "accent_color",
                "label": "Accent",
                "type": "text",
                "default": "#224466",
            }),
        )) \
            .theme_variable("bias-alpha-accent", "accent_color") \
            .extend(app, extension)
        app.make("theme")
        app.make("settings")

        from apps.core.extensions.frontend_runtime_service import _build_frontend_document_payload

        with patch("apps.core.extensions.frontend_runtime_service.get_extension_host", return_value=app):
            entry = {
                "id": "alpha-tools",
                "frontend_document": _build_frontend_document_payload(
                    runtime_view,
                    settings_values={"accent_color": "#335577"},
                ),
            }

        with patch("apps.core.extensions.frontend_runtime_service.get_enabled_extension_runtime_entries", return_value=[entry]):
            payload = build_enabled_frontend_document_payload()

        self.assertEqual(payload["theme_variables"]["bias-alpha-color"], "#123456")
        self.assertEqual(payload["theme_variables"]["bias-alpha-accent"], "#335577")
        self.assertEqual(payload["document_attributes"]["class"], ["theme-alpha"])
        self.assertEqual(payload["head_tags"][0]["attributes"]["name"], "theme-alpha")

    def test_settings_extender_serializes_forum_settings_with_alias_and_transform(self):
        from apps.core.extensions import SettingsExtender, setting_field
        from apps.core.extensions.frontend_runtime_service import _build_extension_forum_settings

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        SettingsExtender(fields=(
            setting_field({
                "key": "allow_username_format",
                "label": "Allow username format",
                "type": "boolean",
                "default": False,
            }),
        ), expose_to_forum=("allow_username_format",)) \
            .serialize_to_forum("allowUsernameMentionFormat", "allow_username_format", bool) \
            .extend(app, extension)
        app.make("settings")

        runtime_view = app.get_runtime_view("alpha-tools")
        payload = _build_extension_forum_settings(
            {
                "forum_settings_keys": tuple(runtime_view.forum_settings_keys),
                "forum_serializations": tuple(runtime_view.settings_forum_serializations),
            },
            {"allow_username_format": "1"},
        )

        self.assertEqual(payload["allow_username_format"], "1")
        self.assertTrue(payload["allowUsernameMentionFormat"])

    def test_frontend_runtime_treats_default_only_forum_settings_as_visible(self):
        from apps.core.extensions.frontend_runtime_service import _is_product_visible_frontend_extension

        extension = SimpleNamespace(source="filesystem", manifest=SimpleNamespace(extra={}))
        runtime_view = SimpleNamespace(
            settings_schema=(),
            settings_defaults=(SimpleNamespace(key="extensions.security.auth_human_verification_provider", value="off"),),
            settings_forum_serializations=(SimpleNamespace(
                attribute="auth_human_verification_provider",
                key="extensions.security.auth_human_verification_provider",
            ),),
            forum_settings_keys=(),
        )

        self.assertTrue(_is_product_visible_frontend_extension(
            extension,
            admin_entry="",
            forum_entry="",
            common_entry="",
            frontend_routes=(),
            runtime_view=runtime_view,
        ))

    def test_validator_extender_runs_during_resource_payload_application(self):
        from apps.core.resource_registry import ResourceRegistry
        from apps.core.resource_objects import Resource, ResourceField
        from apps.core.resource_errors import JsonApiValidationError

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def reject_bad_title(payload, context):
            if payload["payload"].get("title") == "bad":
                raise ValueError("title rejected")

        ValidatorExtender().validator("title", "validated", reject_bad_title).extend(app, extension)
        app.make("validators")

        class Target:
            title = "old"

        class ValidatedResource(Resource):
            def type(self):
                return "validated"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title).writable_when()]

        registry = ResourceRegistry()
        registry.register_resource(ValidatedResource())

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            with self.assertRaises(JsonApiValidationError):
                registry.apply_resource_payload("validated", Target(), {"title": "bad"})

    def test_validator_extender_matches_instance_class_targets(self):
        from apps.core.resource_registry import ResourceRegistry
        from apps.core.resource_objects import Resource, ResourceField
        from apps.core.resource_errors import JsonApiValidationError

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        class Target:
            title = "old"

        def reject_by_class(payload, context):
            if payload["payload"].get("title") == "bad":
                raise ValueError("class rejected")

        ValidatorExtender().validator("target", Target.__name__, reject_by_class).extend(app, extension)
        app.make("validators")

        class ValidatedResource(Resource):
            def type(self):
                return "validated-class"

            def fields(self):
                return [ResourceField("title", resolver=lambda instance, context: instance.title).writable_when()]

        registry = ResourceRegistry()
        registry.register_resource(ValidatedResource())

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            with self.assertRaises(JsonApiValidationError):
                registry.apply_resource_payload("validated-class", Target(), {"title": "bad"})

    def test_extension_lifecycle_extender_runs_on_state_changes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import LifecycleExtender\n"
                "from apps.core.models import ExtensionInstallation\n"
                "\n"
                "def state():\n"
                "    item = ExtensionInstallation.objects.get(extension_id='alpha-tools')\n"
                "    return item.installed, item.enabled, item.booted\n"
                "\n"
                "def install(context):\n"
                "    label = 'installed-target' if context.installed and not context.enabled and state() == (True, False, False) else 'installed-old-state'\n"
                "    return {'status': 'ok', 'status_label': label, 'message': context.extension_id}\n"
                "\n"
                "def enable(context):\n"
                "    label = 'enabled-target' if context.installed and context.enabled and context.booted and state() == (True, True, True) else 'enabled-old-state'\n"
                "    return {'status': 'ok', 'status_label': label}\n"
                "\n"
                "def disable(context):\n"
                "    label = 'disabled-target' if context.installed and not context.enabled and not context.booted and state() == (True, False, False) else 'disabled-old-state'\n"
                "    return {'status': 'ok', 'status_label': label}\n"
                "\n"
                "def uninstall(context):\n"
                "    label = 'uninstalled-target' if not context.installed and not context.enabled and not context.booted and state() == (False, False, False) else 'uninstalled-old-state'\n"
                "    return {'status': 'ok', 'status_label': label}\n"
                "\n"
                "def extend():\n"
                "    return [LifecycleExtender(install=install, enable=enable, disable=disable, uninstall=uninstall)]\n",
                encoding="utf-8",
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            installed = registry.install_extension("alpha-tools")
            self.assertEqual(installed.runtime.backend_hooks["run_install"]["status_label"], "installed-target")
            self.assertIn("lifecycle_results", installed.runtime.backend_hooks["run_install"]["details"])

            disabled = registry.set_extension_enabled("alpha-tools", False)
            self.assertEqual(disabled.runtime.backend_hooks["run_disable"]["status_label"], "disabled-target")
            enabled = registry.set_extension_enabled("alpha-tools", True)
            self.assertEqual(enabled.runtime.backend_hooks["run_enable"]["status_label"], "enabled-target")
            registry.set_extension_enabled("alpha-tools", False)
            uninstalled = registry.uninstall_extension("alpha-tools")
            self.assertEqual(uninstalled.runtime.backend_hooks["run_uninstall"]["status_label"], "uninstalled-target")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_lifecycle_error_blocks_state_transition(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import LifecycleExtender\n"
                "\n"
                "def enable(context):\n"
                "    return {'status': 'error', 'message': 'enable failed'}\n"
                "\n"
                "def extend():\n"
                "    return [LifecycleExtender(enable=enable)]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=False,
                installed=True,
                booted=False,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            with self.assertRaises(ExtensionStateError) as raised:
                registry.set_extension_enabled("alpha-tools", True)

            self.assertEqual(raised.exception.code, "extension_lifecycle_failed")
            installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
            self.assertFalse(installation.enabled)
            self.assertFalse(installation.booted)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_asset_publish_and_runtime_rebuild_marker(self):
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
                registry = ExtensionRegistry(extensions_path=extensions_dir)
                with self.captureOnCommitCallbacks(execute=True):
                    installed = registry.install_extension("alpha-tools")

                published_file = Path(temp_dir) / "static" / "extensions" / "alpha-tools" / "logo.txt"
                self.assertTrue(published_file.exists())
                self.assertEqual(installed.runtime.backend_hooks["publish_assets"]["status"], "ok")
                self.assertIn("run_enable", installed.runtime.backend_hooks)
                published_details = installed.runtime.backend_hooks["publish_assets"]["details"]
                self.assertEqual(published_details["files"][0]["path"], "logo.txt")
                self.assertIn("sha256", published_details["files"][0])
                self.assertIn("/static/extensions/alpha-tools/logo.txt", published_details["files"][0]["url"])
                self.assertTrue(published_details["cache_key"])

                rebuild_marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("extension_enabled", rebuild_marker.value)
                self.assertTrue(output_manifest.exists())
                self.assertTrue(build_manifest.exists())
                self.assertNotIn("stale", output_manifest.read_text(encoding="utf-8"))
                self.assertNotIn("stale", build_manifest.read_text(encoding="utf-8"))
                self.assertTrue(import_map.exists())
                import_map_source = import_map.read_text(encoding="utf-8")
                self.assertIn("generatedAdminExtensionModules", import_map_source)
                self.assertNotIn("staleExtensionModules", import_map_source)

                with self.captureOnCommitCallbacks(execute=True):
                    registry.set_extension_enabled("alpha-tools", False)
                self.assertFalse(published_file.exists())
                disabled_marker = Setting.objects.get(key="extensions_runtime_rebuild_required")
                self.assertIn("extension_disabled", disabled_marker.value)
                self.assertNotIn("alpha-tools", build_manifest.read_text(encoding="utf-8"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_runtime_version_survives_rebuild_marker_clear(self):
        from apps.core.extensions.lifecycle import (
            RUNTIME_REBUILD_MARKER_KEY,
            RUNTIME_VERSION_KEY,
            clear_extension_runtime_rebuild_marker,
            mark_extension_runtime_requires_rebuild,
        )

        mark_extension_runtime_requires_rebuild("extension_enabled", extension_id="alpha-tools")

        marker = Setting.objects.get(key=RUNTIME_REBUILD_MARKER_KEY)
        version = Setting.objects.get(key=RUNTIME_VERSION_KEY)
        self.assertIn("extension_enabled", marker.value)
        self.assertIn("alpha-tools", version.value)

        clear_extension_runtime_rebuild_marker()

        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())
        self.assertEqual(Setting.objects.get(key=RUNTIME_VERSION_KEY).value, version.value)

    def test_extension_runtime_invalidation_middleware_rebuilds_from_persistent_version(self):
        from apps.core.extensions.lifecycle import (
            RUNTIME_REBUILD_MARKER_KEY,
            clear_extension_runtime_rebuild_marker,
            mark_extension_runtime_requires_rebuild,
            reset_extension_runtime_version_seen,
        )
        from apps.core.middleware import ExtensionRuntimeInvalidationMiddleware

        mark_extension_runtime_requires_rebuild("extension_enabled", extension_id="alpha-tools")
        clear_extension_runtime_rebuild_marker()
        reset_extension_runtime_version_seen()

        request = RequestFactory().get("/api/forum")
        middleware = ExtensionRuntimeInvalidationMiddleware(lambda current_request: HttpResponse("ok"))
        with patch("apps.core.extensions.lifecycle.rebuild_extension_runtime_state") as rebuild_runtime:
            response = middleware(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())
        rebuild_runtime.assert_called_once_with()

    def test_extension_runtime_invalidation_middleware_uses_short_version_cache(self):
        from apps.core.extensions.lifecycle import mark_extension_runtime_version_seen, reset_extension_runtime_version_seen
        from apps.core.middleware import ExtensionRuntimeInvalidationMiddleware

        reset_extension_runtime_version_seen()
        mark_extension_runtime_version_seen("stable-version")

        request = RequestFactory().get("/api/forum")
        middleware = ExtensionRuntimeInvalidationMiddleware(lambda current_request: HttpResponse("ok"))
        with patch("apps.core.extensions.lifecycle.get_extension_runtime_version", return_value="stable-version") as get_version:
            first = middleware(request)
            second = middleware(request)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        get_version.assert_called_once_with()

    def test_maintenance_mode_exemption_skips_jwt_resolution_without_token(self):
        from apps.core.middleware import MaintenanceModeMiddleware

        request = RequestFactory().post("/api/discussions/")
        middleware = MaintenanceModeMiddleware(lambda current_request: HttpResponse("ok"))

        with patch("apps.core.middleware.resolve_authenticated_user") as resolve_user:
            exempt = middleware._is_exempt(request, mode="high")

        self.assertFalse(exempt)
        resolve_user.assert_not_called()

    def test_maintenance_mode_exemption_checks_jwt_when_token_present(self):
        from apps.core.jwt_auth import ACCESS_TOKEN_COOKIE_NAME
        from apps.core.middleware import MaintenanceModeMiddleware

        request = RequestFactory().post("/api/discussions/")
        request.COOKIES[ACCESS_TOKEN_COOKIE_NAME] = "token"
        middleware = MaintenanceModeMiddleware(lambda current_request: HttpResponse("ok"))
        staff = SimpleNamespace(is_staff=True)

        with patch("apps.core.middleware.resolve_authenticated_user", return_value=staff) as resolve_user:
            exempt = middleware._is_exempt(request, mode="high")

        self.assertTrue(exempt)
        resolve_user.assert_called_once_with(request)

    @override_settings(BIAS_EXTENSION_AUTO_FRONTEND_REBUILD=True, BIAS_EXTENSION_AUTO_FRONTEND_PUBLISH=True)
    def test_extension_runtime_invalidation_can_auto_rebuild_frontend_assets(self):
        from apps.core.extensions.lifecycle import (
            RUNTIME_REBUILD_MARKER_KEY,
            RUNTIME_VERSION_KEY,
            invalidate_extension_frontend_assets,
        )

        class CompileResult:
            def to_dict(self):
                return {"status": "ok", "message": "rebuilt"}

        Setting.objects.filter(key__in=[RUNTIME_REBUILD_MARKER_KEY, RUNTIME_VERSION_KEY]).delete()
        with patch(
            "apps.core.extensions.frontend_compiler.recompile_extension_frontend_assets",
            return_value=CompileResult(),
        ) as recompile:
            result = invalidate_extension_frontend_assets("extension_enabled", extension_id="alpha-tools")

        self.assertTrue(result["auto_rebuild"])
        self.assertTrue(result["auto_publish"])
        recompile.assert_called_once()
        self.assertTrue(recompile.call_args.kwargs["run_build"])
        self.assertTrue(recompile.call_args.kwargs["clear_marker"])
        self.assertTrue(recompile.call_args.kwargs["publish_dist"])
        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())
        self.assertIn("extension_enabled", Setting.objects.get(key=RUNTIME_VERSION_KEY).value)

    def test_build_extension_frontend_command_writes_manifest(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                backend_dir = manifest_dir / "backend"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                    "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id="alpha-tools",
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

                call_command("build_extension_frontend", stdout=StringIO())
                manifest = json.loads((Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json").read_text(encoding="utf-8"))
                self.assertIn("alpha-tools", manifest["extensions"])
                self.assertEqual(
                    manifest["extensions"]["alpha-tools"]["inputs"]["forum"],
                    "extensions/alpha-tools/frontend/forum/index.js",
                )
                self.assertTrue(manifest["extensions"]["alpha-tools"]["cache_key"])
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                self.assertTrue(import_map.exists())
                self.assertTrue(output_manifest.exists())
                import_map_source = import_map.read_text(encoding="utf-8")
                self.assertIn("generatedForumExtensionModules", import_map_source)
                self.assertIn("../../../extensions/alpha-tools/frontend/forum/index.js", import_map_source)
                output_payload = json.loads(output_manifest.read_text(encoding="utf-8"))
                self.assertIn("alpha-tools", output_payload["extensions"])
                self.assertTrue(output_payload["input_revision"])
                self.assertFalse(output_payload["build"]["ran"])
                inspected = inspect_extension_frontend_output_manifest()
                self.assertEqual(inspected["input_revision"], output_payload["input_revision"])
                self.assertEqual(inspected["current_input_revision"], output_payload["input_revision"])
                self.assertFalse(inspected["input_stale"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_output_manifest_maps_vite_chunks(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                vite_manifest = get_frontend_vite_manifest_path()
                vite_manifest.parent.mkdir(parents=True, exist_ok=True)
                vite_manifest.write_text(json.dumps({
                    "extensions/alpha-tools/frontend/forum/index.js": {
                        "file": "assets/alpha-forum.js",
                        "css": ["assets/alpha-forum.css"],
                        "imports": ["assets/vendor.js"],
                        "dynamicImports": ["../../../extensions/alpha-tools/frontend/forum/lazy.js"],
                    },
                    "../../../extensions/alpha-tools/frontend/forum/lazy.js": {
                        "file": "assets/chunk.js",
                        "css": ["assets/chunk.css"],
                        "imports": ["assets/vendor.js"],
                    },
                    "../../../extensions/alpha-tools/frontend/forum/Page.vue": {
                        "file": "assets/page.js",
                        "css": ["assets/page.css"],
                        "imports": ["assets/vendor.js"],
                    }
                }, ensure_ascii=False), encoding="utf-8")
                output = build_extension_frontend_output_manifest({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                            "admin_entry": "",
                            "routes": [{
                                "path": "/alpha",
                                "name": "alpha.page",
                                "component": "./Page.vue",
                                "frontend": "forum",
                            }],
                        }
                    }
                })

                forum_output = output["extensions"]["alpha-tools"]["outputs"]["forum"]
                self.assertTrue(output["revision"])
                self.assertTrue(output["input_revision"])
                self.assertEqual(output["extensions"]["alpha-tools"]["revision"], output["revision"])
                self.assertEqual(forum_output["revision"], output["revision"])
                self.assertEqual(forum_output["file"], "assets/alpha-forum.js")
                self.assertEqual(forum_output["css"], ["assets/alpha-forum.css"])
                self.assertEqual(forum_output["imports"], ["assets/vendor.js"])
                self.assertEqual(forum_output["dynamic_imports"], ["../../../extensions/alpha-tools/frontend/forum/lazy.js"])
                self.assertEqual(forum_output["chunks"][0]["module_id"], "frontend/forum/lazy.js")
                self.assertEqual(forum_output["chunks"][0]["file"], "assets/chunk.js")
                self.assertEqual(forum_output["chunks"][0]["css"], ["assets/chunk.css"])
                self.assertEqual(forum_output["chunks"][0]["revision"], output["revision"])
                self.assertEqual(forum_output["chunks"][1]["module_id"], "frontend/forum/Page.vue")
                self.assertEqual(forum_output["chunks"][1]["file"], "assets/page.js")
                self.assertEqual(forum_output["chunks"][1]["css"], ["assets/page.css"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_output_manifest_detects_stale_extension_inputs(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                first_manifest = {
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                        }
                    }
                }
                second_manifest = {
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/changed.js",
                        }
                    }
                }
                output = build_extension_frontend_output_manifest(first_manifest)
                write_extension_frontend_output_manifest(output)
                build_manifest_path = get_extension_frontend_build_manifest_path()
                build_manifest_path.parent.mkdir(parents=True, exist_ok=True)
                build_manifest_path.write_text(json.dumps(second_manifest, ensure_ascii=False), encoding="utf-8")

                inspected = inspect_extension_frontend_output_manifest()

                self.assertTrue(inspected["input_revision"])
                self.assertTrue(inspected["current_input_revision"])
                self.assertNotEqual(inspected["input_revision"], inspected["current_input_revision"])
                self.assertTrue(inspected["input_stale"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_recompile_extension_frontend_assets_reports_missing_npm(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extension = SimpleNamespace(
                    id="alpha-tools",
                    source="filesystem",
                    frontend_admin_entry="",
                    frontend_forum_entry="extensions/alpha-tools/frontend/forum/index.js",
                    manifest=SimpleNamespace(path=str(Path(temp_dir) / "extensions" / "alpha-tools")),
                    runtime=SimpleNamespace(enabled=True),
                    frontend_routes=(),
                    discover=lambda: SimpleNamespace(
                        frontend_css=(),
                        frontend_js_directories=(),
                        frontend_preloads=(),
                        frontend_document_attributes=(),
                        frontend_title_driver=None,
                        frontend_routes=(),
                    ),
                )
                with patch("apps.core.extensions.frontend_compiler.subprocess.run", side_effect=FileNotFoundError("npm")):
                    result = recompile_extension_frontend_assets([extension], run_build=True)

                self.assertEqual(result.status, "error")
                self.assertEqual(result.status_label, "编译环境缺失")
                self.assertIn("npm", result.message)
                self.assertTrue(result.input_revision)
                self.assertTrue(get_extension_frontend_output_manifest_path().exists())
                payload = json.loads(get_extension_frontend_output_manifest_path().read_text(encoding="utf-8"))
                self.assertEqual(payload["status"], "error")
                self.assertEqual(payload["status_label"], "编译环境缺失")
                self.assertEqual(payload["input_revision"], result.input_revision)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_output_manifest_maps_route_only_components(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                vite_manifest = get_frontend_vite_manifest_path()
                vite_manifest.parent.mkdir(parents=True, exist_ok=True)
                vite_manifest.write_text(json.dumps({
                    "../../../extensions/alpha-tools/frontend/admin/Page.vue": {
                        "file": "assets/admin-page.js",
                        "css": ["assets/admin-page.css"],
                    },
                    "../../../extensions/alpha-tools/frontend/forum/Page.vue": {
                        "file": "assets/forum-page.js",
                        "css": ["assets/forum-page.css"],
                    },
                }, ensure_ascii=False), encoding="utf-8")

                output = build_extension_frontend_output_manifest({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "admin_entry": "",
                            "forum_entry": "",
                            "routes": [
                                {
                                    "path": "/admin/alpha",
                                    "name": "alpha.admin",
                                    "component": "./Page.vue",
                                    "frontend": "admin",
                                },
                                {
                                    "path": "/alpha",
                                    "name": "alpha.page",
                                    "component": "./Page.vue",
                                    "frontend": "forum",
                                },
                            ],
                        }
                    }
                })

                outputs = output["extensions"]["alpha-tools"]["outputs"]
                self.assertEqual(outputs["admin"]["chunks"][0]["module_id"], "frontend/admin/Page.vue")
                self.assertEqual(outputs["admin"]["chunks"][0]["file"], "assets/admin-page.js")
                self.assertEqual(outputs["forum"]["chunks"][0]["module_id"], "frontend/forum/Page.vue")
                self.assertEqual(outputs["forum"]["chunks"][0]["file"], "assets/forum-page.js")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_import_map_uses_inputs_fallback(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                path = write_extension_frontend_import_map({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "inputs": {
                                "admin": "extensions/alpha-tools/frontend/admin/index.js",
                                "forum": "extensions/alpha-tools/frontend/forum/index.js",
                            },
                        }
                    }
                })

                source = path.read_text(encoding="utf-8")
                self.assertIn("../../../extensions/alpha-tools/frontend/admin/index.js", source)
                self.assertIn("../../../extensions/alpha-tools/frontend/forum/index.js", source)
                self.assertIn('"alpha-tools": () =>', source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_import_map_includes_css_and_route_components(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                path = write_extension_frontend_import_map({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                            "css": ["frontend/forum/style.css"],
                            "routes": [
                                {
                                    "path": "/admin/alpha",
                                    "name": "alpha.admin",
                                    "component": "./AdminPage.vue",
                                    "frontend": "admin",
                                },
                                {
                                    "path": "/alpha",
                                    "name": "alpha.page",
                                    "component": "./Page.vue",
                                    "frontend": "forum",
                                },
                            ],
                        }
                    }
                })

                source = path.read_text(encoding="utf-8")
                self.assertIn("loadExtensionModule", source)
                self.assertIn("../../../extensions/alpha-tools/frontend/forum/style.css", source)
                self.assertNotIn('"./AdminPage.vue": () => import(', source)
                self.assertIn('"extensions/alpha-tools/frontend/admin/AdminPage.vue": () => import("../../../extensions/alpha-tools/frontend/admin/AdminPage.vue")', source)
                self.assertIn('"alpha-tools:./AdminPage.vue": () => import("../../../extensions/alpha-tools/frontend/admin/AdminPage.vue")', source)
                self.assertNotIn('"./Page.vue": () => import(', source)
                self.assertIn('"extensions/alpha-tools/frontend/forum/Page.vue": () => import("../../../extensions/alpha-tools/frontend/forum/Page.vue")', source)
                self.assertIn('"alpha-tools:./Page.vue": () => import("../../../extensions/alpha-tools/frontend/forum/Page.vue")', source)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_frontend_import_map_deduplicates_keys_globally(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                path = write_extension_frontend_import_map({
                    "extensions": {
                        "alpha-tools": {
                            "extension_id": "alpha-tools",
                            "forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
                            "routes": [
                                {
                                    "path": "/alpha",
                                    "name": "alpha.page",
                                    "component": "extensions/shared/frontend/forum/SharedPage.vue",
                                    "frontend": "forum",
                                },
                            ],
                        },
                        "beta-tools": {
                            "extension_id": "beta-tools",
                            "forum_entry": "extensions/beta-tools/frontend/forum/index.js",
                            "routes": [
                                {
                                    "path": "/beta",
                                    "name": "beta.page",
                                    "component": "extensions/shared/frontend/forum/SharedPage.vue",
                                    "frontend": "forum",
                                },
                            ],
                        },
                    }
                })

                source = path.read_text(encoding="utf-8")
                self.assertEqual(
                    source.count('"extensions/shared/frontend/forum/SharedPage.vue": () => import("../../../extensions/shared/frontend/forum/SharedPage.vue")'),
                    1,
                )
                self.assertEqual(
                    source.count('"../../../extensions/shared/frontend/forum/SharedPage.vue": () => import("../../../extensions/shared/frontend/forum/SharedPage.vue")'),
                    1,
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_copy_frontend_dist_to_static_publishes_dist(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                dist_file = Path(temp_dir) / "frontend" / "dist" / "assets" / "main.js"
                dist_file.parent.mkdir(parents=True, exist_ok=True)
                dist_file.write_text("console.log('ok')", encoding="utf-8")

                result = copy_frontend_dist_to_static()

                published = get_published_frontend_root() / "assets" / "main.js"
                self.assertEqual(result["status"], "ok")
                self.assertTrue(published.exists())
                self.assertEqual(published.read_text(encoding="utf-8"), "console.log('ok')")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_build_extension_frontend_command_flushes_generated_assets(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                import_map = get_extension_frontend_import_map_path()
                output_manifest = get_extension_frontend_output_manifest_path()
                build_manifest = Path(temp_dir) / "static" / "extensions" / "frontend-build-manifest.json"
                import_map.parent.mkdir(parents=True, exist_ok=True)
                output_manifest.parent.mkdir(parents=True, exist_ok=True)
                build_manifest.parent.mkdir(parents=True, exist_ok=True)
                import_map.write_text("export const generatedAdminExtensionModules = {}\nexport const generatedForumExtensionModules = {}\n", encoding="utf-8")
                output_manifest.write_text("{}", encoding="utf-8")
                build_manifest.write_text("{}", encoding="utf-8")

                published_root = get_published_frontend_root()
                published_root.mkdir(parents=True, exist_ok=True)
                (published_root / "index.html").write_text("", encoding="utf-8")

                call_command("build_extension_frontend", "--flush", "--flush-published", stdout=StringIO())

                self.assertTrue(import_map.exists())
                self.assertIn("generatedForumExtensionModules", import_map.read_text(encoding="utf-8"))
                self.assertFalse(output_manifest.exists())
                self.assertFalse(build_manifest.exists())
                self.assertFalse(published_root.exists())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_extensions_command_prunes_missing_installations(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import EXTENSION_PACKAGE_LOCK_SETTING

                ExtensionInstallation.objects.create(
                    extension_id="missing-package",
                    version="1.0.0",
                    source="python-package",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

                stdout = StringIO()
                call_command("sync_extensions", stdout=stdout)
                installation = ExtensionInstallation.objects.get(extension_id="missing-package")
                self.assertFalse(installation.enabled)
                self.assertFalse(installation.booted)
                self.assertTrue(installation.meta["sync"]["missing"])
                lock = json.loads(Setting.objects.get(key=EXTENSION_PACKAGE_LOCK_SETTING).value)
                self.assertEqual(lock["schema"], 1)
                self.assertEqual(lock["packages"][0]["id"], "missing-package")
                self.assertTrue(lock["packages"][0]["missing"])
                self.assertIn("包锁定:", stdout.getvalue())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_extension_packages_creates_records_for_discovered_extensions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import EXTENSION_PACKAGE_LOCK_SETTING, ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "alpha-tools"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.0.0",
                    "backend_entry": "extensions.alpha_tools.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")

                result = ExtensionManager(extensions_path=extensions_dir).sync_extension_packages()

                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                lock = json.loads(Setting.objects.get(key=EXTENSION_PACKAGE_LOCK_SETTING).value)

            self.assertEqual(result["created"], ["alpha-tools"])
            self.assertEqual(result["updated"], [])
            self.assertEqual(result["package_inspection"]["summary"]["installation_record_count"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["unmanaged_discovered_count"], 1)
            self.assertFalse(installation.installed)
            self.assertFalse(installation.enabled)
            self.assertFalse(installation.booted)
            self.assertEqual(installation.version, "1.0.0")
            self.assertEqual(installation.source, "filesystem")
            self.assertTrue(installation.meta["sync"]["created"])
            self.assertEqual(lock["packages"][0]["id"], "alpha-tools")
            self.assertFalse(lock["packages"][0]["installed"])
            self.assertFalse(lock["packages"][0]["enabled"])
            self.assertFalse(lock["packages"][0]["missing"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_extension_packages_preserves_auto_install_runtime_state_when_creating_records(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "users"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "users",
                    "name": "Users",
                    "version": "1.0.0",
                    "extra": {
                        "auto_install": True,
                        "auto_enable": True,
                    },
                }, ensure_ascii=False), encoding="utf-8")

                result = ExtensionManager(extensions_path=extensions_dir).sync_extension_packages()

                installation = ExtensionInstallation.objects.get(extension_id="users")

            self.assertEqual(result["created"], ["users"])
            self.assertEqual(result["package_inspection"]["summary"]["installation_record_count"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["unmanaged_discovered_count"], 0)
            self.assertTrue(installation.installed)
            self.assertTrue(installation.enabled)
            self.assertTrue(installation.booted)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_protected_auto_enabled_extension_loads_enabled_from_stale_disabled_record(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "discussions"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "discussions",
                    "name": "Discussions",
                    "version": "1.0.0",
                    "extra": {
                        "auto_install": True,
                        "auto_enable": True,
                        "protected": True,
                    },
                }, ensure_ascii=False), encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id="discussions",
                    version="1.0.0",
                    source="filesystem",
                    installed=True,
                    enabled=False,
                    booted=False,
                )

                extension = ExtensionManager(extensions_path=extensions_dir).get_extension("discussions")

            self.assertTrue(extension.runtime.installed)
            self.assertTrue(extension.runtime.enabled)
            self.assertTrue(extension.runtime.booted)
            self.assertEqual(extension.runtime.status_key, "active")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_sync_extension_packages_repairs_protected_auto_enabled_disabled_record(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                from apps.core.extensions.manager import ExtensionManager

                extensions_dir = Path(temp_dir) / "extensions"
                manifest_dir = extensions_dir / "discussions"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": "discussions",
                    "name": "Discussions",
                    "version": "1.0.0",
                    "extra": {
                        "auto_install": True,
                        "auto_enable": True,
                        "protected": True,
                    },
                }, ensure_ascii=False), encoding="utf-8")
                ExtensionInstallation.objects.create(
                    extension_id="discussions",
                    version="1.0.0",
                    source="filesystem",
                    installed=True,
                    enabled=False,
                    booted=False,
                )

                result = ExtensionManager(extensions_path=extensions_dir).sync_extension_packages()
                installation = ExtensionInstallation.objects.get(extension_id="discussions")

            self.assertEqual(result["updated"], ["discussions"])
            self.assertTrue(installation.installed)
            self.assertTrue(installation.enabled)
            self.assertTrue(installation.booted)
            self.assertEqual(installation.meta["sync"]["reason"], "protected_extension_auto_enabled")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_rebuild_api_urlpatterns_is_idempotent_after_runtime_sync(self):
        import config.urls as root_urls

        first_patterns = root_urls.rebuild_api_urlpatterns()
        second_patterns = root_urls.rebuild_api_urlpatterns()

        self.assertTrue(first_patterns)
        self.assertTrue(second_patterns)
        self.assertNotEqual(root_urls.api.urls_namespace, "bias-api-1")

    @patch("apps.core.extensions.manifest.metadata.distributions")
    def test_sync_extension_packages_persists_distribution_package_lock(self, distributions_mock):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir), BIAS_EXTENSION_PACKAGE_DISCOVERY=True):
                from apps.core.extensions import manifest as manifest_module
                from apps.core.extensions.manager import EXTENSION_PACKAGE_LOCK_SETTING, ExtensionManager

                manifest_module._distribution_manifest_cache = None
                package_dir = Path(temp_dir) / "site-packages" / "alpha_tools" / "bias_extension"
                package_dir.mkdir(parents=True, exist_ok=False)
                (package_dir / "extension.json").write_text(json.dumps({
                    "id": "alpha-tools",
                    "name": "Alpha Tools",
                    "version": "1.2.3",
                    "abandoned": "vendor/beta-tools",
                }, ensure_ascii=False), encoding="utf-8")

                class DemoDistribution:
                    version = "1.2.3"
                    files = ("alpha_tools/bias_extension/extension.json",)
                    metadata = {"Name": "alpha-tools"}

                    def locate_file(self, file):
                        return Path(temp_dir) / "site-packages" / str(file)

                distributions_mock.return_value = [DemoDistribution()]
                ExtensionInstallation.objects.create(
                    extension_id="alpha-tools",
                    version="1.0.0",
                    source="filesystem",
                    enabled=True,
                    installed=True,
                    booted=True,
                )

                result = ExtensionManager(extensions_path=Path(temp_dir) / "extensions").sync_extension_packages()

                installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
                lock = json.loads(Setting.objects.get(key=EXTENSION_PACKAGE_LOCK_SETTING).value)

            self.assertEqual(result["discovered"], ["alpha-tools"])
            self.assertEqual(result["updated"], ["alpha-tools"])
            self.assertEqual(result["locked"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["locked_count"], 1)
            self.assertEqual(result["package_inspection"]["summary"]["missing_count"], 0)
            self.assertEqual(installation.version, "1.2.3")
            self.assertEqual(installation.source, "python-package")
            self.assertEqual(lock["packages"][0]["id"], "alpha-tools")
            self.assertEqual(lock["packages"][0]["source"], "python-package")
            self.assertEqual(lock["packages"][0]["distribution"]["name"], "alpha-tools")
            self.assertEqual(lock["packages"][0]["distribution"]["version"], "1.2.3")
            self.assertTrue(lock["packages"][0]["abandoned"])
            self.assertEqual(lock["packages"][0]["replacement"], "vendor/beta-tools")
            self.assertFalse(lock["packages"][0]["missing"])
            self.assertTrue(lock["packages"][0]["discovered"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_middleware_and_policy_mounts(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import MiddlewareExtender, PolicyExtender\n"
                "\n"
                "def demo_middleware(request):\n"
                "    return request\n"
                "\n"
                "def can_use_demo(user=None, **kwargs):\n"
                "    return True\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        MiddlewareExtender(mounts=(('api', demo_middleware, 30),)),\n"
                "        PolicyExtender(mounts=(('demo.use', can_use_demo),)),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.middleware_mounts), 1)
            self.assertEqual(runtime_view.middleware_mounts[0].target, "api")
            self.assertEqual(runtime_view.middleware_mounts[0].order, 30)
            self.assertEqual(len(runtime_view.policy_mounts), 1)
            self.assertEqual(runtime_view.policy_mounts[0].key, "demo.use")
            self.assertTrue(runtime_view.policy_mounts[0].handler())
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_realtime_included_enrichers(self):
        from apps.core.forum_runtime import (
            clear_realtime_service,
            iter_realtime_included_enrichers,
            iter_realtime_discussion_transports,
            resolve_realtime_visible_discussion_ids,
        )

        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import RealtimeExtender\n"
                "\n"
                "def enrich_alpha(**kwargs):\n"
                "    return {'alpha': [{'id': '1', 'value': 'ok'}]}\n"
                "\n"
                "def visible_discussions(discussion_ids, user):\n"
                "    return [int(item) for item in discussion_ids if int(item) == 2]\n"
                "\n"
                "def broadcast_alpha(discussion_id, event_type, payload):\n"
                "    return None\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        RealtimeExtender()\n"
                "            .included_payload('alpha', enrich_alpha, description='Alpha included payload')\n"
                "            .discussion_visibility(visible_discussions, description='Alpha discussion visibility')\n"
                "            .discussion_transport('alpha.websocket', broadcast_alpha, description='Alpha discussion transport'),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            clear_realtime_service()
            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.realtime_included), 1)
            self.assertEqual(runtime_view.realtime_included[0].key, "alpha")
            self.assertEqual(len(runtime_view.realtime_discussion_visibility), 1)
            self.assertEqual(len(runtime_view.realtime_discussion_transports), 1)
            self.assertEqual(application.realtime.get_included_enrichers(extension_id="alpha-tools")[0].description, "Alpha included payload")
            self.assertEqual(
                application.realtime.get_discussion_visibility_resolvers(extension_id="alpha-tools")[0].description,
                "Alpha discussion visibility",
            )
            self.assertEqual(
                application.realtime.get_discussion_transports(extension_id="alpha-tools")[0].description,
                "Alpha discussion transport",
            )
            included_payload = {}
            for enricher in iter_realtime_included_enrichers():
                included_payload.update(enricher())

            self.assertEqual(included_payload["alpha"][0]["value"], "ok")
            self.assertEqual(resolve_realtime_visible_discussion_ids([1, 2], Mock()), [2])
            self.assertEqual(len(iter_realtime_discussion_transports()), 1)
        finally:
            clear_realtime_service()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_registers_string_domain_event_listeners(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (extensions_dir / "__init__.py").write_text("", encoding="utf-8")
            package_dir = extensions_dir / "alpha_tools"
            package_backend_dir = package_dir / "backend"
            package_backend_dir.mkdir(parents=True, exist_ok=False)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_backend_dir / "__init__.py").write_text("", encoding="utf-8")
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import EventListenersExtender\n"
                "from apps.core.extensions import ExtensionEventListenerDefinition\n"
                "\n"
                "seen = []\n"
                "\n"
                "def record_alpha(event):\n"
                "    seen.append(event.value)\n"
                "\n"
                "def extend():\n"
                "    return [EventListenersExtender(listeners=(ExtensionEventListenerDefinition(\n"
                f"        event_type='{AlphaStringEvent.__module__}.{AlphaStringEvent.__name__}',\n"
                "        handler=record_alpha,\n"
                "        description='String event listener',\n"
                "    ),))]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            application.event_bus.dispatch(AlphaStringEvent(value="ok"))
            handler_state = runtime_view.event_listeners[0].handler.__globals__["seen"]

            self.assertIsNotNone(runtime_view)
            self.assertEqual(runtime_view.event_listeners[0].event_type, AlphaStringEvent)
            self.assertEqual(handler_state, ["ok"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_registers_extension_realtime_discussion_broadcasts(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (extensions_dir / "__init__.py").write_text("", encoding="utf-8")
            package_dir = extensions_dir / "alpha_tools"
            package_backend_dir = package_dir / "backend"
            package_backend_dir.mkdir(parents=True, exist_ok=False)
            (package_dir / "__init__.py").write_text("", encoding="utf-8")
            (package_backend_dir / "__init__.py").write_text("", encoding="utf-8")
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from dataclasses import dataclass\n"
                "from apps.core.domain_events import DomainEvent\n"
                "from apps.core.extensions import RealtimeExtender\n"
                "\n"
                "@dataclass(frozen=True)\n"
                "class AlphaDiscussionCreatedEvent(DomainEvent):\n"
                "    discussion_id: int\n"
                "    actor_user_id: int\n"
                "    is_approved: bool = True\n"
                "\n"
                "@dataclass(frozen=True)\n"
                "class AlphaDiscussionRenamedEvent(DomainEvent):\n"
                "    discussion_id: int\n"
                "    actor_user_id: int\n"
                "    old_title: str\n"
                "    new_title: str\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        RealtimeExtender().broadcast_discussion_event(\n"
                "            AlphaDiscussionRenamedEvent,\n"
                "            'discussion.renamed',\n"
                "            include_discussion=True,\n"
                "            description='Alpha realtime broadcast',\n"
                "        ).broadcast_discussion_event(\n"
                "            AlphaDiscussionCreatedEvent,\n"
                "            'discussion.created',\n"
                "            include_discussion=True,\n"
                "            condition=lambda event: event.is_approved,\n"
                "            description='Approved discussion broadcast',\n"
                "        ),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.realtime_discussion_broadcasts), 2)
            self.assertEqual(
                application.realtime.get_discussion_broadcasts(extension_id="alpha-tools")[0].description,
                "Alpha realtime broadcast",
            )
            broadcasts = application.realtime.get_discussion_broadcasts(extension_id="alpha-tools")
            renamed_event_type = broadcasts[0].event_type
            created_event_type = broadcasts[1].event_type
            broadcast = Mock()
            application.instance("realtime.discussion_broadcaster", broadcast)
            application.event_bus.dispatch(renamed_event_type(
                discussion_id=7,
                actor_user_id=3,
                old_title="Old title",
                new_title="New title",
            ))

            broadcast.assert_called_once_with(
                7,
                "discussion.renamed",
                include_discussion=True,
                include_post=False,
                post_id=None,
                post_id_getter=None,
                extension_context=None,
            )
            broadcast.reset_mock()

            application.event_bus.dispatch(created_event_type(
                discussion_id=8,
                actor_user_id=3,
                is_approved=False,
            ))
            application.event_bus.dispatch(created_event_type(
                discussion_id=8,
                actor_user_id=3,
                is_approved=True,
            ))

            broadcast.assert_called_once_with(
                8,
                "discussion.created",
                include_discussion=True,
                include_post=False,
                post_id=None,
                post_id_getter=None,
                extension_context=None,
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_forum_permission_checkers(self):
        from apps.core.forum_permissions import clear_forum_permission_checkers, has_forum_permission

        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ForumPermissionExtender\n"
                "\n"
                "def can_use_alpha(user, permission_names):\n"
                "    return 'alpha.use' in permission_names\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        ForumPermissionExtender().checker('alpha', can_use_alpha, description='Alpha permission checker'),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            clear_forum_permission_checkers()
            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")
            user = Mock(is_authenticated=True)

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.forum_permission_checkers), 1)
            self.assertEqual(runtime_view.forum_permission_checkers[0].key, "alpha")
            self.assertEqual(application.forum_permissions.get_checkers(extension_id="alpha-tools")[0].description, "Alpha permission checker")
            self.assertTrue(has_forum_permission(user, "alpha.use"))
            self.assertFalse(has_forum_permission(user, "alpha.missing"))
        finally:
            clear_forum_permission_checkers()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_discussion_lifecycle_handlers(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import DiscussionLifecycleExtender\n"
                "\n"
                "def prepare_create(**kwargs):\n"
                "    return {'prepared': kwargs['payload']['alpha']}\n"
                "\n"
                "def apply_create(state=None, **kwargs):\n"
                "    return {'applied': state['prepared']}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        DiscussionLifecycleExtender().handler('alpha', prepare_create=prepare_create, apply_create=apply_create, description='Alpha discussion lifecycle'),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.discussion_lifecycle), 1)
            self.assertEqual(runtime_view.discussion_lifecycle[0].key, "alpha")
            states = application.discussion_lifecycle.prepare_create(
                user=None,
                payload={"alpha": "ok"},
            )
            self.assertEqual(states["alpha"]["prepared"], "ok")
            results = application.discussion_lifecycle.apply_create(
                discussion=SimpleNamespace(id=1),
                states=states,
            )
            self.assertEqual(results["alpha"]["applied"], "ok")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_application_bootstrap_collects_extension_post_lifecycle_handlers(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import PostLifecycleExtender\n"
                "\n"
                "def apply_created(**kwargs):\n"
                "    return {'post_id': kwargs['post'].id, 'value': kwargs['context']['alpha']}\n"
                "\n"
                "def apply_hidden(**kwargs):\n"
                "    return {'post_id': kwargs['post'].id, 'hidden': kwargs['context']['is_hidden']}\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        PostLifecycleExtender().handler('alpha', apply_created=apply_created, apply_hidden=apply_hidden, description='Alpha post lifecycle'),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertIsNotNone(runtime_view)
            self.assertEqual(len(runtime_view.post_lifecycle), 1)
            self.assertEqual(runtime_view.post_lifecycle[0].key, "alpha")
            results = application.post_lifecycle.apply_created(
                post=SimpleNamespace(id=7),
                context={"alpha": "ok"},
            )
            self.assertEqual(results["alpha"]["post_id"], 7)
            self.assertEqual(results["alpha"]["value"], "ok")
            hidden_results = application.post_lifecycle.apply_hidden(
                post=SimpleNamespace(id=8),
                context={"is_hidden": True},
            )
            self.assertEqual(hidden_results["alpha"]["post_id"], 8)
            self.assertTrue(hidden_results["alpha"]["hidden"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_api_application_is_built_from_extension_host_routes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from ninja import Router\n"
                "from apps.core.extensions import ApiRoutesExtender\n"
                "router = Router()\n"
                "@router.get('/ping')\n"
                "def ping(request):\n"
                "    return {'ok': True}\n"
                "def extend():\n"
                "    return [ApiRoutesExtender(mounts=(('/ext/alpha-tools', router),), tags=('Alpha',))]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            api = application.make("api.application")

            paths = {item[0] for item in api._routers}
            self.assertIn("/ext/alpha-tools", paths)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_bias_style_conditional_model_search_and_api_resource_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ApiResourceExtender, ConditionalExtender, FrontendExtender, ModelExtender, ModelVisibilityExtender, SearchDriverExtender\n"
                "from apps.core.extensions import ExtensionModelCastDefinition, ExtensionModelDefaultDefinition, ExtensionModelDefinition, ExtensionModelRelationDefinition, ExtensionModelVisibilityDefinition, ExtensionResourceEndpointDefinition, ExtensionResourceFieldDefinition, ExtensionResourceFieldMutatorDefinition, ExtensionResourceRelationshipDefinition, ExtensionResourceSortDefinition, ExtensionSearchDriverDefinition\n"
                "from apps.core.extensions import SearchFilterDefinition\n"
                "from apps.core.resource_objects import Resource, ResourceEndpoint, ResourceField, ResourceSort\n"
                "\n"
                "class DemoModel:\n"
                "    pass\n"
                "\n"
                "class ChildDemoModel(DemoModel):\n"
                "    pass\n"
                "\n"
                "class AlphaResource(Resource):\n"
                "    module_id = 'alpha-tools'\n"
                "    def type(self):\n"
                "        return 'alpha_resource'\n"
                "    def base(self, model, context):\n"
                "        return {'id': 'alpha'}\n"
                "    def fields(self):\n"
                "        return [ResourceField('title', resolver=lambda model, context: 'alpha')]\n"
                "    def endpoints(self):\n"
                "        return [ResourceEndpoint('show', handler=lambda context: {'version': 1})]\n"
                "    def sorts(self):\n"
                "        return [ResourceSort('hot', handler=('hot',))]\n"
                "\n"
                "def visibility(queryset, context):\n"
                "    return ('visible', queryset, context['ability'])\n"
                "\n"
                "def parse(value):\n"
                "    return value.split(':', 1)[1] if value.startswith('alpha:') else None\n"
                "\n"
                "def apply(queryset, value, context):\n"
                "    return queryset\n"
                "\n"
                "def mutate(queryset, context):\n"
                "    return ('mutated', queryset, context['target'])\n"
                "\n"
                "def mutate_endpoint(endpoint):\n"
                "    return ('endpoint', endpoint)\n"
                "\n"
                "def mutate_owner_relationship(relationship):\n"
                "    return mutated_owner_relationship\n"
                "\n"
                "def mutate_sort(sort):\n"
                "    return ExtensionResourceSortDefinition(resource=sort.resource, sort=sort.sort, module_id=sort.module_id, handler={'name': 'newest-mutated'}, operation='add')\n"
                "\n"
                "def mutate_alpha_field(field):\n"
                "    return ExtensionResourceFieldDefinition(resource='alpha_resource', field=field.field, module_id='', resolver=lambda model, context: 'ALPHA')\n"
                "\n"
                "def mutate_alpha_endpoint(endpoint):\n"
                "    return ExtensionResourceEndpointDefinition(resource='alpha_resource', endpoint=endpoint.endpoint, module_id='', handler=lambda context: {'version': 2})\n"
                "\n"
                "def mutate_alpha_sort(sort):\n"
                "    return ExtensionResourceSortDefinition(resource='alpha_resource', sort=sort.sort, module_id='', handler=('-hot',))\n"
                "\n"
                "field = ExtensionResourceFieldDefinition(resource='forum', field='alpha', module_id='alpha-tools', resolver=lambda model, context: True)\n"
                "before_field = ExtensionResourceFieldDefinition(resource='forum', field='before_title', module_id='', resolver=lambda model, context: True)\n"
                "owner_relationship = ExtensionResourceRelationshipDefinition(resource='forum', relationship='owner', module_id='alpha-tools', resolver=lambda model, context: {'name': 'owner'}, select_related=('owner',))\n"
                "mutated_owner_relationship = ExtensionResourceRelationshipDefinition(resource='forum', relationship='owner', module_id='', resolver=lambda model, context: {'name': 'mutated'}, select_related=('owner_profile',))\n"
                "search_filter = SearchFilterDefinition(code='alpha', label='Alpha', module_id='alpha-tools', target='discussion', parser=parse, applier=apply)\n"
                "endpoint_add = ExtensionResourceEndpointDefinition(resource='forum', endpoint='store', module_id='alpha-tools', operation='add', mutator=lambda endpoint: {'name': 'store'})\n"
                "endpoint_before = ExtensionResourceEndpointDefinition(resource='forum', endpoint='before_store', module_id='', operation='add', mutator=lambda endpoint: {'name': 'before_store'})\n"
                "endpoint_first = ExtensionResourceEndpointDefinition(resource='forum', endpoint='first', module_id='', operation='add', mutator=lambda endpoint: {'name': 'first'})\n"
                "field_mutator = ExtensionResourceFieldMutatorDefinition(resource='forum', field='title', module_id='alpha-tools', mutator=lambda field: {'name': 'title', 'mutated': True})\n"
                "sort = ExtensionResourceSortDefinition(resource='forum', sort='newest', module_id='alpha-tools', handler={'name': 'newest'}, operation='add')\n"
                "old_sort = ExtensionResourceSortDefinition(resource='forum', sort='old', module_id='', handler={'name': 'old'}, operation='add')\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        FrontendExtender(forum_entry='forum.js').css('forum.css').js_directory('chunks').preload({'href': '/x.js', 'as': 'script'}).extra_document_attributes({'data-alpha': '1'}).extra_document_classes(['alpha-page', {'beta-page': True}]).title('AlphaTitle').route('/alpha', 'alpha', 'AlphaView', title='Alpha').remove_route('old-alpha'),\n"
                "        ApiResourceExtender(fields=(field,)).fields_before('title', before_field).relationships_with(owner_relationship).field(field_mutator).field(\n"
                "            'owner', mutate_owner_relationship\n"
                "        ).remove_fields('hidden').endpoint('show', mutate_endpoint).endpoint(endpoint_add).endpoints_before('store', endpoint_before).endpoints_before_all(endpoint_first).sort(sort, old_sort).sort('newest', mutate_sort).remove_sorts('old'),\n"
                "        ApiResourceExtender.from_resource(AlphaResource).field('title', mutate_alpha_field).endpoint('show', mutate_alpha_endpoint).sort('hot', mutate_alpha_sort),\n"
                "        ModelExtender(definitions=(ExtensionModelDefinition(model=DemoModel, key='alpha', handler='belongsToMany'),)).relationship(\n"
                "            ExtensionModelRelationDefinition(model=DemoModel, name='owner', resolver=lambda model: ('owner', model), relation_type='belongsTo')\n"
                "        ).has_one(\n"
                "            'owner_profile', DemoModel, model=DemoModel, foreign_key='owner_id', local_key='id'\n"
                "        ).has_many(\n"
                "            'children', DemoModel, model=DemoModel, foreign_key='parent_id', local_key='id'\n"
                "        ).cast(\n"
                "            ExtensionModelCastDefinition(model=DemoModel, attribute='meta', cast='json')\n"
                "        ).default(\n"
                "            ExtensionModelDefaultDefinition(model=DemoModel, attribute='enabled', value=True)\n"
                "        ),\n"
                "        ModelVisibilityExtender(definitions=(ExtensionModelVisibilityDefinition(model=DemoModel, ability='view', scope=visibility),)),\n"
                "        SearchDriverExtender(drivers=(ExtensionSearchDriverDefinition(target='discussion', driver='database', filters=(search_filter,), mutators=(mutate,), searchers=('tag-searcher',), fulltext='fulltext'),)),\n"
                "        ConditionalExtender().when_extension_enabled('alpha-tools', lambda: ApiResourceExtender(fields=(\n"
                "            ExtensionResourceFieldDefinition(resource='forum', field='conditional', module_id='alpha-tools', resolver=lambda model, context: True),\n"
                "        ))),\n"
                "    ]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            registry = ExtensionRegistry(extensions_path=extensions_dir)
            application = build_extension_application(manager=registry, force=True)
            runtime_view = application.get_runtime_view("alpha-tools")

            self.assertEqual([item.field for item in runtime_view.resource_fields], ["alpha", "conditional"])
            self.assertEqual([item.module_id for item in runtime_view.resource_field_mutators if item.field in {"before_title", "owner", "hidden"}], ["alpha-tools", "alpha-tools", "alpha-tools"])
            self.assertEqual(runtime_view.resource_endpoints[0].endpoint, "show")
            self.assertEqual(runtime_view.resource_sorts[0].sort, "newest")
            self.assertEqual(runtime_view.model_definitions[0].key, "alpha")
            self.assertEqual(runtime_view.model_relations[0].name, "owner")
            self.assertEqual([item.relation_type for item in runtime_view.model_relations], ["belongsTo", "hasOne", "hasMany"])
            self.assertEqual(runtime_view.model_relations[1].foreign_key, "owner_id")
            self.assertEqual(runtime_view.model_relations[2].owner_key, "id")
            self.assertEqual(runtime_view.model_casts[0].attribute, "meta")
            self.assertEqual(runtime_view.model_defaults[0].attribute, "enabled")
            self.assertEqual(runtime_view.frontend_forum_entry, "forum.js")
            self.assertEqual(runtime_view.frontend_css, ("forum.css",))
            self.assertEqual(runtime_view.frontend_js_directories, ("chunks",))
            self.assertEqual(runtime_view.frontend_preloads[0]["as"], "script")
            self.assertEqual(runtime_view.frontend_document_attributes[0]["data-alpha"], "1")
            self.assertEqual(runtime_view.frontend_title_driver, "AlphaTitle")
            self.assertEqual(runtime_view.frontend_routes[0].path, "/alpha")
            self.assertEqual(runtime_view.frontend_routes[0].module_id, "alpha-tools")
            self.assertEqual(runtime_view.frontend_routes[1].name, "old-alpha")
            self.assertTrue(runtime_view.frontend_routes[1].removed)
            self.assertIn({"class": ["alpha-page", {"beta-page": True}]}, runtime_view.frontend_document_attributes)
            self.assertEqual(runtime_view.search_drivers[0].target, "discussion")
            self.assertEqual(runtime_view.search_drivers[0].mutators[0].__name__, "mutate")
            self.assertEqual(runtime_view.search_drivers[0].searchers, ("tag-searcher",))
            self.assertEqual(runtime_view.search_drivers[0].fulltext, "fulltext")
            self.assertFalse(any(item.code == "alpha" for item in application.forum.get_search_filters("discussion")))
            self.assertEqual(
                application.models.get_definitions_for_model(runtime_view.model_definitions[0].model)[0].key,
                "alpha",
            )
            child_model = runtime_view.model_relations[0].resolver.__globals__["ChildDemoModel"]
            self.assertEqual(application.models.get_definitions_for_model(child_model)[0].key, "alpha")
            self.assertEqual(
                application.models.apply_visibility(runtime_view.model_definitions[0].model, "base", {"ability": "view"}),
                ("visible", "base", "view"),
            )
            self.assertEqual(
                application.models.apply_visibility(runtime_view.model_definitions[0].model, "base", {"ability": "edit"}),
                "base",
            )
            self.assertEqual(application.search.get_searchers("discussion"), ["tag-searcher"])
            self.assertEqual(application.search.get_fulltext_handlers("discussion"), ["fulltext"])
            self.assertEqual(application.search.apply_mutators("discussion", "base", {"target": "discussion"}), ("mutated", "base", "discussion"))
            self.assertEqual(application.resources.apply_endpoint_mutators("forum", "show", "base"), ("endpoint", "base"))
            self.assertEqual(
                application.resources.apply_endpoint_definitions("forum", [{"name": "index"}]),
                [{"name": "first"}, {"name": "index"}, {"name": "before_store"}, {"name": "store"}],
            )
            self.assertEqual(
                application.resources.apply_endpoint_definitions("forum", [{"name": "store"}]),
                [{"name": "first"}, {"name": "before_store"}, {"name": "store"}, {"name": "store"}],
            )
            field_definitions = application.resources.apply_field_definitions("forum", [{"name": "title"}, {"name": "hidden"}])
            self.assertEqual(getattr(field_definitions[0], "field", ""), "before_title")
            self.assertEqual(field_definitions[1], {"name": "title", "mutated": True})
            self.assertEqual(len(field_definitions), 2)
            self.assertEqual(
                application.resources.apply_payload_field_mutators("forum", {"title": {"name": "title"}}),
                {"title": {"name": "title", "mutated": True}},
            )
            resource_payload = application.resources.serialize("forum", SimpleNamespace(), include=("owner",))
            resource_plan = application.resources.build_preload_plan("forum", include=("owner",))
            self.assertEqual(resource_payload["owner"], {"name": "mutated"})
            self.assertEqual(resource_plan.select_related, ("owner_profile",))
            self.assertEqual(application.resources.apply_sort_definitions("forum", []), [{"name": "newest-mutated"}])
            alpha_payload = application.resources.serialize("alpha_resource", SimpleNamespace())
            alpha_endpoint = application.resources.get_dispatch_endpoint("alpha_resource", "show", "GET")
            alpha_queryset = Mock()
            alpha_ordered_queryset = Mock()
            alpha_queryset.order_by.return_value = alpha_ordered_queryset
            self.assertEqual(alpha_payload, {"id": "alpha", "title": "ALPHA"})
            self.assertEqual(alpha_endpoint.handler({}), {"version": 2})
            self.assertIs(application.resources.apply_named_sort("alpha_resource", alpha_queryset, "hot"), alpha_ordered_queryset)
            alpha_queryset.order_by.assert_called_once_with("-hot")
            self.assertEqual(application.models.resolve_relation(runtime_view.model_definitions[0].model, "owner", "demo"), ("owner", "demo"))
            self.assertEqual(application.models.resolve_relation(child_model, "owner", "child"), ("owner", "child"))
            child_instance = child_model()
            self.assertEqual(child_instance.owner, ("owner", child_instance))
            self.assertEqual(application.models.get_casts_for_model(runtime_view.model_definitions[0].model), {"meta": "json"})
            self.assertEqual(application.models.get_casts_for_model(child_model), {"meta": "json"})
            self.assertEqual(application.models.get_defaults_for_model(runtime_view.model_definitions[0].model), {"enabled": True})
            self.assertEqual(application.models.get_defaults_for_model(child_model), {"enabled": True})
            runtime_text_query, runtime_filters = application.search.extract_filter_tokens(
                "alpha:1 body",
                targets=("discussion",),
            )
            self.assertEqual(runtime_text_query, "body")
            self.assertEqual(runtime_filters["discussion"][0][0].code, "alpha")
            self.assertTrue(any(
                item.code == "alpha"
                for item in application.search.get_available_filters(targets=("discussion",))
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_dependency_sort_detects_cycles_and_persists_enabled_order(self):
        alpha = Extension.from_manifest(ExtensionManifest(
            id="alpha",
            name="Alpha",
            version="1.0.0",
            dependencies=("beta",),
            source="filesystem",
        ))
        beta = Extension.from_manifest(ExtensionManifest(
            id="beta",
            name="Beta",
            version="1.0.0",
            dependencies=("alpha",),
            source="filesystem",
        ))
        manager = ExtensionRegistry()
        with self.assertRaises(ExtensionStateError) as raised:
            manager.sort_extensions_for_boot([alpha, beta])
        self.assertEqual(raised.exception.code, "extension_dependency_cycle")

        core = Extension.from_manifest(ExtensionManifest(
            id="core",
            name="Core",
            version="1.0.0",
            source="filesystem",
        ))
        tags = Extension.from_manifest(ExtensionManifest(
            id="tags",
            name="Tags",
            version="1.0.0",
            dependencies=("core",),
            source="filesystem",
        ))
        ordered = manager.sort_extensions_for_boot([tags, core])
        self.assertEqual([item.id for item in ordered], ["core", "tags"])

        notifications = Extension.from_manifest(ExtensionManifest(
            id="notifications",
            name="Notifications",
            version="1.0.0",
            dependencies=("core",),
            source="filesystem",
        ))
        likes = Extension.from_manifest(ExtensionManifest(
            id="likes",
            name="Likes",
            version="1.0.0",
            dependencies=("notifications",),
            source="filesystem",
        ))
        ordered = manager.sort_extensions_for_boot([likes, tags, notifications, core])
        self.assertEqual([item.id for item in ordered], ["core", "notifications", "tags", "likes"])

    def test_extension_enabled_order_sync_reports_and_repairs_drift(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            beta_dir = extensions_dir / "beta"
            alpha_dir = extensions_dir / "alpha"
            beta_dir.mkdir(parents=True, exist_ok=False)
            alpha_dir.mkdir(parents=True, exist_ok=False)
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta",
                "name": "Beta",
                "version": "1.0.0",
                "dependencies": ["alpha"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha",
                "name": "Alpha",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")
            ExtensionInstallation.objects.create(
                extension_id="alpha",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )
            ExtensionInstallation.objects.create(
                extension_id="beta",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )
            Setting.objects.update_or_create(
                key="extensions_enabled_order",
                defaults={"value": json.dumps(["beta", "alpha", "missing"], ensure_ascii=False)},
            )

            manager = ExtensionRegistry(extensions_path=extensions_dir)
            before = manager.inspect_enabled_extension_order(force=True)
            self.assertTrue(before["drift"])
            self.assertEqual(before["persisted"], ["beta", "alpha", "missing"])
            self.assertEqual(before["resolved"], ["alpha", "beta"])
            self.assertEqual(before["stale"], ["missing"])

            result = manager.sync_enabled_extension_order()

            self.assertTrue(result["changed"])
            self.assertEqual(result["after"]["persisted"], ["alpha", "beta"])
            self.assertFalse(result["after"]["drift"])
            persisted = Setting.objects.get(key="extensions_enabled_order")
            self.assertEqual(json.loads(persisted.value), ["alpha", "beta"])
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_site_extend_file_contributes_runtime_extenders_without_module_registration(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with override_settings(BASE_DIR=Path(temp_dir)):
                extensions_dir = Path(temp_dir) / "extensions"
                extensions_dir.mkdir(parents=True, exist_ok=False)
                (Path(temp_dir) / "extend.py").write_text(
                    "from apps.core.extensions import SettingsExtender\n"
                    "\n"
                    "def extend():\n"
                    "    return [SettingsExtender().default('site.local_enabled', True)]\n",
                    encoding="utf-8",
                )

                application = build_extension_application(
                    manager=ExtensionRegistry(extensions_path=extensions_dir),
                    forum_registry=ForumRegistry(),
                    event_bus=DomainEventBus(),
                    force=True,
                )
                application.make("settings")

                site_view = application.get_runtime_view("site")
                self.assertIsNotNone(site_view)
                self.assertEqual(site_view.source, "site")
                self.assertTrue(any(
                    item.key == "site.local_enabled"
                    and item.value is True
                    and item.module_id == "site"
                    for item in site_view.settings_defaults
                ))
                self.assertNotIn(
                    "site",
                    {module.module_id for module in application.forum.get_modules()},
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_bootstrap_populates_shared_registries_at_startup(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            manifest_dir = extensions_dir / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import AdminSurfaceExtender, ApiResourceExtender, EventListenersExtender\n"
                "from apps.core.extensions import ExtensionEventListenerDefinition, ExtensionResourceDefinition\n"
                "from apps.core.extensions import PermissionDefinition\n"
                "\n"
                "def _serialize(instance, context):\n"
                "    return {'ok': True}\n"
                "\n"
                "def _handle(event):\n"
                "    return None\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        AdminSurfaceExtender(permissions=(\n"
                "            PermissionDefinition(code='alpha.manage', label='管理 Alpha', section='admin', section_label='后台', module_id='alpha-tools'),\n"
                "        )),\n"
                "        ApiResourceExtender.from_resource(\n"
                "            ExtensionResourceDefinition(resource='alpha', module_id='alpha-tools', resolver=_serialize),\n"
                "        ),\n"
                "        EventListenersExtender(listeners=(\n"
                "            ExtensionEventListenerDefinition(event_type=object, handler=_handle),\n"
                "        )),\n"
                "    ]\n",
                encoding="utf-8",
            )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            manager = ExtensionRegistry(extensions_path=extensions_dir)
            forum_registry = ForumRegistry()
            event_bus = DomainEventBus()
            resource_registry = ResourceRegistry()

            with patch("apps.core.extensions.bootstrap.get_extension_registry", return_value=manager), patch(
                "apps.core.forum_registry.get_forum_registry",
                return_value=forum_registry,
            ), patch(
                "apps.core.domain_events.get_forum_event_bus",
                return_value=event_bus,
            ), patch(
                "apps.core.resource_registry.get_resource_registry",
                return_value=resource_registry,
            ):
                application = bootstrap_extension_application(force=True)

            self.assertIsNotNone(application)
            self.assertTrue(any(item.code == "alpha.manage" for item in forum_registry.get_all_permissions()))
            self.assertIsNotNone(resource_registry.get_resource("alpha"))
            self.assertIn(object, event_bus._listeners)
        finally:
            reset_extension_application_bootstrap_state()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_catalogs_disabled_extensions_without_running_extenders(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            for extension_id, permission in (
                ("alpha-tools", "alpha.manage"),
                ("beta-tools", "beta.manage"),
            ):
                manifest_dir = extensions_dir / extension_id
                backend_dir = manifest_dir / "backend"
                manifest_dir.mkdir(parents=True, exist_ok=False)
                backend_dir.mkdir(parents=True, exist_ok=False)
                (manifest_dir / "extension.json").write_text(json.dumps({
                    "id": extension_id,
                    "name": extension_id.title(),
                    "version": "1.0.0",
                    "backend_entry": f"extensions.{extension_id.replace('-', '_')}.backend.ext",
                }, ensure_ascii=False), encoding="utf-8")
                (backend_dir / "ext.py").write_text(
                    "from apps.core.extensions import AdminSurfaceExtender\n"
                    "from apps.core.extensions import PermissionDefinition\n"
                    "\n"
                    "def extend():\n"
                    "    return [AdminSurfaceExtender(permissions=(\n"
                    f"        PermissionDefinition(code='{permission}', label='{permission}', section='admin', section_label='后台', module_id='{extension_id}'),\n"
                    "    ))]\n",
                    encoding="utf-8",
                )

            ExtensionInstallation.objects.create(
                extension_id="alpha-tools",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )
            ExtensionInstallation.objects.create(
                extension_id="beta-tools",
                version="1.0.0",
                source="filesystem",
                enabled=False,
                installed=True,
                booted=False,
            )

            application = build_extension_application(
                manager=ExtensionRegistry(extensions_path=extensions_dir),
                forum_registry=ForumRegistry(),
                resource_registry=ResourceRegistry(),
                event_bus=DomainEventBus(),
                force=True,
            )
            modules = {module.module_id: module for module in application.forum.get_modules()}

            self.assertTrue(modules["alpha-tools"].enabled)
            self.assertFalse(modules["beta-tools"].enabled)
            self.assertTrue(any(item.code == "alpha.manage" for item in application.forum.get_all_permissions()))
            self.assertFalse(any(item.code == "beta.manage" for item in application.forum.get_all_permissions()))
            self.assertIsNotNone(application.get_runtime_view("alpha-tools"))
            self.assertIsNone(application.get_runtime_view("beta-tools"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_application_resolving_callbacks_do_not_reapply_previous_callbacks(self):
        application = ExtensionApplication()
        application.instance("actions", [])

        application.resolving("actions", lambda actions, host: [*actions, "first"])
        application.resolving("actions", lambda actions, host: [*actions, "second"])

        self.assertEqual(application.get("actions"), ["first", "second"])


    def test_loader_rejects_invalid_extension_id_and_version(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "Bad_Extension"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "Bad_Extension",
                "name": "Bad Extension",
                "version": "1.0",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            with self.assertRaisesMessage(Exception, f"扩展清单 id 非法: {manifest_dir / 'extension.json'}"):
                loader.discover()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
