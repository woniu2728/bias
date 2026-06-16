from apps.core.tests.common import *

class RuntimeStatusCacheTests(TestCase):
    def tearDown(self):
        from apps.core.runtime_state import clear_runtime_status_cache

        clear_runtime_status_cache()
        super().tearDown()

    def test_runtime_status_uses_short_process_cache(self):
        from apps.core.runtime_state import clear_runtime_status_cache, get_runtime_status

        clear_runtime_status_cache()
        Setting.objects.update_or_create(
            key="system.version",
            defaults={"value": json.dumps("1.0.0")},
        )
        bootstrap = SiteBootstrapConfig(installed=True, source="file", database_mode="sqlite")

        with self.assertNumQueries(1):
            first = get_runtime_status(bootstrap)
            second = get_runtime_status(bootstrap)

        self.assertEqual(first.state, "ready")
        self.assertEqual(second.state, "ready")

    def test_clear_runtime_setting_caches_clears_runtime_status_cache(self):
        from apps.core.runtime_state import clear_runtime_status_cache, get_runtime_status

        clear_runtime_status_cache()
        Setting.objects.update_or_create(
            key="system.version",
            defaults={"value": json.dumps("1.0.0")},
        )
        bootstrap = SiteBootstrapConfig(installed=True, source="file", database_mode="sqlite")
        get_runtime_status(bootstrap)

        clear_runtime_setting_caches()

        with self.assertNumQueries(1):
            status = get_runtime_status(bootstrap)

        self.assertEqual(status.state, "ready")
