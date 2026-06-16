from apps.core.tests.common import *

class AdminSettingsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_settings_are_persisted(self):
        response = self.client.post(
            "/api/admin/settings",
            data=json.dumps({
                "forum_title": "中文社区",
                "seo_title": "中文社区 - 技术论坛",
                "seo_description": "这是一个专注 Django 与 Vue 的中文社区。",
                "seo_keywords": "Python, Django, Vue",
                "seo_robots_index": False,
                "seo_robots_follow": True,
                "announcement_enabled": True,
                "announcement_message": "今晚 23:00 进行维护。",
                "announcement_tone": "warning",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.forum_title").value),
            "中文社区",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.seo_title").value),
            "中文社区 - 技术论坛",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.seo_robots_index").value),
            False,
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.announcement_message").value),
            "今晚 23:00 进行维护。",
        )


    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_advanced_and_cache_endpoints_exist(self):
        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("cache_driver", payload)
        self.assertIn("queue_driver", payload)
        self.assertNotIn("storage_driver", payload)

        response = self.client.post(
            "/api/admin/cache/clear",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["message"], "缓存已清除")

    def test_appearance_settings_persist_head_and_footer_html(self):
        response = self.client.post(
            "/api/admin/appearance",
            data=json.dumps({
                "custom_head_html": "<script>window.testHead = true</script>",
                "custom_footer_html": "<p>备案号：蜀ICP备123456号</p>",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="appearance.custom_head_html").value),
            "<script>window.testHead = true</script>",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="appearance.custom_footer_html").value),
            "<p>备案号：蜀ICP备123456号</p>",
        )

        response = self.client.get(
            "/api/admin/appearance",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["custom_head_html"], "<script>window.testHead = true</script>")
        self.assertEqual(payload["custom_footer_html"], "<p>备案号：蜀ICP备123456号</p>")

    def test_debug_mode_setting_is_read_only_runtime_value(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "debug_mode": not settings.DEBUG,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["debug_mode"], settings.DEBUG)
        self.assertFalse(Setting.objects.filter(key="advanced.debug_mode").exists())

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("localhost", 6379)]}}},
    )
    def test_advanced_settings_rejects_file_cache_in_postgres_runtime(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "cache_driver": "file",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "invalid_runtime_configuration")
        self.assertIn("PostgreSQL 生产形态下不允许将缓存驱动保存为文件缓存", payload["message"])

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    )
    def test_advanced_settings_rejects_nonredis_queue_in_postgres_runtime(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "queue_enabled": True,
                "queue_driver": "database",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        payload = response.json()
        self.assertEqual(payload["code"], "invalid_runtime_configuration")
        self.assertIn("当前仅允许使用 Redis 队列驱动", payload["message"])

    def test_mail_settings_persist_mail_from_and_saved_test_recipient(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_driver": "smtp",
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_test_recipient": "saved-recipient@example.com",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["mail_from"], "Bias Mailer <service@example.com>")

        response = self.client.get(
            "/api/admin/mail",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["mail_from"], "Bias Mailer <service@example.com>")
        self.assertEqual(response.json()["mail_test_recipient"], "saved-recipient@example.com")
        self.assertEqual(response.json()["test_to_email"], "saved-recipient@example.com")

    def test_mail_settings_expose_default_templates(self):
        response = self.client.get(
            "/api/admin/mail",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("{{ site_name }}", payload["mail_verification_subject"])
        self.assertIn("{{ verification_url }}", payload["mail_verification_text"])
        self.assertIn("{{ reset_url }}", payload["mail_password_reset_html"])
        self.assertTrue(payload["mail_from"])
        self.assertEqual(list(payload["drivers"].keys()), ["smtp"])
        self.assertEqual(payload["driver_options"], [{"value": "smtp", "label": "SMTP"}])
        self.assertEqual(payload["mail_host"], "smtp.gmail.com")
        self.assertEqual(payload["mail_encryption"], "tls")
        self.assertIn("sending", payload)

    def test_smtp_driver_requires_host_before_sending(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
                "mail_host": "",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertFalse(payload["sending"])
        self.assertIn("mail_host", payload["errors"])

    def test_public_forum_settings_include_basic_and_appearance(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("运行时论坛名称")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_title",
            defaults={"value": json.dumps("运行时 SEO 标题")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_description",
            defaults={"value": json.dumps("运行时 SEO 描述")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_keywords",
            defaults={"value": json.dumps("Python, Django, Vue")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_robots_index",
            defaults={"value": json.dumps(False)},
        )
        Setting.objects.update_or_create(
            key="basic.seo_robots_follow",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="basic.announcement_enabled",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="basic.announcement_message",
            defaults={"value": json.dumps("运行时公告")},
        )
        Setting.objects.update_or_create(
            key="basic.announcement_tone",
            defaults={"value": json.dumps("warning")},
        )
        Setting.objects.update_or_create(
            key="appearance.primary_color",
            defaults={"value": json.dumps("#123456")},
        )
        Setting.objects.update_or_create(
            key="appearance.logo_url",
            defaults={"value": json.dumps("/media/runtime-logo.png")},
        )
        ExtensionInstallation.objects.create(
            extension_id="alpha-tools",
            version="0.1.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["forum_title"], "运行时论坛名称")
        self.assertEqual(payload["seo_title"], "运行时 SEO 标题")
        self.assertEqual(payload["seo_description"], "运行时 SEO 描述")
        self.assertEqual(payload["seo_keywords"], "Python, Django, Vue")
        self.assertFalse(payload["seo_robots_index"])
        self.assertTrue(payload["seo_robots_follow"])
        self.assertTrue(payload["announcement_enabled"])
        self.assertEqual(payload["announcement_message"], "运行时公告")
        self.assertEqual(payload["announcement_tone"], "warning")
        self.assertEqual(payload["primary_color"], "#123456")
        self.assertEqual(payload["logo_url"], "/media/runtime-logo.png")
        self.assertIn("notification_types", payload)
        self.assertIn("user_preferences", payload)
        self.assertIn("post_types", payload)
        self.assertIn("enabled_modules", payload)
        self.assertIn("enabled_extensions", payload)
        self.assertIn("extension_runtime", payload)
        self.assertIn("stamp", payload["extension_runtime"])
        self.assertIn("core", payload["enabled_modules"])
        self.assertFalse(any(item["id"] == "alpha-tools" for item in payload["enabled_extensions"]))

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_cache_lifetime_controls_public_forum_settings_cache(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 A")},
        )
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(60)},
        )
        clear_runtime_setting_caches()

        first_response = self.client.get("/api/forum")
        self.assertEqual(first_response.status_code, 200, first_response.content)
        self.assertEqual(first_response.json()["forum_title"], "缓存标题 A")

        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 B")},
        )

        cached_response = self.client.get("/api/forum")
        self.assertEqual(cached_response.status_code, 200, cached_response.content)
        self.assertEqual(cached_response.json()["forum_title"], "缓存标题 A")

        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(0)},
        )
        clear_runtime_setting_caches()

        uncached_response = self.client.get("/api/forum")
        self.assertEqual(uncached_response.status_code, 200, uncached_response.content)
        self.assertEqual(uncached_response.json()["forum_title"], "缓存标题 B")

        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 C")},
        )
        direct_response = self.client.get("/api/forum")
        self.assertEqual(direct_response.status_code, 200, direct_response.content)
        self.assertEqual(direct_response.json()["forum_title"], "缓存标题 C")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_public_forum_settings_rebuilds_stale_cache_payload_missing_runtime_fields(self):
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(60)},
        )
        clear_runtime_setting_caches()
        from django.core.cache import cache

        cache.set(
            "settings.public.forum",
            {
                "forum_title": "过期缓存标题",
                "notification_types": [],
                "user_preferences": [],
                "post_types": [],
            },
            60,
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("enabled_modules", payload)
        self.assertIn("enabled_extensions", payload)
        self.assertIn("core", payload["enabled_modules"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_maintenance_mode_blocks_public_api_but_keeps_admin_paths_available(self):
        Setting.objects.update_or_create(
            key="advanced.maintenance_mode_key",
            defaults={"value": json.dumps("high")},
        )
        Setting.objects.update_or_create(
            key="advanced.maintenance_message",
            defaults={"value": json.dumps("站点维护中，请稍后回来。")},
        )
        clear_runtime_setting_caches()

        public_settings_response = self.client.get("/api/forum")
        self.assertEqual(public_settings_response.status_code, 200, public_settings_response.content)
        self.assertTrue(public_settings_response.json()["maintenance_mode"])
        self.assertEqual(public_settings_response.json()["maintenance_mode_key"], "high")
        self.assertEqual(public_settings_response.json()["maintenance_message"], "站点维护中，请稍后回来。")

        blocked_response = self.client.get("/api/search", {"q": "维护"})
        self.assertEqual(blocked_response.status_code, 503, blocked_response.content)
        self.assertEqual(blocked_response.json()["error"], "站点维护中，请稍后回来。")
        self.assertTrue(blocked_response.json()["maintenance"])

        admin_response = self.client.get("/api/admin/advanced", **self.auth_header())
        self.assertEqual(admin_response.status_code, 200, admin_response.content)

        me_response = self.client.get("/api/users/me", **self.auth_header())
        self.assertEqual(me_response.status_code, 200, me_response.content)
        self.assertTrue(me_response.json()["is_staff"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_low_maintenance_mode_allows_reads_but_blocks_writes(self):
        Setting.objects.update_or_create(
            key="advanced.maintenance_mode_key",
            defaults={"value": json.dumps("low")},
        )
        clear_runtime_setting_caches()

        read_response = self.client.get("/api/search", {"q": "维护"})
        self.assertNotEqual(read_response.status_code, 503, read_response.content)

        write_response = self.client.post("/api/discussions", data={}, content_type="application/json")
        self.assertEqual(write_response.status_code, 503, write_response.content)
        self.assertEqual(write_response.json()["maintenance_mode_key"], "low")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_log_queries_setting_logs_sql_statements(self):
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(0)},
        )
        Setting.objects.update_or_create(
            key="advanced.log_queries",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        with self.assertLogs("bias.sql", level="INFO") as captured:
            response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        joined_output = "\n".join(captured.output)
        self.assertIn("/api/forum", joined_output)
        self.assertIn("total_queries=", joined_output)
        self.assertIn("SELECT", joined_output.upper())

    def test_markdown_preview_endpoint_returns_rendered_html(self):
        alice = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        response = self.client.post(
            "/api/preview",
            data=json.dumps({
                "content": "# 标题\n\n你好 @alice\n\n[官网](https://example.com)"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        html = response.json()["html"]
        self.assertIn("<h1", html)
        self.assertIn(f'href="/u/{alice.id}"', html)
        self.assertIn(">官网</a>", html)
        self.assertIn('target="_blank"', html)
