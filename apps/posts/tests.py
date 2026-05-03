from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from ninja_jwt.tokens import RefreshToken

from apps.core.models import AuditLog
from apps.discussions.models import DiscussionUser
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
            is_email_confirmed=True,
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

    def test_own_reply_advances_read_state_without_auto_follow(self):
        self.user.preferences = {"follow_after_reply": False}
        self.user.save(update_fields=["preferences"])

        discussion = DiscussionService.create_discussion(
            title="Read progress discussion",
            content="First post",
            user=self.user,
        )

        DiscussionUser.objects.filter(discussion=discussion, user=self.user).update(
            last_read_post_number=1,
            is_subscribed=False,
        )

        reply = PostService.create_post(
            discussion_id=discussion.id,
            content="My own reply",
            user=self.user,
        )

        state = DiscussionUser.objects.get(discussion=discussion, user=self.user)
        self.assertEqual(state.last_read_post_number, reply.number)
        self.assertFalse(state.is_subscribed)


class PostFlagApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.admin = User.objects.create_superuser(
            username="flag-admin",
            email="flag-admin@example.com",
            password="password123",
        )
        self.reporter = User.objects.create_user(
            username="reporter",
            email="reporter@example.com",
            password="password123",
            is_email_confirmed=True,
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

    def auth_header_for(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def auth_header(self):
        return self.auth_header_for(self.reporter)

    def admin_auth_header(self):
        return self.auth_header_for(self.admin)

    def test_post_detail_exposes_user_primary_group_via_resource_payload(self):
        group = Group.objects.create(name="Post Authors", color="#8e44ad", icon="fas fa-comment")
        self.author.user_groups.add(group)

        response = self.client.get(f"/api/posts/{self.post.id}")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["user"]["primary_group"]["name"], group.name)

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

    def test_reported_post_exposes_flag_feedback_for_reporter(self):
        self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"违规内容","message":"包含明显违规信息"}',
            content_type="application/json",
            **self.auth_header(),
        )

        response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        target = next(item for item in response.json()["data"] if item["id"] == self.post.id)
        self.assertTrue(target["viewer_has_open_flag"])
        self.assertEqual(target["open_flag_count"], 0)

    def test_staff_can_resolve_flags_from_forum_post_flow(self):
        self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"违规内容","message":"包含明显违规信息"}',
            content_type="application/json",
            **self.auth_header(),
        )

        response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.admin_auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        target = next(item for item in response.json()["data"] if item["id"] == self.post.id)
        self.assertEqual(target["open_flag_count"], 1)
        self.assertEqual(len(target["open_flags"]), 1)
        self.assertTrue(target["can_moderate_flags"])

        resolve_response = self.client.post(
            f"/api/posts/{self.post.id}/flags/resolve",
            data='{"status":"resolved","resolution_note":"已在前台处理"}',
            content_type="application/json",
            **self.admin_auth_header(),
        )

        self.assertEqual(resolve_response.status_code, 200, resolve_response.content)
        self.assertEqual(resolve_response.json()["resolved_count"], 1)
        self.assertEqual(resolve_response.json()["post"]["open_flag_count"], 0)

        flag = PostFlag.objects.get(post=self.post, user=self.reporter)
        self.assertEqual(flag.status, PostFlag.STATUS_RESOLVED)
        self.assertEqual(flag.resolution_note, "已在前台处理")
        self.assertEqual(flag.resolved_by_id, self.admin.id)

    def test_non_staff_cannot_resolve_flags_from_forum_post_flow(self):
        self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"违规内容","message":"包含明显违规信息"}',
            content_type="application/json",
            **self.auth_header(),
        )

        response = self.client.post(
            f"/api/posts/{self.post.id}/flags/resolve",
            data='{"status":"resolved"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("只有管理员", response.json()["error"])

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

    def test_unverified_user_cannot_reply(self):
        self.reporter.is_email_confirmed = False
        self.reporter.save(update_fields=["is_email_confirmed"])

        response = self.client.post(
            f"/api/discussions/{self.discussion.id}/posts",
            data='{"content":"尝试回复"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "请先完成邮箱验证后再回复讨论")

    def test_cannot_reply_without_discussion_reply_permission(self):
        restricted_group = Group.objects.create(name="ReplyDisabledGroup", color="#95a5a6")
        self.reporter.user_groups.add(restricted_group)

        response = self.client.post(
            f"/api/discussions/{self.discussion.id}/posts",
            data='{"content":"尝试回复"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限回复讨论")

    def test_delete_last_approved_reply_rebuilds_discussion_last_post_stats(self):
        trailing_reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="最后一条已发布回复",
            user=self.reporter,
        )

        discussion = self.discussion
        discussion.refresh_from_db()
        self.assertEqual(discussion.last_post_id, trailing_reply.id)
        self.assertEqual(discussion.last_post_number, trailing_reply.number)

        PostService.delete_post(trailing_reply.id, self.reporter)

        discussion.refresh_from_db()
        self.assertEqual(discussion.comment_count, 2)
        self.assertEqual(discussion.last_post_id, self.post.id)
        self.assertEqual(discussion.last_post_number, self.post.number)
        self.assertEqual(discussion.last_posted_user_id, self.post.user_id)

        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.comment_count, 0)

    def test_delete_pending_reply_does_not_decrement_comment_stats(self):
        trusted_group = Group.objects.create(name="DeletePendingReplyTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")
        pending_reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="不会计入统计的待审核回复",
            user=self.reporter,
        )

        discussion = self.discussion
        discussion.refresh_from_db()
        self.assertEqual(discussion.comment_count, 2)

        PostService.delete_post(pending_reply.id, self.reporter)

        discussion.refresh_from_db()
        self.assertEqual(discussion.comment_count, 2)
        self.assertEqual(discussion.last_post_id, self.post.id)
        self.assertEqual(discussion.last_post_number, self.post.number)

    def test_delete_discussion_updates_reply_author_comment_counts(self):
        extra_reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="这条回复会随讨论一起删除",
            user=self.reporter,
        )

        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.comment_count, 1)

        DiscussionService.delete_discussion(self.discussion.id, self.admin)

        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.comment_count, 0)

    def test_all_posts_list_respects_hidden_discussion_visibility(self):
        DiscussionService.set_hidden_state(self.discussion, self.admin, True)

        response = self.client.get(
            "/api/posts",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotIn(self.post.id, {item["id"] for item in response.json()["data"]})

        admin_response = self.client.get(
            "/api/posts",
            **self.admin_auth_header(),
        )

        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertIn(self.post.id, {item["id"] for item in admin_response.json()["data"]})

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

    def test_author_can_still_view_rejected_reply_and_note(self):
        admin = User.objects.create_superuser(
            username="reply-approval-admin",
            email="reply-approval-admin@example.com",
            password="password123",
        )
        rejected_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要补充说明",
            user=self.reporter,
        )
        PostService.reject_post(rejected_post, admin, note="请补充更完整的回复内容")

        detail_response = self.client.get(
            f"/api/posts/{rejected_post.id}",
            **self.auth_header(),
        )

        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.json()["approval_status"], "rejected")
        self.assertEqual(detail_response.json()["approval_note"], "请补充更完整的回复内容")

        list_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.auth_header(),
        )

        self.assertEqual(list_response.status_code, 200, list_response.content)
        target = next(item for item in list_response.json()["data"] if item["id"] == rejected_post.id)
        self.assertEqual(target["approval_status"], "rejected")

    def test_other_member_cannot_view_rejected_reply(self):
        admin = User.objects.create_superuser(
            username="reply-approval-admin-other",
            email="reply-approval-admin-other@example.com",
            password="password123",
        )
        rejected_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要补充说明",
            user=self.reporter,
        )
        PostService.reject_post(rejected_post, admin, note="请补充更完整的回复内容")

        reader = User.objects.create_user(
            username="reader-posts",
            email="reader-posts@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        token = RefreshToken.for_user(reader).access_token

        detail_response = self.client.get(
            f"/api/posts/{rejected_post.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(detail_response.status_code, 404, detail_response.content)

    def test_author_editing_rejected_reply_resubmits_it_for_review(self):
        admin = User.objects.create_superuser(
            username="reply-approval-admin-resubmit",
            email="reply-approval-admin-resubmit@example.com",
            password="password123",
        )
        rejected_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要补充说明",
            user=self.reporter,
        )
        PostService.reject_post(rejected_post, admin, note="请补充更完整的回复内容")

        response = self.client.patch(
            f"/api/posts/{rejected_post.id}",
            data='{"content":"已经补充完整说明"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["approval_status"], "pending")
        self.assertEqual(response.json()["approval_note"], "")

        detail_response = self.client.get(
            f"/api/posts/{rejected_post.id}",
            **self.auth_header(),
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.json()["approval_status"], "pending")
        self.assertEqual(detail_response.json()["content"], "已经补充完整说明")

        reader = User.objects.create_user(
            username="reader-posts-pending",
            email="reader-posts-pending@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        token = RefreshToken.for_user(reader).access_token
        reader_detail_response = self.client.get(
            f"/api/posts/{rejected_post.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(reader_detail_response.status_code, 404, reader_detail_response.content)

        reader_list_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(reader_list_response.status_code, 200, reader_list_response.content)
        self.assertFalse(any(item["id"] == rejected_post.id for item in reader_list_response.json()["data"]))

    def test_approving_pending_reply_makes_it_visible_to_other_members(self):
        trusted_group = Group.objects.create(name="TrustedReplyVisible", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")

        response = self.client.post(
            f"/api/discussions/{self.discussion.id}/posts",
            data='{"content":"需要审核后公开的回复"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        pending_post_id = response.json()["id"]
        pending_post = Post.objects.get(id=pending_post_id)
        self.assertEqual(pending_post.approval_status, Post.APPROVAL_PENDING)

        PostService.approve_post(pending_post, self.admin, note="已通过审核")

        pending_post.refresh_from_db()
        self.assertEqual(pending_post.approval_status, Post.APPROVAL_APPROVED)

        reader = User.objects.create_user(
            username="reader-posts-visible",
            email="reader-posts-visible@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        token = RefreshToken.for_user(reader).access_token

        detail_response = self.client.get(
            f"/api/posts/{pending_post.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.json()["approval_status"], "approved")

        list_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(list_response.status_code, 200, list_response.content)
        self.assertTrue(any(item["id"] == pending_post.id for item in list_response.json()["data"]))

    def test_post_approval_transitions_keep_discussion_and_author_counts_consistent(self):
        trusted_group = Group.objects.create(name="TrustedReplyCounts", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")
        pending_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要审核的计数回复",
            user=self.reporter,
        )

        self.discussion.refresh_from_db()
        self.reporter.refresh_from_db()
        self.assertEqual(self.discussion.comment_count, 2)
        self.assertEqual(self.reporter.comment_count, 0)

        PostService.approve_post(pending_post, self.admin, note="通过")
        self.discussion.refresh_from_db()
        self.reporter.refresh_from_db()
        self.assertEqual(self.discussion.comment_count, 3)
        self.assertEqual(self.reporter.comment_count, 1)
        self.assertEqual(self.discussion.last_post_id, pending_post.id)

        pending_post.refresh_from_db()
        PostService.approve_post(pending_post, self.admin, note="重复通过")
        self.discussion.refresh_from_db()
        self.reporter.refresh_from_db()
        self.assertEqual(self.discussion.comment_count, 3)
        self.assertEqual(self.reporter.comment_count, 1)

        PostService.reject_post(pending_post, self.admin, note="下架")
        self.discussion.refresh_from_db()
        self.reporter.refresh_from_db()
        self.assertEqual(self.discussion.comment_count, 2)
        self.assertEqual(self.reporter.comment_count, 0)
        self.assertEqual(self.discussion.last_post_id, self.post.id)

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

    def test_owner_without_edit_own_permission_cannot_edit_reply(self):
        member_group = Group.objects.create(name="ReplyAuthorNoEdit", color="#4d698e")
        Permission.objects.create(group=member_group, permission="discussion.reply")
        self.reporter.user_groups.add(member_group)

        reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要权限才能编辑",
            user=self.reporter,
        )

        response = self.client.patch(
            f"/api/posts/{reply.id}",
            data='{"content":"尝试修改"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限编辑此帖子")

    def test_owner_with_delete_own_permission_can_delete_reply(self):
        member_group = Group.objects.create(name="ReplyAuthorDeleteOwn", color="#4d698e")
        Permission.objects.create(group=member_group, permission="discussion.reply")
        Permission.objects.create(group=member_group, permission="discussion.deleteOwn")
        self.reporter.user_groups.add(member_group)

        reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="允许删除自己的回复",
            user=self.reporter,
        )

        response = self.client.delete(
            f"/api/posts/{reply.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Post.objects.filter(id=reply.id).exists())
        self.assertFalse(AuditLog.objects.filter(action="admin.post.delete").exists())

    def test_user_with_global_delete_permission_can_delete_others_reply(self):
        moderator = User.objects.create_user(
            username="reply-moderator",
            email="reply-moderator@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        moderator_group = Group.objects.create(name="ReplyDeleteModerator", color="#4d698e")
        Permission.objects.create(group=moderator_group, permission="discussion.delete")
        moderator.user_groups.add(moderator_group)

        reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="会被全局删除权限用户删除",
            user=self.author,
        )

        response = self.client.delete(
            f"/api/posts/{reply.id}",
            **self.auth_header_for(moderator),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Post.objects.filter(id=reply.id).exists())
        audit_log = AuditLog.objects.get(action="admin.post.delete", target_id=reply.id)
        self.assertEqual(audit_log.user_id, moderator.id)
        self.assertEqual(audit_log.target_type, "post")
        self.assertEqual(audit_log.data["discussion_id"], self.discussion.id)


class PostLikeTests(TestCase):
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
