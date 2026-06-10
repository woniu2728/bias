from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from ninja_jwt.tokens import RefreshToken

from apps.core.models import AuditLog, Setting
from apps.core.online_service import OnlineUserService
from apps.core.queue_service import QueueService
from apps.core.settings_service import clear_runtime_setting_caches
from extensions.notifications.backend.events import NotificationCreatedEvent
from extensions.realtime.backend.ext import dispatch_notification_batch
from extensions.users.backend.models import User


class RealtimeNotificationDispatchTests(TestCase):
    def test_notification_created_event_is_serialized_and_sent_to_user_channel(self):
        notification = SimpleNamespace(id=10, user_id=7)
        service = {
            "load_realtime_notifications": Mock(return_value=[notification]),
            "serialize_realtime_notification": Mock(return_value={
                "id": 10,
                "type": "discussionReply",
                "is_read": False,
            }),
        }

        with patch("extensions.realtime.backend.ext.get_runtime_notification_service", return_value=service):
            with patch("extensions.realtime.backend.ext.WebSocketService.send_notification_to_user") as send:
                dispatch_notification_batch(NotificationCreatedEvent(notification_ids=(10,)))

        service["load_realtime_notifications"].assert_called_once_with([10])
        service["serialize_realtime_notification"].assert_called_once_with(notification)
        send.assert_called_once_with(
            user_id=7,
            notification_data={
                "id": 10,
                "type": "discussionReply",
                "is_read": False,
            },
        )


class RealtimeForumSettingsTests(TestCase):
    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_public_forum_settings_expose_realtime_typing_toggle(self):
        Setting.objects.update_or_create(
            key="extensions.realtime.typing_enabled",
            defaults={"value": json.dumps(False)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["realtime_typing_enabled"])

    def test_runtime_entry_exposes_realtime_settings_schema(self):
        from apps.core.extensions.runtime_service import get_enabled_extension_runtime_entries

        entries = get_enabled_extension_runtime_entries(product_visible_only=True)
        realtime = next(item for item in entries if item["id"] == "realtime")

        self.assertEqual(realtime["settings_values"]["typing_enabled"], True)
        self.assertEqual(realtime["forum_settings"]["realtime_typing_enabled"], True)


@override_settings(
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "queue-reset-test"}},
    CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
    CELERY_BROKER_URL="memory://",
)
class RealtimeQueueMetricsAdminApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="queue-admin",
            email="queue-admin@example.com",
            password="password123",
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_reset_queue_metrics(self):
        class DummyTask:
            name = "tests.reset_metric_task"

            def delay(self):
                raise AssertionError("queue should be disabled")

        QueueService.reset_metrics()
        QueueService.dispatch_celery_task(DummyTask(), fallback=lambda: "done")
        self.assertEqual(QueueService.get_metrics()["sync_count"], 1)

        response = self.client.post("/api/admin/queue/metrics/reset", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["message"], "队列运行指标已重置")
        self.assertEqual(payload["metrics"]["sync_count"], 0)
        self.assertEqual(payload["metrics"]["enqueued_count"], 0)
        self.assertEqual(payload["metrics"]["fallback_count"], 0)
        audit_log = AuditLog.objects.get(action="admin.queue_metrics.reset")
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "")

    def test_non_staff_cannot_reset_queue_metrics(self):
        member = User.objects.create_user(
            username="queue-reset-member",
            email="queue-reset-member@example.com",
            password="password123",
        )

        response = self.client.post(
            "/api/admin/queue/metrics/reset",
            **self.auth_header(member),
        )

        self.assertEqual(response.status_code, 403, response.content)


@override_settings(CACHES={
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "bias-online-tests",
    }
})
class OnlineUserServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="online-user",
            email="online-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.other_user = User.objects.create_user(
            username="online-other",
            email="online-other@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_multiple_connections_only_go_offline_after_last_disconnect(self):
        self.assertTrue(OnlineUserService.mark_user_online(self.user.id))
        self.assertFalse(OnlineUserService.mark_user_online(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        self.assertFalse(OnlineUserService.mark_user_offline(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        self.assertTrue(OnlineUserService.mark_user_offline(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [])

    def test_touch_extends_presence_ttl(self):
        with patch.object(OnlineUserService, "_now_ts", return_value=100):
            OnlineUserService.mark_user_online(self.user.id)

        with patch.object(OnlineUserService, "_now_ts", return_value=150):
            self.assertTrue(OnlineUserService.touch_user_online(self.user.id))

        with patch.object(OnlineUserService, "_now_ts", return_value=200):
            self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        with patch.object(OnlineUserService, "_now_ts", return_value=241):
            self.assertEqual(OnlineUserService.get_online_user_ids(), [])

    def test_get_online_users_returns_only_marked_users(self):
        OnlineUserService.mark_user_online(self.other_user.id)
        OnlineUserService.mark_user_online(self.user.id)

        users = OnlineUserService.get_online_users(limit=10)

        self.assertEqual({item["id"] for item in users}, {self.user.id, self.other_user.id})
        self.assertTrue(all("username" in item for item in users))
