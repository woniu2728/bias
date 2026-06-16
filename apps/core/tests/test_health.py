from apps.core.tests.common import *

class HealthCheckApiTests(TestCase):
    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "health-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="health-check-secret-key-1234567890123456",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "health-check-jwt-secret-key-1234567890"},
    )
    def test_health_check_exposes_minimal_runtime_status(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["state"], "ready")
        self.assertNotIn("readiness", payload)
        self.assertNotIn("database_label", payload)
        self.assertNotIn("cache_driver", payload)

    @override_settings(
        DEBUG=False,
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "health-prod-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="django-insecure-change-this-in-production",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "short-jwt-secret"},
        FRONTEND_URL="",
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    def test_health_check_hides_production_runtime_risks(self, _is_test_process):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertNotIn("readiness", payload)
