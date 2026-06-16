from apps.core.tests.common import *

class QueueServiceTests(TestCase):
    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_queue_worker_status_reports_disabled_when_queue_is_off(self):
        from apps.core.queue_service import QueueService

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "disabled")
        self.assertFalse(status["available"])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    @patch("apps.core.queue_service.QueueService._should_skip_live_worker_check", return_value=False)
    def test_queue_worker_status_reports_available_workers(self, _skip_live_worker_check, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        inspect.return_value.ping.return_value = {
            "celery@worker-a": {"ok": "pong"},
            "celery@worker-b": {"ok": "pong"},
        }

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "available")
        self.assertTrue(status["available"])
        self.assertEqual(status["worker_count"], 2)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    @patch("apps.core.queue_service.QueueService._should_skip_live_worker_check", return_value=False)
    def test_queue_worker_status_reports_unavailable_without_ping_response(self, _skip_live_worker_check, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        inspect.return_value.ping.return_value = None

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "unavailable")
        self.assertFalse(status["available"])
        self.assertEqual(status["worker_count"], 0)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    def test_queue_worker_status_skips_live_probe_during_tests(self, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "unavailable")
        self.assertEqual(status["label"], "测试环境跳过")
        self.assertFalse(status["available"])
        inspect.assert_not_called()

    def test_queue_metrics_record_sync_dispatch(self):
        from apps.core.queue_service import QueueService

        class DummyTask:
            name = "tests.sync_task"

            def delay(self):
                raise AssertionError("queue should be disabled")

        QueueService.reset_metrics()
        result = QueueService.dispatch_celery_task(DummyTask(), fallback=lambda: "done")
        metrics = QueueService.get_metrics()

        self.assertEqual(result, "done")
        self.assertEqual(metrics["sync_count"], 1)
        self.assertEqual(metrics["enqueued_count"], 0)
        self.assertEqual(metrics["fallback_count"], 0)
        self.assertEqual(metrics["last_task"], "tests.sync_task")

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_queue_metrics_record_enqueue_and_fallback(self):
        from apps.core.queue_service import QueueService

        class SuccessfulTask:
            name = "tests.successful_task"

            def delay(self):
                return "queued"

        class FailingTask:
            name = "tests.failing_task"

            def delay(self):
                raise RuntimeError("queue down")

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        QueueService.reset_metrics()

        self.assertEqual(
            QueueService.dispatch_celery_task(SuccessfulTask(), fallback=lambda: "sync"),
            "queued",
        )
        with self.assertLogs("apps.core.queue_service", level="WARNING") as logs:
            self.assertEqual(
                QueueService.dispatch_celery_task(FailingTask(), fallback=lambda: "fallback"),
                "fallback",
            )
        self.assertTrue(any("tests.failing_task" in message for message in logs.output))
        metrics = QueueService.get_metrics()

        self.assertEqual(metrics["enqueued_count"], 1)
        self.assertEqual(metrics["fallback_count"], 1)
        self.assertEqual(metrics["sync_count"], 0)
        self.assertEqual(metrics["last_task"], "tests.failing_task")
        self.assertEqual(metrics["last_error"], "queue down")

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_queue_dispatch_skips_live_enqueue_for_app_tasks_during_tests(self):
        from apps.core.queue_service import QueueService

        class AppTask:
            __module__ = "extensions.notifications.backend.tasks"
            name = "extensions.notifications.backend.tasks.dispatch_notification_batch"

            def delay(self):
                raise AssertionError("live queue should be skipped in tests")

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        QueueService.reset_metrics()

        result = QueueService.dispatch_celery_task(AppTask(), fallback=lambda: "sync")
        metrics = QueueService.get_metrics()

        self.assertEqual(result, "sync")
        self.assertEqual(metrics["sync_count"], 1)
        self.assertEqual(metrics["enqueued_count"], 0)
        self.assertEqual(metrics["fallback_count"], 0)

    def test_queue_dispatch_records_sync_from_initial_queue_state(self):
        from apps.core.queue_service import QueueService

        class DummyTask:
            name = "tests.initial_sync_task"

            def delay(self):
                raise AssertionError("queue should be disabled")

        QueueService.reset_metrics()
        with patch("apps.core.queue_service.QueueService.should_enqueue", side_effect=[False]) as should_enqueue:
            result = QueueService.dispatch_celery_task(DummyTask(), fallback=lambda: "sync")

        metrics = QueueService.get_metrics()
        self.assertEqual(result, "sync")
        self.assertEqual(should_enqueue.call_count, 1)
        self.assertEqual(metrics["sync_count"], 1)
        self.assertEqual(metrics["fallback_count"], 0)
