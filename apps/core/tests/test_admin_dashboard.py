from apps.core.tests.common import *

class AdminDashboardStatsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="dashboard-secret-key-12345678901234567890",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "dashboard-jwt-secret-key-123456789012345"},
    )
    def test_admin_stats_returns_python_runtime_status(self):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["runtimeName"], "Python")
        self.assertTrue(payload["pythonVersion"])
        self.assertTrue(payload["djangoVersion"])
        self.assertIn("SQLite", payload["databaseLabel"])
        self.assertEqual(payload["cacheDriver"], "内存")
        self.assertEqual(payload["realtimeDriver"], "In-memory")
        self.assertEqual(payload["queueLabel"], "同步执行")
        self.assertFalse(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "disabled")
        self.assertFalse(payload["queueWorkerAvailable"])
        self.assertEqual(payload["queueMetrics"]["enqueued_count"], 0)
        self.assertEqual(payload["queueMetrics"]["sync_count"], 0)
        self.assertEqual(payload["queueMetrics"]["fallback_count"], 0)
        self.assertFalse(payload["redisEnabled"])
        self.assertEqual(payload["cacheConnectionStatus"], "disabled")
        self.assertIsNone(payload["cacheConnectionAvailable"])
        self.assertEqual(payload["realtimeConnectionStatus"], "disabled")
        self.assertIsNone(payload["realtimeConnectionAvailable"])
        self.assertEqual(payload["queueBrokerStatus"], "disabled")
        self.assertIsNone(payload["queueBrokerAvailable"])
        self.assertEqual(payload["authSecretStatus"], "healthy")
        self.assertEqual(payload["runtimeRisks"], [])

    @override_settings(
        CACHES={"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://localhost:6379/0"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("localhost", 6379)]}}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
        SECRET_KEY="dashboard-secret-key-12345678901234567890",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "dashboard-jwt-secret-key-123456789012345"},
    )
    @patch("apps.core.admin_runtime_summary.probe_redis_ping")
    @patch("apps.core.admin_runtime_summary.cache")
    @patch("apps.core.admin_stats_api.QueueService.get_worker_status")
    def test_admin_stats_marks_redis_and_queue_status(self, get_worker_status, mock_cache, probe_redis_ping):
        mock_cache.get.return_value = "ok"
        mock_cache.set.return_value = None
        probe_redis_ping.return_value = {
            "available": True,
            "status": "available",
            "label": "可用",
            "message": "Redis 返回 PONG",
        }
        get_worker_status.return_value = {
            "status": "available",
            "label": "2 个 worker 在线",
            "available": True,
            "worker_count": 2,
            "message": "Celery worker 可用。",
        }
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["cacheDriver"], "Redis")
        self.assertEqual(payload["realtimeDriver"], "Redis")
        self.assertEqual(payload["queueDriver"], "redis")
        self.assertEqual(payload["queueLabel"], "Redis")
        self.assertTrue(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "available")
        self.assertEqual(payload["queueWorkerLabel"], "2 个 worker 在线")
        self.assertTrue(payload["queueWorkerAvailable"])
        self.assertEqual(payload["queueWorkerCount"], 2)
        self.assertTrue(payload["redisEnabled"])
        self.assertEqual(payload["cacheConnectionStatus"], "available")
        self.assertTrue(payload["cacheConnectionAvailable"])
        self.assertEqual(payload["realtimeConnectionStatus"], "available")
        self.assertTrue(payload["realtimeConnectionAvailable"])
        self.assertEqual(payload["queueBrokerStatus"], "available")
        self.assertTrue(payload["queueBrokerAvailable"])
        self.assertEqual(payload["runtimeRisks"], [])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
        SECRET_KEY="dashboard-secret-key-12345678901234567890",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "dashboard-jwt-secret-key-123456789012345"},
    )
    def test_admin_stats_does_not_mark_redis_enabled_from_idle_broker_config(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(False)},
        )
        Setting.objects.update_or_create(
            key="advanced.queue_driver",
            defaults={"value": json.dumps("redis")},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["cacheDriver"], "内存")
        self.assertEqual(payload["realtimeDriver"], "In-memory")
        self.assertEqual(payload["queueDriver"], "redis")
        self.assertEqual(payload["queueLabel"], "同步执行")
        self.assertFalse(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "disabled")
        self.assertFalse(payload["queueWorkerAvailable"])
        self.assertFalse(payload["redisEnabled"])
        self.assertEqual(payload["runtimeRisks"], [])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "prod-risk-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    def test_admin_stats_reports_production_runtime_risks(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="advanced.queue_driver",
            defaults={"value": json.dumps("redis")},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertIn("locmem-cache-production", risk_codes)
        self.assertIn("realtime-inmemory-production", risk_codes)
        self.assertIn("queue-worker-unavailable", risk_codes)

    @override_settings(
        WEB_CONCURRENCY=2,
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="dashboard-secret-key-12345678901234567890",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "dashboard-jwt-secret-key-123456789012345"},
    )
    def test_admin_stats_reports_multiprocess_inmemory_risks(self):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertIn("locmem-cache-multiprocess", risk_codes)
        self.assertIn("realtime-inmemory-multiprocess", risk_codes)

    @override_settings(
        CACHES={"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://localhost:6379/0"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("localhost", 6379)]}}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    @patch("apps.core.admin_runtime_summary.cache")
    def test_admin_stats_reports_cache_backend_unavailable(self, mock_cache):
        mock_cache.get.side_effect = RuntimeError("cache offline")
        mock_cache.set.side_effect = RuntimeError("cache offline")
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        dependency_checks = {item["key"]: item for item in payload["runtimeDependencyChecks"]}
        self.assertEqual(payload["cacheConnectionStatus"], "unavailable")
        self.assertFalse(payload["cacheConnectionAvailable"])
        self.assertIn("cache-backend-unavailable", risk_codes)
        self.assertIn("缓存服务在线", dependency_checks["cache"]["recommended_action"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {}}},
        CELERY_BROKER_URL="memory://",
    )
    @patch("apps.core.admin_runtime_summary.probe_redis_ping")
    def test_admin_stats_reports_realtime_backend_misconfigured(self, _probe_redis_ping):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        dependency_checks = {item["key"]: item for item in payload["runtimeDependencyChecks"]}
        self.assertEqual(payload["realtimeConnectionStatus"], "misconfigured")
        self.assertFalse(payload["realtimeConnectionAvailable"])
        self.assertIn("realtime-backend-unavailable", risk_codes)
        self.assertIn("CHANNEL_LAYERS.default.CONFIG.hosts", dependency_checks["realtime"]["recommended_action"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    @patch("apps.core.admin_stats_api.QueueService.get_worker_status")
    @patch("apps.core.admin_stats_api.get_runtime_advanced_settings")
    def test_admin_stats_reports_queue_broker_misconfigured(self, get_runtime_advanced_settings, get_worker_status):
        get_runtime_advanced_settings.return_value = {
            "queue_enabled": True,
            "queue_driver": "redis",
            "maintenance_mode": False,
        }
        get_worker_status.return_value = {
            "status": "unavailable",
            "label": "无 worker 响应",
            "available": False,
            "worker_count": 0,
            "message": "队列已启用，但没有检测到在线 worker。",
        }

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        dependency_checks = {item["key"]: item for item in payload["runtimeDependencyChecks"]}
        self.assertEqual(payload["queueBrokerStatus"], "misconfigured")
        self.assertFalse(payload["queueBrokerAvailable"])
        self.assertIn("queue-broker-unavailable", risk_codes)
        self.assertIn("CELERY_BROKER_URL", dependency_checks["queue-broker"]["recommended_action"])
        self.assertIn("启动 Celery worker", dependency_checks["queue-worker"]["recommended_action"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("redis.internal", 6379)]}}},
        CELERY_BROKER_URL="redis://redis.internal:6379/1",
    )
    @patch("apps.core.admin_runtime_summary.cache")
    @patch("apps.core.admin_runtime_summary.probe_redis_ping")
    @patch("apps.core.admin_stats_api.QueueService.get_worker_status")
    def test_admin_stats_reports_unreachable_realtime_and_queue_broker(
        self,
        get_worker_status,
        probe_redis_ping,
        mock_cache,
    ):
        mock_cache.get.return_value = "ok"
        mock_cache.set.return_value = None
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        get_worker_status.return_value = {
            "status": "unavailable",
            "label": "无 worker 响应",
            "available": False,
            "worker_count": 0,
            "message": "队列已启用，但没有检测到在线 worker。",
        }
        probe_redis_ping.side_effect = [
            {
                "available": False,
                "status": "unreachable",
                "label": "不可达",
                "message": "Redis Channel Layer 主机 redis.internal:6379 无法连通：timeout",
            },
            {
                "available": False,
                "status": "unreachable",
                "label": "不可达",
                "message": "Redis broker 主机 redis.internal:6379 无法连通：timeout",
            },
        ]

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertEqual(payload["realtimeConnectionStatus"], "unreachable")
        self.assertEqual(payload["queueBrokerStatus"], "unreachable")
        self.assertIn("realtime-backend-unavailable", risk_codes)
        self.assertIn("queue-broker-unavailable", risk_codes)

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("redis.internal", 6379)]}}},
        CELERY_BROKER_URL="redis://redis.internal:6379/1",
    )
    @patch("apps.core.admin_runtime_summary.cache")
    @patch("apps.core.admin_runtime_summary.probe_redis_ping")
    @patch("apps.core.admin_stats_api.QueueService.get_worker_status")
    def test_admin_stats_reports_protocol_error_for_realtime_and_queue_broker(
        self,
        get_worker_status,
        probe_redis_ping,
        mock_cache,
    ):
        mock_cache.get.return_value = "ok"
        mock_cache.set.return_value = None
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        get_worker_status.return_value = {
            "status": "available",
            "label": "1 个 worker 在线",
            "available": True,
            "worker_count": 1,
            "message": "Celery worker 可用。",
        }
        probe_redis_ping.side_effect = [
            {
                "available": False,
                "status": "protocol-error",
                "label": "协议异常",
                "message": "Redis Channel Layer 已建立连接，但未返回 Redis PONG。",
            },
            {
                "available": False,
                "status": "protocol-error",
                "label": "协议异常",
                "message": "Redis broker 已建立连接，但未返回 Redis PONG。",
            },
        ]

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["realtimeConnectionStatus"], "protocol-error")
        self.assertEqual(payload["queueBrokerStatus"], "protocol-error")

    @override_settings(
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "prod-risk-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_stats_reports_missing_redis_in_postgres_runtime(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(False)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertIn("redis-disabled-production", risk_codes)

    @override_settings(
        SECRET_KEY="django-insecure-change-this-in-production",
        NINJA_JWT={
            "ALGORITHM": "HS256",
            "SIGNING_KEY": "short-jwt-secret",
        },
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "auth-risk-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_stats_reports_auth_secret_risks(self):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        risk_codes = {item["code"] for item in payload["runtimeRisks"]}
        self.assertEqual(payload["authSecretStatus"], "danger")
        self.assertEqual(payload["authSecretLabel"], "存在风险")
        self.assertIn("django-secret-placeholder", risk_codes)
        self.assertIn("jwt-secret-too-short", risk_codes)
        self.assertIn("JWT 签名密钥长度不足", payload["authSecretMessage"])
