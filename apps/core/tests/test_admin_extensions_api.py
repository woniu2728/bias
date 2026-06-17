from apps.core.tests.common import *

@override_settings(BIAS_EXTENSION_PACKAGE_DISCOVERY=False)
class AdminExtensionsApiTests(TestCase):
    def setUp(self):
        self.extension_base_dir = make_extension_test_base_dir()
        self.settings_override = override_settings(BASE_DIR=self.extension_base_dir)
        self.settings_override.enable()
        reset_extension_runtime_state()
        self.addCleanup(self._cleanup_extension_base_dir)
        self.admin = User.objects.create_superuser(
            username="admin-extensions",
            email="admin-extensions@example.com",
            password="password123",
        )

    def _cleanup_extension_base_dir(self):
        reset_extension_runtime_state()
        self.settings_override.disable()
        reset_extension_runtime_state()
        shutil.rmtree(self.extension_base_dir, ignore_errors=True)

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extensions_api_returns_filesystem_extension_snapshot(self):
        response = self.client.get(
            "/api/admin/extensions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("summary", payload)
        self.assertIn("extensions", payload)
        self.assertGreaterEqual(payload["summary"]["extension_count"], 1)
        self.assertGreaterEqual(payload["summary"]["filesystem_count"], 1)
        self.assertGreaterEqual(payload["summary"]["product_visible_count"], 1)
        self.assertIn("blocking_count", payload["summary"])
        self.assertIn("warning_count", payload["summary"])
        self.assertIn("attention_count", payload["summary"])
        self.assertIn("frontend_bundle_count", payload["summary"])
        self.assertIn("migration_bundle_count", payload["summary"])

        extension_ids = {item["id"] for item in payload["extensions"]}
        self.assertNotIn("core", extension_ids)
        self.assertIn("posts", extension_ids)
        self.assertIn("discussions", extension_ids)
        self.assertIn("users", extension_ids)
        self.assertIn("realtime", extension_ids)
        self.assertIn("tags", extension_ids)
        self.assertIn("alpha-tools", extension_ids)

        users_extension = next(item for item in payload["extensions"] if item["id"] == "users")
        self.assertEqual(users_extension["source"], "filesystem")
        self.assertTrue(users_extension["product_visible"])
        self.assertTrue(users_extension["protected"])
        self.assertIn("认证基础域", users_extension["protected_reason"])
        self.assertFalse(any(action["action"] == "disable" for action in users_extension["runtime_actions"]))
        self.assertIn("/admin/extensions/users/permissions", users_extension["permissions_pages"])

        discussions_extension = next(item for item in payload["extensions"] if item["id"] == "discussions")
        self.assertEqual(discussions_extension["source"], "filesystem")
        self.assertTrue(discussions_extension["product_visible"])
        self.assertEqual(
            discussions_extension["frontend_admin_entry"],
            "extensions/discussions/frontend/admin/index.js",
        )
        self.assertIn("/admin/extensions/discussions/permissions", discussions_extension["permissions_pages"])

        posts_extension = next(item for item in payload["extensions"] if item["id"] == "posts")
        self.assertEqual(posts_extension["source"], "filesystem")
        self.assertTrue(posts_extension["product_visible"])
        self.assertTrue(posts_extension["protected"])
        self.assertFalse(any(action["action"] == "disable" for action in posts_extension["runtime_actions"]))
        self.assertIn("post-types", posts_extension["provides"])

        realtime_extension = next(item for item in payload["extensions"] if item["id"] == "realtime")
        self.assertEqual(realtime_extension["source"], "filesystem")
        self.assertTrue(realtime_extension["product_visible"])
        self.assertIn("core", realtime_extension["dependencies"])

        sample_extension = next(item for item in payload["extensions"] if item["id"] == "alpha-tools")
        self.assertEqual(sample_extension["source"], "filesystem")
        self.assertFalse(sample_extension["product_visible"])
        self.assertEqual(sample_extension["frontend_admin_entry"], "extensions/alpha-tools/frontend/admin/index.js")
        self.assertIn("/admin/extensions/alpha-tools/settings", sample_extension["settings_pages"])
        self.assertIn("/admin/extensions/alpha-tools/permissions", sample_extension["permissions_pages"])
        self.assertEqual(sample_extension["compatibility"]["bias_version"], "^1.0.0")
        self.assertEqual(sample_extension["compatibility"]["api_stability"], "experimental")
        self.assertEqual(sample_extension["distribution"]["channel"], "private")
        self.assertTrue(sample_extension["distribution"]["abandoned"])
        self.assertEqual(sample_extension["distribution"]["replacement"], "beta-tools")
        self.assertEqual(sample_extension["action_links"]["settings_page"], "/admin/extensions/alpha-tools/settings")
        self.assertEqual(sample_extension["action_links"]["permissions_page"], "/admin/extensions/alpha-tools/permissions")
        self.assertTrue(any(item["key"] == "welcome_message" for item in sample_extension["settings_schema"]))
        self.assertEqual(sample_extension["admin_actions"][0]["key"], "details")
        self.assertTrue(any(action["key"] == "documentation" for action in sample_extension["admin_actions"]))
        self.assertTrue(any(action["action"] == "hook:run_rebuild_cache" for action in sample_extension["runtime_actions"]))

    @patch("apps.core.extension_detail.orchestrator.inspect_extension_frontend_output_manifest")
    def test_extensions_api_reuses_frontend_output_manifest_snapshot(self, inspect_manifest):
        inspect_manifest.return_value = {
            "extensions": {},
        }

        response = self.client.get(
            "/api/admin/extensions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertGreater(len(response.json()["extensions"]), 1)
        inspect_manifest.assert_called_once()

    def test_extensions_sync_api_prunes_missing_installations_and_returns_package_lock(self):
        ExtensionInstallation.objects.create(
            extension_id="missing-package",
            version="1.0.0",
            source="python-package",
            enabled=True,
            installed=True,
            booted=True,
        )

        response = self.client.post(
            "/api/admin/extensions/sync",
            data=json.dumps({"prune_missing": True}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        installation = ExtensionInstallation.objects.get(extension_id="missing-package")
        self.assertFalse(installation.enabled)
        self.assertFalse(installation.booted)
        self.assertTrue(installation.meta["sync"]["missing"])
        payload = response.json()
        package_lock = payload["runtime"]["package_lock"]
        self.assertGreaterEqual(package_lock["summary"]["missing_count"], 1)
        self.assertIn("missing-package", package_lock["missing"])
        missing_record = next(item for item in package_lock["packages"] if item["id"] == "missing-package")
        self.assertTrue(missing_record["missing"])

    def test_extensions_sync_order_api_repairs_enabled_order_drift(self):
        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "1.0.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        Setting.objects.update_or_create(
            key="extensions_enabled_order",
            defaults={"value": json.dumps(["alpha-tools", "missing-package"], ensure_ascii=False)},
        )

        response = self.client.get(
            "/api/admin/extensions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        before_order = response.json()["runtime"]["package_lock"]["enabled_order"]
        self.assertTrue(before_order["drift"])
        self.assertIn("missing-package", before_order["stale"])

        response = self.client.post(
            "/api/admin/extensions/sync-order",
            data=json.dumps({}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        after_order = response.json()["runtime"]["package_lock"]["enabled_order"]
        self.assertFalse(after_order["drift"])
        self.assertEqual(after_order["stale"], [])
        self.assertEqual(after_order["persisted"], after_order["resolved"])

    def test_extensions_rebuild_frontend_api_runs_build_and_returns_payload(self):
        from apps.core.extensions.lifecycle import RUNTIME_REBUILD_MARKER_KEY, mark_extension_runtime_requires_rebuild

        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "1.0.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        mark_extension_runtime_requires_rebuild("extension_enabled", extension_id="alpha-tools")

        class CompileResult:
            def to_dict(self):
                return {
                    "status": "ok",
                    "status_label": "已编译",
                    "message": "rebuilt",
                    "extension_count": 1,
                    "returncode": 0,
                    "output_manifest": {
                        "extensions": {
                            "alpha-tools": {
                                "outputs": {"admin": {"entry": "assets/alpha.js"}},
                            },
                        },
                    },
                }

        with patch(
            "apps.core.extension_service.recompile_extension_frontend_assets",
            return_value=CompileResult(),
        ) as recompile:
            response = self.client.post(
                "/api/admin/extensions/rebuild-frontend",
                data=json.dumps({"run_build": True, "include_disabled": False}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        recompile.assert_called_once()
        self.assertTrue(recompile.call_args.kwargs["run_build"])
        self.assertTrue(recompile.call_args.kwargs["clear_marker"])
        self.assertFalse(recompile.call_args.kwargs["publish_dist"])
        payload = response.json()
        self.assertEqual(payload["frontend_rebuild"]["status"], "ok")
        self.assertIn("extensions", payload)
        self.assertFalse(Setting.objects.filter(key=RUNTIME_REBUILD_MARKER_KEY).exists())

    def test_extensions_rebuild_frontend_api_can_generate_manifest_only(self):
        from apps.core.extensions.lifecycle import RUNTIME_REBUILD_MARKER_KEY

        class CompileResult:
            def to_dict(self):
                return {
                    "status": "ok",
                    "status_label": "已生成",
                    "message": "manifest built",
                    "extension_count": 1,
                    "returncode": None,
                }

        with patch(
            "apps.core.extension_service.recompile_extension_frontend_assets",
            return_value=CompileResult(),
        ) as recompile:
            response = self.client.post(
                "/api/admin/extensions/rebuild-frontend",
                data=json.dumps({"run_build": False}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(recompile.call_args.kwargs["run_build"])
        self.assertFalse(recompile.call_args.kwargs["clear_marker"])
        self.assertIn("extension_frontend_manifest_built", Setting.objects.get(key=RUNTIME_REBUILD_MARKER_KEY).value)

    def test_extension_detail_api_returns_extension_actions(self):
        response = self.client.get(
            "/api/admin/extensions/alpha-tools",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["id"], "alpha-tools")
        self.assertEqual(payload["action_links"]["detail_page"], "/admin/extensions/alpha-tools")
        self.assertEqual(payload["action_links"]["settings_page"], "/admin/extensions/alpha-tools/settings")
        self.assertEqual(payload["action_links"]["permissions_page"], "/admin/extensions/alpha-tools/permissions")
        self.assertEqual(payload["action_links"]["operations_page"], "/admin/extensions/alpha-tools/operations")
        self.assertEqual(payload["frontend_admin_entry"], "extensions/alpha-tools/frontend/admin/index.js")
        self.assertEqual(payload["admin_actions"][0]["key"], "details")
        self.assertEqual(payload["runtime_status"]["key"], "pending_install")
        self.assertEqual(payload["runtime_actions"][0]["action"], "install")
        self.assertEqual(payload["compatibility"]["bias_version"], "^1.0.0")
        self.assertEqual(payload["compatibility"]["api_stability_label"], "实验性")
        self.assertEqual(payload["distribution"]["channel_label"], "私有分发")
        self.assertTrue(payload["distribution"]["abandoned"])
        self.assertEqual(payload["distribution"]["replacement"], "beta-tools")
        self.assertEqual(payload["security"]["support_email"], "security@bias.local")
        self.assertEqual(payload["homepage"], "https://bias.local/extensions/alpha-tools")
        self.assertEqual(payload["authors"], ["Alpha Maintainer", "Security Contact"])
        self.assertEqual(payload["links"]["authors"][0], {
            "name": "Alpha Maintainer",
            "link": "https://bias.local/authors/alpha",
        })
        self.assertEqual(payload["links"]["authors"][1], {
            "name": "Security Contact",
            "link": "mailto:security-author@bias.local",
        })
        self.assertEqual(payload["links"]["documentation"], "https://bias.local/docs/alpha-tools")
        self.assertEqual(payload["links"]["website"], "https://bias.local/extensions/alpha-tools")
        self.assertEqual(payload["links"]["support"], "mailto:security@bias.local")
        self.assertEqual(payload["links"]["source"], "https://bias.local/source/alpha-tools")
        self.assertEqual(payload["links"]["discuss"], "https://bias.local/discuss/alpha-tools")
        self.assertTrue(payload["readme"]["available"])
        self.assertIn("<h1", payload["readme"]["html"])
        self.assertIn("Alpha Tools README", payload["readme"]["html"])
        self.assertEqual(payload["operations_profile"]["kicker"], "Alpha Runtime")
        self.assertIn("settings", payload["operations_profile"]["recommended_action_keys"])
        self.assertTrue(any(item["key"] == "card_tone" for item in payload["settings_schema"]))
        self.assertEqual(payload["settings_values"]["welcome_message"], "欢迎使用 Alpha Tools")
        self.assertIn("diagnostics", payload)
        self.assertIn("delivery_assets", payload)
        self.assertGreaterEqual(payload["delivery_assets"]["asset_count"], 4)
        self.assertTrue(any(item["key"] == "backend_entry" and item["exists"] for item in payload["delivery_assets"]["assets"]))
        self.assertTrue(any(item["key"] == "frontend_admin_entry" and item["exists"] for item in payload["delivery_assets"]["assets"]))
        self.assertTrue(payload["diagnostics"]["warning"])
        self.assertFalse(payload["diagnostics"]["blocking"])
        self.assertIn("迁移状态待完善", payload["diagnostics"]["warning_reasons"])
        self.assertTrue(any(item["key"] == "migrations" for item in payload["delivery_checks"]))
        self.assertTrue(any("不会自动回滚数据库迁移" in item for item in payload["uninstall_warnings"]))
        self.assertIsNone(payload["migration_execution"])
        self.assertEqual(payload["debug_info"]["manifest_path"], str(Path(settings.BASE_DIR) / "extensions" / "alpha-tools"))
        self.assertEqual(payload["debug_info"]["frontend_admin_entry"]["entry_type"], "filesystem")
        self.assertTrue(payload["debug_info"]["frontend_admin_entry"]["exists"])
        self.assertIn("resolveDetailPage", payload["debug_info"]["frontend_admin_entry"]["available_exports"])
        self.assertEqual(payload["debug_info"]["frontend_forum_entry"]["entry_type"], "filesystem")
        self.assertTrue(payload["debug_info"]["frontend_forum_entry"]["exists"])
        self.assertIn("0001_bootstrap.py", payload["migration_plan"]["pending_files"])
        self.assertTrue(any(
            item["key"] == "settings"
            and item["matches_expected"]
            and item["declared"] == "/admin/extensions/alpha-tools/settings"
            for item in payload["debug_info"]["route_bindings"]
        ))
        self.assertTrue(any(
            item["key"] == "frontend_forum_entry"
            and item["matches_expected"]
            and item["declared"] == "extensions/alpha-tools/frontend/forum/index.js"
            for item in payload["debug_info"]["route_bindings"]
        ))
        self.assertTrue(any(
            item["key"] == "settings"
            and item["mode"] == "custom"
            and item["mode_label"] == "自定义组件"
            for item in payload["debug_info"]["admin_surface_statuses"]
        ))
        self.assertEqual(payload["debug_info"]["validation_issues"], [])
        self.assertEqual(payload["backend_hooks"], [])
        self.assertEqual(payload["permission_summary"]["permission_count"], 0)
        self.assertEqual(payload["permission_summary"]["section_count"], 0)
        self.assertEqual(payload["permission_modules"], [])
        self.assertEqual(payload["permission_sections"], [])
        self.assertEqual(payload["admin_page_details"], [])

    def test_extension_detail_api_surfaces_runtime_system_hooks(self):
        ext_path = self.extension_base_dir / "extensions" / "alpha-tools" / "backend" / "ext.py"
        ext_path.write_text(
            "from __future__ import annotations\n"
            "\n"
            "from apps.core.extensions import ConsoleExtender, CsrfExtender, ThrottleApiExtender\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        ConsoleExtender().command('alpha:refresh', lambda payload, context: {'ok': True}, description='Alpha refresh', order=20),\n"
            "        CsrfExtender().exempt_route('alpha-webhook', description='Alpha webhook', order=30),\n"
            "        ThrottleApiExtender().set('alpha', lambda request: False, description='Alpha throttler', order=40),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "0.1.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        sys.modules.pop("extensions.alpha_tools.backend.ext", None)
        reset_extension_runtime_state()

        response = self.client.get(
            "/api/admin/extensions/alpha-tools",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        hooks = response.json()["extension"]["debug_info"]["system_hooks"]
        hook_keys = {
            (item["service"], item["key"], item["order"], item["description"])
            for item in hooks
        }
        self.assertIn(("console", "command", 20, "Alpha refresh"), hook_keys)
        self.assertIn(("csrf", "exempt_route", 30, "Alpha webhook"), hook_keys)
        self.assertIn(("throttle.api", "throttler", 40, "Alpha throttler"), hook_keys)

    def test_extension_detail_api_surfaces_settings_frontend_and_theme_runtime(self):
        ext_path = self.extension_base_dir / "extensions" / "alpha-tools" / "backend" / "ext.py"
        ext_path.write_text(
            "from __future__ import annotations\n"
            "\n"
            "from apps.core.extensions import FrontendExtender, SettingsExtender, ThemeExtender, setting_field\n"
            "\n"
            "def is_default(value):\n"
            "    return value == 'primary'\n"
            "\n"
            "def expose_upper(value):\n"
            "    return str(value or '').upper()\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        SettingsExtender(fields=(\n"
            "            setting_field({'key': 'card_tone', 'label': '卡片风格', 'type': 'text', 'default': 'primary'}),\n"
            "        ))\n"
            "            .default('card_tone', 'primary')\n"
            "            .reset_when('card_tone', is_default)\n"
            "            .reset_frontend_cache_for('card_tone')\n"
            "            .theme_variable('bias-alpha-card-tone', 'card_tone', expose_upper)\n"
            "            .serialize_to_forum('alphaCardTone', 'card_tone', expose_upper),\n"
            "        FrontendExtender(forum_entry='extensions/alpha-tools/frontend/forum/index.js')\n"
            "            .preload({'href': '/assets/alpha.css', 'as': 'style'})\n"
            "            .extra_document_attributes({'data-alpha': '1'})\n"
            "            .content('alpha.content', priority=90)\n"
            "            .title('AlphaTitle'),\n"
            "        ThemeExtender()\n"
            "            .variables({'bias-alpha-accent': '#335577'})\n"
            "            .document_classes(['alpha-theme'])\n"
            "            .head_tag('meta', {'name': 'alpha-theme', 'content': 'enabled'}),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.update_or_create(
            extension_id="alpha-tools",
            defaults={
                "version": "0.1.0",
                "source": "filesystem",
                "enabled": True,
                "installed": True,
                "booted": True,
            },
        )
        Setting.objects.update_or_create(
            key="extensions.alpha-tools.card_tone",
            defaults={"value": json.dumps("warm", ensure_ascii=False)},
        )
        sys.modules.pop("extensions.alpha_tools.backend.ext", None)
        reset_extension_runtime_state()

        response = self.client.get(
            "/api/admin/extensions/alpha-tools",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        debug_info = response.json()["extension"]["debug_info"]
        settings_runtime = debug_info["settings_runtime"]
        self.assertEqual(settings_runtime["defaults"], [{
            "key": "card_tone",
            "value": "primary",
            "module_id": "alpha-tools",
        }])
        self.assertEqual(settings_runtime["reset_rules"][0]["key"], "card_tone")
        self.assertEqual(settings_runtime["reset_rules"][0]["callback"], "is_default")
        self.assertEqual(settings_runtime["frontend_cache_keys"], ["card_tone"])
        self.assertEqual(settings_runtime["theme_variables"][0]["name"], "bias-alpha-card-tone")
        self.assertEqual(settings_runtime["theme_variables"][0]["callback"], "expose_upper")
        self.assertEqual(settings_runtime["forum_serializations"][0]["attribute"], "alphaCardTone")
        self.assertEqual(settings_runtime["forum_serializations"][0]["callback"], "expose_upper")

        frontend_document = debug_info["frontend_document"]
        self.assertEqual(frontend_document["preloads"], [{"href": "/assets/alpha.css", "as": "style"}])
        self.assertIn({"data-alpha": "1"}, frontend_document["document_attributes"])
        self.assertIn({"class": ["alpha-theme"]}, frontend_document["document_attributes"])
        self.assertEqual(frontend_document["title_driver"], "AlphaTitle")
        self.assertEqual(frontend_document["content_callbacks"], [{"callback": "alpha.content", "priority": 90}])
        self.assertIn({"bias-alpha-card-tone": "WARM"}, frontend_document["theme_variables"])
        self.assertIn({"bias-alpha-accent": "#335577"}, frontend_document["theme_variables"])
        self.assertEqual(frontend_document["head_tags"][0]["attributes"]["name"], "alpha-theme")

        theme_runtime = debug_info["theme_runtime"]
        self.assertTrue(any(item["key"] == "variables" for item in theme_runtime["handlers"]))
        self.assertEqual(theme_runtime["variables"], [{"bias-alpha-accent": "#335577"}])
        self.assertEqual(theme_runtime["document_attributes"], [{"class": ["alpha-theme"]}])
        self.assertEqual(theme_runtime["head_tags"][0]["attributes"]["name"], "alpha-theme")

    @patch("apps.core.extension_settings_service.get_extension_settings", return_value={})
    @patch("apps.core.extension_settings_service.serialize_extension_settings_schema", return_value=[])
    @patch("apps.core.admin_content_api.get_extension_registry")
    def test_extension_detail_api_prefers_contract_runtime_surfaces(
        self,
        get_extension_registry_mock,
        _serialize_extension_settings_schema,
        _get_extension_settings,
    ):
        manifest = ExtensionManifest(
            id="contract-first",
            name="Contract First",
            version="1.0.0",
            frontend_admin_entry="",
            frontend_forum_entry="",
            settings_pages=(),
            permissions_pages=(),
            operations_pages=(),
            admin_actions=(),
            path=str(Path.cwd() / "extensions" / "alpha-tools"),
        )
        extension = Extension(
            manifest=ExtensionManifest(
                id="contract-first",
                name="Contract First",
                version="1.0.0",
                frontend_admin_entry="extensions/alpha-tools/frontend/admin/index.js",
                frontend_forum_entry="extensions/alpha-tools/frontend/forum/index.js",
                settings_pages=("/admin/extensions/contract-first/settings",),
                permissions_pages=("/admin/extensions/contract-first/permissions",),
                operations_pages=("/admin/extensions/contract-first/operations",),
                admin_actions=(
                    ExtensionAdminActionDefinition(
                        key="settings",
                        label="设置",
                        kind="route",
                        target="/admin/extensions/contract-first/settings",
                        order=20,
                    ),
                ),
                path=str(Path.cwd() / "extensions" / "alpha-tools"),
            ),
            source="filesystem",
        )
        get_extension_registry_mock.return_value = SimpleNamespace(
            extensions_path=Path.cwd() / "extensions",
            get_extension=lambda extension_id: extension,
            get_extensions=lambda: [extension],
        )

        response = self.client.get(
            "/api/admin/extensions/contract-first",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_admin_entry"], "extensions/alpha-tools/frontend/admin/index.js")
        self.assertEqual(payload["frontend_forum_entry"], "extensions/alpha-tools/frontend/forum/index.js")
        self.assertEqual(payload["settings_pages"], ["/admin/extensions/contract-first/settings"])
        self.assertEqual(payload["permissions_pages"], ["/admin/extensions/contract-first/permissions"])
        self.assertEqual(payload["operations_pages"], ["/admin/extensions/contract-first/operations"])
        self.assertEqual(payload["action_links"]["settings_page"], "/admin/extensions/contract-first/settings")
        self.assertEqual(payload["action_links"]["permissions_page"], "/admin/extensions/contract-first/permissions")
        self.assertEqual(payload["action_links"]["operations_page"], "/admin/extensions/contract-first/operations")
        self.assertEqual(payload["admin_actions"][0]["key"], "settings")
        self.assertTrue(any(
            item["key"] == "settings"
            and item["declared"] == "/admin/extensions/contract-first/settings"
            for item in payload["debug_info"]["route_bindings"]
        ))

    def test_extension_settings_api_can_read_and_save_declared_schema(self):
        response = self.client.get(
            "/api/admin/extensions/alpha-tools/settings",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["extension_id"], "alpha-tools")
        self.assertTrue(any(item["key"] == "card_tone" for item in payload["schema"]))
        self.assertEqual(payload["settings"]["card_tone"], "primary")

        save_response = self.client.post(
            "/api/admin/extensions/alpha-tools/settings",
            data=json.dumps({
                "welcome_message": "新的欢迎语",
                "card_tone": "warm",
                "show_runtime_tips": False,
            }),
            content_type="application/json",
            **self.auth_header(),
        )
        self.assertEqual(save_response.status_code, 200, save_response.content)
        saved_payload = save_response.json()
        self.assertEqual(saved_payload["settings"]["welcome_message"], "新的欢迎语")
        self.assertEqual(saved_payload["settings"]["card_tone"], "warm")
        self.assertFalse(saved_payload["settings"]["show_runtime_tips"])
        self.assertEqual(
            json.loads(Setting.objects.get(key="extensions.alpha-tools.welcome_message").value),
            "新的欢迎语",
        )

    def test_extension_settings_api_rejects_unknown_key(self):
        response = self.client.post(
            "/api/admin/extensions/alpha-tools/settings",
            data=json.dumps({"unknown_key": "x"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_settings_unknown_key")

    def test_extensions_api_can_install_disable_enable_and_uninstall_extension(self):
        install_response = self.client.post(
            "/api/admin/extensions/alpha-tools/install",
            **self.auth_header(),
        )

        self.assertEqual(install_response.status_code, 200, install_response.content)
        installed_payload = install_response.json()
        self.assertIn("extension", installed_payload)
        self.assertNotIn("extensions", installed_payload)
        installed_extension = installed_payload["extension"]
        self.assertTrue(installed_extension["installed"])
        self.assertTrue(installed_extension["enabled"])
        self.assertEqual(installed_extension["runtime_status"]["key"], "active")
        self.assertEqual(installed_extension["migration_state"], "applied")
        self.assertEqual(installed_extension["migration_label"], "最近已执行")
        self.assertEqual(installed_extension["migration_execution"]["state"], "applied")
        self.assertEqual(installed_extension["migration_execution"]["status"], "ok")
        self.assertEqual(installed_extension["migration_plan"]["pending_files"], [])
        self.assertIn("0001_bootstrap.py", installed_extension["migration_plan"]["applied_files"])
        self.assertTrue(any(item["hook"] == "run_install" for item in installed_extension["backend_hooks"]))
        self.assertTrue(any(item["hook"] == "run_migrations" for item in installed_extension["backend_hooks"]))
        self.assertTrue(any(item["action"] == "migrations" for item in installed_extension["runtime_actions"]))
        self.assertTrue(any(item["action"] == "hook:run_rebuild_cache" for item in installed_extension["runtime_actions"]))

        disable_response = self.client.post(
            "/api/admin/extensions/alpha-tools/disable",
            **self.auth_header(),
        )

        self.assertEqual(disable_response.status_code, 200, disable_response.content)
        disabled_payload = disable_response.json()
        disabled_extension = disabled_payload["extension"]
        self.assertFalse(disabled_extension["enabled"])
        self.assertEqual(disabled_extension["runtime_status"]["key"], "disabled")
        self.assertTrue(any(item["action"] == "uninstall" for item in disabled_extension["runtime_actions"]))
        self.assertTrue(any(item["hook"] == "run_disable" for item in disabled_extension["backend_hooks"]))

        installation = ExtensionInstallation.objects.get(extension_id="alpha-tools")
        self.assertFalse(installation.enabled)
        self.assertFalse(installation.booted)
        self.assertIn("run_install", installation.meta["backend_hooks"])
        self.assertIn("run_disable", installation.meta["backend_hooks"])

        enable_response = self.client.post(
            "/api/admin/extensions/alpha-tools/enable",
            **self.auth_header(),
        )

        self.assertEqual(enable_response.status_code, 200, enable_response.content)
        enabled_payload = enable_response.json()
        enabled_extension = enabled_payload["extension"]
        self.assertTrue(enabled_extension["enabled"])
        self.assertTrue(any(item["hook"] == "run_enable" for item in enabled_extension["backend_hooks"]))

        runtime_hook_response = self.client.post(
            "/api/admin/extensions/alpha-tools/runtime-hooks/run_rebuild_cache",
            **self.auth_header(),
        )
        self.assertEqual(runtime_hook_response.status_code, 200, runtime_hook_response.content)
        runtime_hook_payload = runtime_hook_response.json()
        runtime_hook_extension = runtime_hook_payload["extension"]
        self.assertTrue(any(item["hook"] == "run_rebuild_cache" for item in runtime_hook_extension["backend_hooks"]))

        migrations_response = self.client.post(
            "/api/admin/extensions/alpha-tools/migrations",
            **self.auth_header(),
        )
        self.assertEqual(migrations_response.status_code, 200, migrations_response.content)
        migrations_payload = migrations_response.json()
        migrations_extension = migrations_payload["extension"]
        self.assertTrue(any(item["hook"] == "run_migrations" for item in migrations_extension["backend_hooks"]))
        self.assertEqual(migrations_extension["migration_label"], "最近已执行")
        self.assertEqual(migrations_extension["migration_execution"]["state"], "applied")

        installation.refresh_from_db()
        self.assertTrue(installation.enabled)
        self.assertTrue(installation.booted)
        self.assertIn("0001_bootstrap.py", installation.meta["applied_migration_files"])

        disable_response = self.client.post(
            "/api/admin/extensions/alpha-tools/disable",
            **self.auth_header(),
        )
        self.assertEqual(disable_response.status_code, 200, disable_response.content)

        uninstall_response = self.client.post(
            "/api/admin/extensions/alpha-tools/uninstall",
            **self.auth_header(),
        )
        self.assertEqual(uninstall_response.status_code, 200, uninstall_response.content)
        uninstalled_payload = uninstall_response.json()
        uninstalled_extension = uninstalled_payload["extension"]
        self.assertFalse(uninstalled_extension["installed"])
        self.assertFalse(uninstalled_extension["enabled"])
        self.assertEqual(uninstalled_extension["runtime_status"]["key"], "pending_install")
        self.assertTrue(any(item["hook"] == "run_uninstall" for item in uninstalled_extension["backend_hooks"]))

        installation.refresh_from_db()
        self.assertFalse(installation.installed)
        self.assertFalse(installation.enabled)
        self.assertFalse(installation.booted)

    def test_extensions_api_ignores_stale_core_installation_dependency_record(self):
        self.client.post(
            "/api/admin/extensions/alpha-tools/install",
            **self.auth_header(),
        )
        self.client.post(
            "/api/admin/extensions/alpha-tools/disable",
            **self.auth_header(),
        )

        ExtensionInstallation.objects.create(
            extension_id="core",
            version="1.0.0",
            source="core-module",
            enabled=False,
            installed=True,
            booted=False,
        )

        response = self.client.post(
            "/api/admin/extensions/alpha-tools/enable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        sample_extension = payload["extension"]
        self.assertTrue(sample_extension["enabled"])

    def test_extensions_api_blocks_enable_when_extension_not_installed(self):
        response = self.client.post(
            "/api/admin/extensions/alpha-tools/enable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_enable_not_installed")

    @patch("apps.core.extensions.compatibility_guard.resolve_bias_version_compatibility")
    def test_extensions_api_blocks_install_when_bias_version_incompatible(self, resolve_bias_version_compatibility_mock):
        resolve_bias_version_compatibility_mock.return_value = {
            "compatible": False,
            "current_version": "1.0.0",
            "required_range": "^2.0.0",
            "message": "当前 Bias 版本 1.0.0 不满足扩展声明的兼容范围 ^2.0.0。",
        }

        response = self.client.post(
            "/api/admin/extensions/alpha-tools/install",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_install_incompatible_bias_version")
        self.assertEqual(payload["field_errors"]["required_bias_version"], "^2.0.0")

    def test_extensions_api_blocks_disable_when_other_extensions_depend_on_it(self):
        response = self.client.post(
            "/api/admin/extensions/notifications/disable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_disable_blocked")
        self.assertIn("blocking_dependents", payload["field_errors"])
        self.assertIn("approval", payload["field_errors"]["blocking_dependents"])

    def test_extensions_api_blocks_disable_for_core_extension(self):
        response = self.client.post(
            "/api/admin/extensions/core/disable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_disable_core_blocked")

    def test_extensions_api_blocks_disable_for_protected_extension(self):
        response = self.client.post(
            "/api/admin/extensions/posts/disable",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 409, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "extension_disable_protected_blocked")
        self.assertIn("protected_reason", payload["field_errors"])

    def test_extensions_api_uninstall_disables_enabled_extension_first(self):
        self.client.post(
            "/api/admin/extensions/alpha-tools/install",
            **self.auth_header(),
        )

        response = self.client.post(
            "/api/admin/extensions/alpha-tools/uninstall",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        extension = payload["extension"]
        self.assertFalse(extension["installed"])
        self.assertFalse(extension["enabled"])
        hooks = {item["hook"]: item for item in extension["backend_hooks"]}
        self.assertEqual(hooks["run_disable"]["status"], "ok")
        self.assertEqual(hooks["run_uninstall"]["status"], "ok")
