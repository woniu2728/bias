from django.test import TestCase
from ninja_jwt.tokens import RefreshToken

from extensions.discussions.backend.models import DiscussionUser
from apps.discussions.services import DiscussionService
from apps.posts.services import PostService
from apps.users.models import User
from extensions.notifications.backend.models import Notification


class SubscriptionsExtensionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="subscription-author",
            email="subscription-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.reader = User.objects.create_user(
            username="subscription-reader",
            email="subscription-reader@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.admin = User.objects.create_superuser(
            username="subscription-admin",
            email="subscription-admin@example.com",
            password="password123",
        )

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extension_detail_api_surfaces_registered_capabilities_for_subscriptions_extension(self):
        response = self.client.get(
            "/api/admin/extensions/subscriptions",
            **self.auth_header(self.admin),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_forum_entry"], "extensions/subscriptions/frontend/forum/index.js")
        self.assertTrue(
            any(
                route["path"] == "/following"
                and route["name"] == "following"
                and route["component"] == "DiscussionListView"
                and route["requires_auth"]
                for route in payload["frontend_routes"]
            )
        )
        self.assertTrue(any(item["code"] == "following" for item in payload["discussion_list_filters"]))
        self.assertTrue(any(item["code"] == "is_following" for item in payload["search_filters"]))
        self.assertTrue(any(item["target"] == "discussion" for item in payload["search_drivers"]))
        self.assertTrue(any(item["code"] == "discussionReply" for item in payload["notification_types"]))
        self.assertTrue(any(item["key"] == "follow_after_reply" for item in payload["user_preferences"]))
        self.assertTrue(any(item["key"] == "notify_new_post" for item in payload["user_preferences"]))
        self.assertTrue(
            any(item["module_id"] == "subscriptions" and item["field"] == "is_subscribed" for item in payload["resource_fields"])
        )
        self.assertTrue(
            any(item["module_id"] == "subscriptions" and item["endpoint"] == "subscribe" for item in payload["resource_endpoints"])
        )
        self.assertTrue(
            any(
                item["event"] == "PostCreatedEvent"
                and item["module_id"] == "subscriptions"
                and item.get("source") == "runtime"
                for item in payload["event_listeners"]
            )
        )

    def test_create_discussion_auto_follows_when_preference_enabled(self):
        self.author.preferences = {"follow_after_create": True}
        self.author.save(update_fields=["preferences"])

        with self.captureOnCommitCallbacks(execute=True):
            discussion = DiscussionService.create_discussion(
                title="Auto follow started discussion",
                content="Initial post",
                user=self.author,
            )

        state = DiscussionUser.objects.get(discussion=discussion, user=self.author)
        self.assertTrue(state.is_subscribed)
        self.assertEqual(state.last_read_post_number, 1)

    def test_reply_auto_follows_when_preference_enabled(self):
        self.author.preferences = {"follow_after_reply": True}
        self.author.save(update_fields=["preferences"])

        discussion = DiscussionService.create_discussion(
            title="Auto follow discussion",
            content="First post",
            user=self.author,
        )
        DiscussionUser.objects.filter(discussion=discussion, user=self.author).update(
            last_read_post_number=1,
            is_subscribed=False,
        )

        with self.captureOnCommitCallbacks(execute=True):
            reply = PostService.create_post(
                discussion_id=discussion.id,
                content="My followed reply",
                user=self.author,
            )

        state = DiscussionUser.objects.get(discussion=discussion, user=self.author)
        self.assertEqual(state.last_read_post_number, reply.number)
        self.assertTrue(state.is_subscribed)

    def test_discussion_list_following_filter_uses_registered_filter_code(self):
        followed = DiscussionService.create_discussion(
            title="关注过滤 API",
            content="关注过滤内容",
            user=self.author,
        )
        other = DiscussionService.create_discussion(
            title="未关注过滤 API",
            content="未关注过滤内容",
            user=self.author,
        )
        DiscussionUser.objects.update_or_create(
            discussion=followed,
            user=self.reader,
            defaults={"is_subscribed": True, "last_read_post_number": 1},
        )
        DiscussionUser.objects.update_or_create(
            discussion=other,
            user=self.reader,
            defaults={"is_subscribed": False, "last_read_post_number": 1},
        )

        following_response = self.client.get(
            "/api/discussions/",
            {"filter": "following"},
            **self.auth_header(self.reader),
        )
        self.assertEqual(following_response.status_code, 200, following_response.content)
        self.assertEqual([item["id"] for item in following_response.json()["data"]], [followed.id])

    def test_discussion_list_exposes_following_filter_route(self):
        DiscussionService.create_discussion(
            title="关注过滤器元数据",
            content="用于验证扩展过滤器",
            user=self.author,
        )

        response = self.client.get(
            "/api/discussions/",
            {"page": 0, "limit": 999},
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(any(item["code"] == "following" and item["route_path"] == "/following" for item in payload["available_filters"]))
        self.assertTrue(any(item["code"] == "following" and item["requires_authenticated_user"] for item in payload["available_filters"]))

    def test_search_api_supports_registered_following_filter(self):
        followed = DiscussionService.create_discussion(
            title="关注搜索命中讨论",
            content="关注搜索过滤关键字",
            user=self.author,
        )
        other = DiscussionService.create_discussion(
            title="关注搜索未命中讨论",
            content="关注搜索过滤关键字",
            user=self.author,
        )
        DiscussionUser.objects.update_or_create(
            discussion=followed,
            user=self.reader,
            defaults={"is_subscribed": True, "last_read_post_number": 1},
        )
        DiscussionUser.objects.update_or_create(
            discussion=other,
            user=self.reader,
            defaults={"is_subscribed": False, "last_read_post_number": 1},
        )

        response = self.client.get(
            "/api/search",
            {"q": "关注搜索过滤关键字 is:following", "type": "discussions"},
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual([item["id"] for item in response.json()["discussions"]], [followed.id])

    def test_search_filters_api_exposes_registered_following_filter_syntax(self):
        response = self.client.get("/api/search/filters", {"target": "discussions"})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("is:following", {item["syntax"] for item in response.json()["filters"]})

    def test_delete_post_cleans_discussion_reply_notifications(self):
        discussion = DiscussionService.create_discussion(
            title="Notification cleanup discussion",
            content="First post",
            user=self.author,
        )
        reply = PostService.create_post(
            discussion_id=discussion.id,
            content="带通知的回复",
            user=self.reader,
        )
        notification = Notification.objects.create(
            user=self.author,
            from_user=self.reader,
            type="discussionReply",
            subject_type="discussion",
            subject_id=discussion.id,
            data={
                "discussion_id": discussion.id,
                "post_id": reply.id,
                "post_number": reply.number,
            },
        )

        with self.captureOnCommitCallbacks(execute=True):
            PostService.delete_post(reply.id, self.reader)

        self.assertFalse(Notification.objects.filter(id=notification.id).exists())

    def test_hiding_post_cleans_discussion_reply_notifications(self):
        discussion = DiscussionService.create_discussion(
            title="Hidden notification cleanup discussion",
            content="First post",
            user=self.author,
        )
        post = PostService.create_post(
            discussion_id=discussion.id,
            content="会被隐藏的回复",
            user=self.author,
        )
        notification = Notification.objects.create(
            user=self.reader,
            from_user=self.author,
            type="discussionReply",
            subject_type="discussion",
            subject_id=discussion.id,
            data={
                "discussion_id": discussion.id,
                "post_id": post.id,
                "post_number": post.number,
            },
        )

        with self.captureOnCommitCallbacks(execute=True):
            PostService.set_hidden_state(post, self.admin, True)

        self.assertFalse(Notification.objects.filter(id=notification.id).exists())
