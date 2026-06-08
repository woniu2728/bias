from unittest.mock import Mock, patch

from django.test import TestCase
from ninja_jwt.tokens import RefreshToken

from apps.core.extension_settings_service import save_extension_settings
from apps.discussions.services import DiscussionService
from extensions.posts.backend.services import PostService
from extensions.users.backend.models import User
from extensions.likes.backend.services import like_post


class LikesExtensionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="like_author",
            email="like_author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.liker = User.objects.create_user(
            username="like_user",
            email="like_user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.admin = User.objects.create_superuser(
            username="like-admin",
            email="like-admin@example.com",
            password="password123",
        )
        self.discussion = DiscussionService.create_discussion(
            title="Like discussion",
            content="Initial post",
            user=self.author,
        )
        self.post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="Reply to like",
            user=self.author,
        )

    def admin_auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extension_detail_api_surfaces_registered_resources_for_likes_extension(self):
        response = self.client.get(
            "/api/admin/extensions/likes",
            **self.admin_auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_forum_entry"], "extensions/likes/frontend/forum/index.js")
        like_fields = {
            item["field"]
            for item in payload["resource_fields"]
            if item["module_id"] == "likes"
        }
        self.assertIn("like_count", like_fields)
        self.assertIn("is_liked", like_fields)
        self.assertIn("can_like", like_fields)
        self.assertTrue(
            any(item["module_id"] == "likes" and item["endpoint"] == "like" for item in payload["resource_endpoints"])
        )
        self.assertTrue(any(item["key"] == "like_own_post" for item in payload["settings_schema"]))
        self.assertTrue(any(item["code"] == "likedBy" for item in payload["search_filters"]))
        self.assertTrue(any(item["module_id"] == "likes" and item["relationship"] == "likes" for item in payload["resource_relationships"]))
        self.assertTrue(any(item["module_id"] == "likes" and item["filter"] == "likedBy" for item in payload["resource_filters"]))
        self.assertTrue(any(item["code"] == "postLiked" for item in payload["notification_types"]))

    def test_duplicate_like_raises_value_error_not_integrity_error(self):
        with self.captureOnCommitCallbacks(execute=True):
            like_post(self.post.id, self.liker)

        with self.assertRaisesMessage(ValueError, "已经点赞过了"):
            like_post(self.post.id, self.liker)

    def test_like_own_post_returns_bad_request_in_api(self):
        token = RefreshToken.for_user(self.author).access_token

        response = self.client.post(
            f"/api/posts/{self.post.id}/like",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不能给自己的帖子点赞")

    def test_like_own_post_setting_allows_author_to_like_own_post(self):
        save_extension_settings("likes", {"like_own_post": True})
        token = RefreshToken.for_user(self.author).access_token

        response = self.client.post(
            f"/api/posts/{self.post.id}/like",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)

    def test_post_global_index_supports_liked_by_extension_filter(self):
        other_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="Reply not liked",
            user=self.author,
        )
        with self.captureOnCommitCallbacks(execute=True):
            like_post(self.post.id, self.liker)

        response = self.client.get(
            "/api/posts",
            {"filter[likedBy]": self.liker.username},
        )

        self.assertEqual(response.status_code, 200, response.content)
        ids = [item["id"] for item in response.json()["data"]]
        self.assertIn(self.post.id, ids)
        self.assertNotIn(other_post.id, ids)

    def test_post_search_supports_liked_by_extension_filter(self):
        other_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="Reply to like",
            user=self.author,
        )
        with self.captureOnCommitCallbacks(execute=True):
            like_post(self.post.id, self.liker)

        response = self.client.get(
            "/api/search",
            {"q": f"Reply likedBy:{self.liker.username}", "type": "posts"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        ids = [item["id"] for item in response.json()["posts"]]
        self.assertIn(self.post.id, ids)
        self.assertNotIn(other_post.id, ids)

    def test_like_post_dispatches_domain_event_instead_of_direct_notification_call(self):
        with patch("extensions.notifications.backend.services.NotificationService.notify_post_liked") as notify_mock:
            with self.captureOnCommitCallbacks(execute=True):
                like_post(self.post.id, self.liker)

        notify_mock.assert_called_once_with(post_id=self.post.id, from_user=self.liker)

    def test_like_post_dispatches_domain_event_after_commit(self):
        with patch("apps.core.domain_events.get_forum_event_bus") as get_bus_mock:
            bus_mock = Mock()
            get_bus_mock.return_value = bus_mock

            with self.captureOnCommitCallbacks() as callbacks:
                like_post(self.post.id, self.liker)

            self.assertEqual(len(callbacks), 1)
            bus_mock.dispatch.assert_not_called()

            callbacks[0]()

        bus_mock.dispatch.assert_called_once()
