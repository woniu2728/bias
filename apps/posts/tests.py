from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from ninja_jwt.tokens import RefreshToken

from apps.discussions.services import DiscussionService
from apps.posts.models import Post
from apps.posts.models import PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.users.models import Group, Permission, User


class PostPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="poster",
            email="poster@example.com",
            password="password123",
        )

    def test_get_page_for_near_post(self):
        discussion = DiscussionService.create_discussion(
            title="Near pagination",
            content="First post",
            user=self.user,
        )

        for index in range(2, 46):
            PostService.create_post(
                discussion_id=discussion.id,
                content=f"Reply {index}",
                user=self.user,
            )

        page = PostService.get_page_for_near_post(
            discussion_id=discussion.id,
            near=41,
            limit=20,
            user=self.user,
        )

        self.assertEqual(page, 3)

    def test_create_post_retries_on_transient_sqlite_lock(self):
        discussion = DiscussionService.create_discussion(
            title="Retry post discussion",
            content="First post",
            user=self.user,
        )
        original_create = Post.objects.create
        state = {"failed": False}

        def flaky_create(*args, **kwargs):
            if not state["failed"]:
                state["failed"] = True
                raise OperationalError("database is locked")
            return original_create(*args, **kwargs)

        with patch("apps.core.db.time.sleep", return_value=None):
            with patch("apps.posts.services.Post.objects.create", side_effect=flaky_create):
                post = PostService.create_post(
                    discussion_id=discussion.id,
                    content="Retry reply",
                    user=self.user,
                )

        self.assertTrue(state["failed"])
        self.assertEqual(post.content, "Retry reply")


class PostFlagApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
        )
        self.reporter = User.objects.create_user(
            username="reporter",
            email="reporter@example.com",
            password="password123",
        )
        self.discussion = DiscussionService.create_discussion(
            title="Flag discussion",
            content="First post",
            user=self.author,
        )
        self.post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要举报的内容",
            user=self.author,
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.reporter).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_report_post_creates_flag(self):
        response = self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"违规内容","message":"包含明显违规信息"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["reason"], "违规内容")
        self.assertEqual(payload["status"], "open")

        flag = PostFlag.objects.get(post=self.post, user=self.reporter)
        self.assertEqual(flag.message, "包含明显违规信息")

    def test_suspended_user_cannot_reply_or_report_post(self):
        self.reporter.suspended_until = timezone.now() + timedelta(days=2)
        self.reporter.suspend_message = "封禁期间不可互动"
        self.reporter.save(update_fields=["suspended_until", "suspend_message"])

        response = self.client.post(
            f"/api/discussions/{self.discussion.id}/posts",
            data='{"content":"尝试回复"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("账号已被封禁", response.json()["error"])

        response = self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"违规内容","message":"尝试举报"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("封禁期间不可互动", response.json()["error"])

    def test_post_can_enter_approval_queue(self):
        trusted_group = Group.objects.create(name="Trusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")

        response = self.client.post(
            f"/api/discussions/{self.discussion.id}/posts",
            data='{"content":"需要审核的回复"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["approval_status"], "pending")

    def test_cannot_reply_in_tag_without_reply_permission(self):
        admin = User.objects.create_superuser(
            username="reply-admin",
            email="reply-admin@example.com",
            password="password123",
        )
        restricted_tag = Tag.objects.create(
            name="管理回复区",
            slug="staff-reply-only",
            view_scope=Tag.ACCESS_PUBLIC,
            start_discussion_scope=Tag.ACCESS_PUBLIC,
            reply_scope=Tag.ACCESS_STAFF,
        )
        restricted_discussion = DiscussionService.create_discussion(
            title="限制回复讨论",
            content="只有管理员能回复",
            user=admin,
            tag_ids=[restricted_tag.id],
        )

        response = self.client.post(
            f"/api/discussions/{restricted_discussion.id}/posts",
            data='{"content":"尝试回复"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("没有权限", response.json()["error"])


class PostLikeTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="like_author",
            email="like_author@example.com",
            password="password123",
        )
        self.liker = User.objects.create_user(
            username="like_user",
            email="like_user@example.com",
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

    def test_duplicate_like_raises_value_error_not_integrity_error(self):
        PostService.like_post(self.post.id, self.liker)

        with self.assertRaisesMessage(ValueError, "已经点赞过了"):
            PostService.like_post(self.post.id, self.liker)

    def test_like_own_post_returns_bad_request_in_api(self):
        token = RefreshToken.for_user(self.author).access_token

        response = self.client.post(
            f"/api/posts/{self.post.id}/like",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不能给自己的帖子点赞")
