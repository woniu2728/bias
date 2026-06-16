from apps.core.tests.common import *

class SettingsServiceFallbackTests(TestCase):
    def setUp(self):
        super().setUp()
        clear_runtime_setting_caches()

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_get_setting_group_returns_defaults_when_settings_table_is_unavailable(self):
        defaults = {"log_queries": False, "maintenance_mode": False}

        with patch("apps.core.settings_service.Setting.objects.filter", side_effect=OperationalError("no such table")):
            values = get_setting_group("advanced", defaults)

        self.assertEqual(values, defaults)

    def test_extension_setting_defaults_do_not_force_rebuild_on_hot_path(self):
        host = SimpleNamespace(
            get_runtime_extensions=lambda: (),
            get_extension_views=lambda: (),
        )

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=host) as get_host:
            self.assertEqual(get_extension_setting_group_defaults("advanced"), {})
            self.assertEqual(get_extension_setting_group_defaults("advanced"), {})

        get_host.assert_called_once_with()

    def test_advanced_settings_are_cached_until_runtime_settings_are_cleared(self):
        with patch("apps.core.settings_service.get_extension_setting_group_defaults", return_value={}) as get_defaults:
            first = get_advanced_settings()
            second = get_advanced_settings()

        self.assertEqual(first["maintenance_mode_key"], "none")
        self.assertEqual(second["maintenance_mode_key"], "none")
        get_defaults.assert_called_once_with("advanced")

    def test_advanced_settings_use_short_process_cache_before_backend_cache(self):
        with patch("apps.core.settings_service.get_extension_setting_group_defaults", return_value={}):
            first = get_advanced_settings()
            with patch("apps.core.settings_service._cache_get", side_effect=AssertionError("backend cache hit")):
                second = get_advanced_settings()

        self.assertEqual(first["maintenance_mode_key"], "none")
        self.assertEqual(second["maintenance_mode_key"], "none")

    def test_clear_runtime_setting_caches_clears_advanced_settings_process_cache(self):
        with patch("apps.core.settings_service.get_extension_setting_group_defaults", return_value={}) as get_defaults:
            get_advanced_settings()

        clear_runtime_setting_caches()

        with patch("apps.core.settings_service.get_extension_setting_group_defaults", return_value={}) as get_defaults_after_clear:
            get_advanced_settings()

        get_defaults.assert_called_once_with("advanced")
        get_defaults_after_clear.assert_called_once_with("advanced")

    @override_settings(CELERY_BROKER_URL="redis://:secret-password@localhost:6379/1")
    def test_advanced_settings_cache_key_does_not_expose_broker_secret(self):
        from apps.core.settings_service import _advanced_settings_cache_key

        first_key = _advanced_settings_cache_key()

        with override_settings(CELERY_BROKER_URL="redis://:other-password@localhost:6379/1"):
            second_key = _advanced_settings_cache_key()

        self.assertNotIn("secret-password", first_key)
        self.assertNotIn("other-password", second_key)
        self.assertNotEqual(first_key, second_key)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_advanced_settings_do_not_enable_queue_by_default_in_tests(self):
        clear_runtime_setting_caches()

        settings_data = get_advanced_settings()

        self.assertEqual(settings_data["queue_driver"], "redis")
        self.assertFalse(settings_data["queue_enabled"])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_advanced_settings_enable_queue_by_default_for_redis_runtime(self):
        clear_runtime_setting_caches()

        with patch("apps.core.settings_service._is_test_process", return_value=False):
            settings_data = get_advanced_settings()

        self.assertEqual(settings_data["queue_driver"], "redis")
        self.assertTrue(settings_data["queue_enabled"])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_saved_queue_disabled_setting_overrides_redis_runtime_default(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(False)},
        )
        clear_runtime_setting_caches()

        with patch("apps.core.settings_service._is_test_process", return_value=False):
            settings_data = get_advanced_settings()

        self.assertEqual(settings_data["queue_driver"], "redis")
        self.assertFalse(settings_data["queue_enabled"])
