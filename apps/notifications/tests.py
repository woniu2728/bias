from django.core.cache import cache
from django.test import TestCase, override_settings
from ninja_jwt.tokens import RefreshToken
from unittest.mock import patch

from apps.discussions.models import DiscussionUser
from apps.core.models import Setting
from apps.core.settings_service import clear_runtime_setting_caches
from apps.discussions.services import DiscussionService
from apps.notifications.models import Notification
from apps.notifications.admin import NotificationAdmin
from apps.notifications.services import NotificationService
from apps.posts.services import PostService
from apps.users.models import User


class NotificationServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.replier = User.objects.create_user(
            username="replier",
            email="replier@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.participant = User.objects.create_user(
            username="participant",
            email="participant@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.mentioned = User.objects.create_user(
            username="mentioned",
            email="mentioned@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        self.discussion = DiscussionService.create_discussion(
            title="Notification discussion",
            content="Initial post",
            user=self.author,
        )
        self.initial_reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="First reply",
            user=self.participant,
        )

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_reply_to_post_creates_post_reply_notification(self):
        PostService.create_post(
            discussion_id=self.discussion.id,
            content="@author Thanks for the update",
            user=self.replier,
            reply_to_post_id=self.initial_reply.id,
        )

        notification = Notification.objects.filter(
            user=self.participant,
            type="postReply",
        ).latest("id")

        self.assertEqual(notification.data["discussion_id"], self.discussion.id)
        self.assertEqual(notification.data["reply_to_post_id"], self.initial_reply.id)
        self.assertEqual(notification.data["reply_to_post_number"], self.initial_reply.number)
        self.assertIn("post_number", notification.data)

    def test_like_notification_contains_post_number(self):
        PostService.like_post(self.initial_reply.id, self.replier)

        notification = Notification.objects.get(
            user=self.participant,
            type="postLiked",
            subject_id=self.initial_reply.id,
        )

        self.assertEqual(notification.data["discussion_id"], self.discussion.id)
        self.assertEqual(notification.data["post_id"], self.initial_reply.id)
        self.assertEqual(notification.data["post_number"], self.initial_reply.number)

    def test_mention_notification_contains_post_number(self):
        post = PostService.create_post(
            discussion_id=self.discussion.id,
            content=f"Hello @{self.mentioned.username}",
            user=self.replier,
        )

        notification = Notification.objects.get(
            user=self.mentioned,
            type="userMentioned",
            subject_id=post.id,
        )

        self.assertEqual(notification.data["discussion_id"], self.discussion.id)
        self.assertEqual(notification.data["post_id"], post.id)
        self.assertEqual(notification.data["post_number"], post.number)

    def test_reply_notification_respects_post_reply_preference(self):
        self.participant.preferences = {"notify_post_reply": False}
        self.participant.save(update_fields=["preferences"])

        PostService.create_post(
            discussion_id=self.discussion.id,
            content="Reply without notify",
            user=self.replier,
            reply_to_post_id=self.initial_reply.id,
        )

        self.assertFalse(
            Notification.objects.filter(
                user=self.participant,
                type="postReply",
            ).exists()
        )

    def test_like_notification_respects_post_liked_preference(self):
        self.participant.preferences = {"notify_post_liked": False}
        self.participant.save(update_fields=["preferences"])

        PostService.like_post(self.initial_reply.id, self.replier)

        self.assertFalse(
            Notification.objects.filter(
                user=self.participant,
                type="postLiked",
                subject_id=self.initial_reply.id,
            ).exists()
        )

    def test_mention_notification_respects_user_preference(self):
        self.mentioned.preferences = {"notify_user_mentioned": False}
        self.mentioned.save(update_fields=["preferences"])

        PostService.create_post(
            discussion_id=self.discussion.id,
            content=f"Hello again @{self.mentioned.username}",
            user=self.replier,
        )

        self.assertFalse(
            Notification.objects.filter(
                user=self.mentioned,
                type="userMentioned",
            ).exists()
        )

    def test_multiple_replies_in_same_discussion_create_multiple_notifications(self):
        PostService.create_post(
            discussion_id=self.discussion.id,
            content="Second reply",
            user=self.replier,
        )
        PostService.create_post(
            discussion_id=self.discussion.id,
            content="Third reply",
            user=self.replier,
        )

        notifications = Notification.objects.filter(
            user=self.author,
            type="discussionReply",
            subject_id=self.discussion.id,
            is_read=False,
        ).order_by("id")

        self.assertEqual(notifications.count(), 3)
        self.assertEqual(
            [item.data["post_number"] for item in notifications],
            [2, 3, 4],
        )

    def test_discussion_reply_notifications_dispatch_synchronously_when_queue_disabled(self):
        subscriber = User.objects.create_user(
            username="subscriber",
            email="subscriber@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        DiscussionUser.objects.create(discussion=self.discussion, user=subscriber, is_subscribed=True)
        new_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="Sync reply",
            user=self.replier,
        )

        with patch("apps.notifications.tasks.dispatch_notification_batch.delay") as delay:
            with patch("apps.notifications.services.NotificationService._send_websocket_notification") as websocket_send:
                with self.captureOnCommitCallbacks(execute=True):
                    NotificationService.notify_discussion_reply(
                        discussion_id=self.discussion.id,
                        post_id=new_post.id,
                        from_user=self.replier,
                    )

        created_notifications = Notification.objects.filter(
            type="discussionReply",
            subject_id=self.discussion.id,
            data__post_id=new_post.id,
        )
        self.assertEqual({item.user_id for item in created_notifications}, {self.author.id, subscriber.id})
        delay.assert_not_called()
        self.assertEqual(websocket_send.call_count, 2)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_discussion_reply_notifications_use_queue_when_enabled(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": "true"},
        )
        Setting.objects.update_or_create(
            key="advanced.queue_driver",
            defaults={"value": '"redis"'},
        )
        clear_runtime_setting_caches()

        subscriber = User.objects.create_user(
            username="subscriber",
            email="subscriber@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        muted = User.objects.create_user(
            username="muted",
            email="muted@example.com",
            password="password123",
            is_email_confirmed=True,
            preferences={"notify_new_post": False},
        )
        DiscussionUser.objects.create(discussion=self.discussion, user=subscriber, is_subscribed=True)
        DiscussionUser.objects.create(discussion=self.discussion, user=muted, is_subscribed=True)
        new_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="Bulk reply",
            user=self.replier,
        )

        with patch("apps.notifications.tasks.dispatch_notification_batch.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                NotificationService.notify_discussion_reply(
                    discussion_id=self.discussion.id,
                    post_id=new_post.id,
                    from_user=self.replier,
                )

        created_notifications = Notification.objects.filter(
            type="discussionReply",
            subject_id=self.discussion.id,
            data__post_id=new_post.id,
        )
        self.assertEqual({item.user_id for item in created_notifications}, {self.author.id, subscriber.id})
        delay.assert_called_once()

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_bulk_notifications_fallback_to_local_dispatch_when_task_enqueue_fails(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": "true"},
        )
        Setting.objects.update_or_create(
            key="advanced.queue_driver",
            defaults={"value": '"redis"'},
        )
        clear_runtime_setting_caches()

        first = Notification(
            user=self.author,
            from_user=self.replier,
            type="discussionReply",
            subject_type="discussion",
            subject_id=self.discussion.id,
            data={"discussion_id": self.discussion.id},
        )
        second = Notification(
            user=self.participant,
            from_user=self.replier,
            type="discussionReply",
            subject_type="discussion",
            subject_id=self.discussion.id,
            data={"discussion_id": self.discussion.id},
        )

        with patch("apps.notifications.tasks.dispatch_notification_batch.delay", side_effect=RuntimeError("queue down")):
            with patch("apps.notifications.services.NotificationService._send_websocket_notification") as websocket_send:
                with self.captureOnCommitCallbacks(execute=True):
                    created = NotificationService.create_notifications_bulk([first, second])

        self.assertEqual(len(created), 2)
        self.assertEqual(websocket_send.call_count, 2)

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_delete_all_read_endpoint_uses_clear_route(self):
        unread_before = Notification.objects.filter(user=self.author, is_read=False).count()
        Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            is_read=True,
            data={"post_id": self.initial_reply.id},
        )
        Notification.objects.create(
            user=self.author,
            from_user=self.participant,
            type="postReply",
            subject_type="post",
            subject_id=self.initial_reply.id,
            is_read=False,
            data={"post_id": self.initial_reply.id},
        )

        response = self.client.delete(
            "/api/notifications/read/clear",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(Notification.objects.filter(user=self.author, is_read=True).count(), 0)
        self.assertEqual(Notification.objects.filter(user=self.author, is_read=False).count(), unread_before + 1)

    def test_notification_list_returns_type_count_metadata(self):
        Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )
        Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            is_read=True,
            data={"post_id": self.initial_reply.id},
        )
        Notification.objects.create(
            user=self.author,
            from_user=self.participant,
            type="postReply",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )

        response = self.client.get(
            "/api/notifications",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["type_counts"]["postLiked"], 2)
        self.assertEqual(payload["type_counts"]["postReply"], 1)
        self.assertEqual(payload["unread_type_counts"]["postLiked"], 1)
        self.assertEqual(payload["unread_type_counts"]["postReply"], 1)

    def test_notification_detail_exposes_registered_from_user_summary(self):
        group = self.replier.user_groups.create(name="Notifier", color="#1abc9c", icon="fas fa-bell")
        notification = Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )

        response = self.client.get(
            f"/api/notifications/{notification.id}",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["from_user"]["username"], self.replier.username)
        self.assertEqual(payload["from_user"]["primary_group"]["name"], group.name)

    def test_notification_list_exposes_registered_from_user_summary(self):
        group = self.replier.user_groups.create(name="NotifyList", color="#9b59b6", icon="fas fa-star")
        Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postReply",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )

        response = self.client.get(
            "/api/notifications",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertGreaterEqual(payload["total"], 1)
        self.assertEqual(payload["data"][0]["from_user"]["username"], self.replier.username)
        self.assertEqual(payload["data"][0]["from_user"]["primary_group"]["name"], group.name)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "notification-cache-test"}})
    def test_notification_stats_reuses_cached_unread_count(self):
        cache.clear()
        unread_before = Notification.objects.filter(user=self.author, is_read=False).count()
        Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )

        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before + 1)

        with self.assertNumQueries(1):
            stats = NotificationService.get_stats(self.author)

        self.assertEqual(stats["total"], Notification.objects.filter(user=self.author).count())
        self.assertEqual(stats["unread_count"], unread_before + 1)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "notification-invalidate-test"}})
    def test_unread_count_cache_is_invalidated_after_writes(self):
        cache.clear()
        unread_before = Notification.objects.filter(user=self.author, is_read=False).count()
        notification = Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )

        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before + 1)

        NotificationService.mark_as_read(notification.id, self.author)
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before)

        NotificationService.create_notification(
            user=self.author,
            from_user=self.replier,
            type="postReply",
            subject_type="post",
            subject_id=self.initial_reply.id,
            allow_merge=False,
            data={"post_id": self.initial_reply.id},
        )
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before + 1)

        new_notification = Notification.objects.filter(user=self.author, is_read=False).latest("id")
        NotificationService.delete_notification(new_notification.id, self.author)
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "notification-signal-test"}})
    def test_unread_count_cache_is_invalidated_by_model_signals(self):
        cache.clear()
        unread_before = Notification.objects.filter(user=self.author, is_read=False).count()

        notification = Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before + 1)

        notification.is_read = True
        notification.read_at = None
        notification.save(update_fields=["is_read", "read_at"])
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before)

        notification.is_read = False
        notification.save(update_fields=["is_read"])
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before + 1)

        notification.delete()
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "notification-admin-test"}})
    def test_admin_bulk_actions_invalidate_unread_count_cache(self):
        cache.clear()
        notification = Notification.objects.create(
            user=self.author,
            from_user=self.replier,
            type="postLiked",
            subject_type="post",
            subject_id=self.initial_reply.id,
            data={"post_id": self.initial_reply.id},
        )
        unread_before = Notification.objects.filter(user=self.author, is_read=False).exclude(id=notification.id).count()
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before + 1)

        admin = NotificationAdmin(Notification, None)
        request = type("Request", (), {})()
        admin.message_user = lambda *args, **kwargs: None

        admin.mark_as_read(request, Notification.objects.filter(id=notification.id))
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before)

        admin.mark_as_unread(request, Notification.objects.filter(id=notification.id))
        self.assertEqual(NotificationService.get_unread_count(self.author), unread_before + 1)
