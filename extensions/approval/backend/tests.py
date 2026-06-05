import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from ninja_jwt.tokens import RefreshToken

from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from apps.notifications.models import Notification
from apps.posts.models import Post
from apps.posts.services import PostService
from apps.users.models import Group, Permission, User
from extensions.approval.backend.resources import resolve_approval_event_data


def discussion_resource_payload(*, title=None, content=None, tag_ids=None):
    attributes = {}
    if title is not None:
        attributes["title"] = title
    if content is not None:
        attributes["content"] = content

    payload = {"data": {"type": "discussion", "attributes": attributes}}
    if tag_ids is not None:
        payload["data"]["relationships"] = {
            "tags": {
                "data": [
                    {"type": "tag", "id": str(tag_id)}
                    for tag_id in tag_ids
                ],
            },
        }
    return payload


class AdminApprovalQueueApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-approval-mgr",
            email="admin-approval@example.com",
            password="password123",
        )
        self.trusted_group = Group.objects.create(
            name="Trusted",
            name_singular="Trusted",
            name_plural="Trusted",
            color="#4d698e",
        )
        Permission.objects.create(group=self.trusted_group, permission="startDiscussion")
        Permission.objects.create(group=self.trusted_group, permission="startDiscussionWithoutApproval")
        Permission.objects.create(group=self.trusted_group, permission="replyWithoutApproval")

        self.author = User.objects.create_user(
            username="approval-author",
            email="approval-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.author.user_groups.add(self.trusted_group)
        self.pending_author = User.objects.create_user(
            username="approval-pending-author",
            email="approval-pending-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.replier = User.objects.create_user(
            username="approval-replier",
            email="approval-replier@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        self.pending_discussion = DiscussionService.create_discussion(
            title="待审核讨论",
            content="首帖需要审核",
            user=self.pending_author,
        )
        self.discussion = DiscussionService.create_discussion(
            title="已通过讨论",
            content="已发布首帖",
            user=self.author,
        )
        self.post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="这是一条待审核回复",
            user=self.replier,
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extension_detail_api_surfaces_registered_capabilities_for_approval_extension(self):
        response = self.client.get(
            "/api/admin/extensions/approval",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_admin_entry"], "extensions/approval/frontend/admin/index.js")
        self.assertEqual(payload["frontend_forum_entry"], "extensions/approval/frontend/forum/index.js")
        self.assertGreater(payload["permission_summary"]["permission_count"], 0)
        self.assertGreater(payload["permission_summary"]["section_count"], 0)
        self.assertTrue(any(item["module_id"] == "approval" for item in payload["permission_modules"]))
        self.assertTrue(any(
            permission["module_id"] == "approval"
            for section in payload["permission_sections"]
            for permission in section["permissions"]
        ))
        self.assertFalse(any(
            permission["module_id"] != "approval"
            for section in payload["permission_sections"]
            for permission in section["permissions"]
        ))
        self.assertGreaterEqual(payload["capability_summary"]["notification_type_count"], 1)
        self.assertGreaterEqual(payload["capability_summary"]["user_preference_count"], 1)
        self.assertGreaterEqual(payload["capability_summary"]["event_listener_count"], 1)
        self.assertTrue(any(item["module_id"] == "approval" for item in payload["notification_types"]))
        self.assertTrue(any(item["module_id"] == "approval" for item in payload["user_preferences"]))
        self.assertTrue(any(item["module_id"] == "approval" and item["code"] == "postApproved" for item in payload["post_types"]))
        self.assertTrue(
            any(
                item["module_id"] == "approval"
                and item["event"] == "PostApprovedEvent"
                and item.get("source") == "runtime"
                for item in payload["event_listeners"]
            )
        )

    def test_admin_can_list_and_approve_queue(self):
        response = self.client.get(
            "/api/admin/approval-queue",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 2)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/admin/approval-queue/discussion/{self.pending_discussion.id}/approve",
                data=json.dumps({"note": "讨论符合规范"}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.pending_discussion.refresh_from_db()
        self.assertEqual(self.pending_discussion.approval_status, "approved")
        approved_notification = Notification.objects.get(
            user=self.pending_author,
            type="discussionApproved",
            subject_id=self.pending_discussion.id,
        )
        self.assertEqual(approved_notification.from_user_id, self.admin.id)
        self.assertEqual(approved_notification.data["approval_note"], "讨论符合规范")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/admin/approval-queue/post/{self.post.id}/reject",
                data=json.dumps({"note": "回复质量不足"}),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.post.refresh_from_db()
        self.assertEqual(self.post.approval_status, "rejected")
        self.assertIsNotNone(self.post.hidden_at)
        rejected_notification = Notification.objects.get(
            user=self.replier,
            type="postRejected",
            subject_id=self.post.id,
        )
        self.assertEqual(rejected_notification.from_user_id, self.admin.id)
        self.assertEqual(rejected_notification.data["approval_note"], "回复质量不足")

    def test_admin_can_bulk_process_approval_queue(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                "/api/admin/approval-queue/bulk/approve",
                data=json.dumps({
                    "note": "批量审核通过",
                    "items": [
                        {"type": "discussion", "id": self.pending_discussion.id},
                        {"type": "post", "id": self.post.id},
                    ],
                }),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["processed_count"], 2)
        self.assertEqual(payload["action"], "approve")
        self.assertEqual(len(payload["data"]), 2)

        self.pending_discussion.refresh_from_db()
        self.post.refresh_from_db()
        self.assertEqual(self.pending_discussion.approval_status, "approved")
        self.assertEqual(self.post.approval_status, "approved")

        discussion_notification = Notification.objects.get(
            user=self.pending_author,
            type="discussionApproved",
            subject_id=self.pending_discussion.id,
        )
        post_notification = Notification.objects.get(
            user=self.replier,
            type="postApproved",
            subject_id=self.post.id,
        )
        self.assertEqual(discussion_notification.data["approval_note"], "批量审核通过")
        self.assertEqual(post_notification.data["approval_note"], "批量审核通过")

    def test_bulk_approval_queue_rejects_invalid_payload(self):
        response = self.client.post(
            "/api/admin/approval-queue/bulk/reject",
            data=json.dumps({"note": "批量拒绝", "items": []}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("请至少选择一条待审核内容", response.json()["error"])

    def test_admin_without_approval_permissions_is_denied_for_bulk_processing(self):
        with patch("extensions.approval.backend.admin_api.UserService.has_forum_permission", return_value=False):
            response = self.client.post(
                "/api/admin/approval-queue/bulk/approve",
                data=json.dumps({
                    "note": "尝试越权批量审核",
                    "items": [{"type": "discussion", "id": self.pending_discussion.id}],
                }),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(response.status_code, 403, response.content)

    def test_non_staff_cannot_access_or_process_approval_queue(self):
        member_token = RefreshToken.for_user(self.pending_author).access_token
        auth = {"HTTP_AUTHORIZATION": f"Bearer {member_token}"}

        list_response = self.client.get(
            "/api/admin/approval-queue",
            **auth,
        )
        self.assertEqual(list_response.status_code, 403, list_response.content)

        approve_response = self.client.post(
            f"/api/admin/approval-queue/discussion/{self.pending_discussion.id}/approve",
            data=json.dumps({"note": "尝试越权审核"}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(approve_response.status_code, 403, approve_response.content)

        reject_post_response = self.client.post(
            f"/api/admin/approval-queue/post/{self.post.id}/reject",
            data=json.dumps({"note": "尝试越权拒绝回复"}),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(reject_post_response.status_code, 403, reject_post_response.content)

        bulk_response = self.client.post(
            "/api/admin/approval-queue/bulk/approve",
            data=json.dumps({
                "note": "尝试越权批量审核",
                "items": [{"type": "discussion", "id": self.pending_discussion.id}],
            }),
            content_type="application/json",
            **auth,
        )
        self.assertEqual(bulk_response.status_code, 403, bulk_response.content)

    def test_admin_without_approval_permissions_is_denied(self):
        with patch("extensions.approval.backend.admin_api.UserService.has_forum_permission", return_value=False):
            list_response = self.client.get(
                "/api/admin/approval-queue",
                **self.auth_header(),
            )
            self.assertEqual(list_response.status_code, 403, list_response.content)

            approve_response = self.client.post(
                f"/api/admin/approval-queue/discussion/{self.pending_discussion.id}/approve",
                data=json.dumps({"note": "尝试越权审核"}),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(approve_response.status_code, 403, approve_response.content)

            reject_post_response = self.client.post(
                f"/api/admin/approval-queue/post/{self.post.id}/reject",
                data=json.dumps({"note": "尝试越权拒绝回复"}),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(reject_post_response.status_code, 403, reject_post_response.content)


class PostApprovalForumApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="approval-post-author",
            email="approval-post-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.admin = User.objects.create_superuser(
            username="approval-post-admin",
            email="approval-post-admin@example.com",
            password="password123",
        )
        self.reporter = User.objects.create_user(
            username="approval-post-reporter",
            email="approval-post-reporter@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.discussion = DiscussionService.create_discussion(
            title="Approval post discussion",
            content="First post",
            user=self.author,
        )
        self.post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要审核相关操作的内容",
            user=self.author,
        )

    def auth_header_for(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def auth_header(self):
        return self.auth_header_for(self.reporter)

    def admin_auth_header(self):
        return self.auth_header_for(self.admin)

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
        rejected_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要补充说明",
            user=self.reporter,
        )
        PostService.reject_post(rejected_post, self.admin, note="请补充更完整的回复内容")

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
        rejected_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要补充说明",
            user=self.reporter,
        )
        PostService.reject_post(rejected_post, self.admin, note="请补充更完整的回复内容")

        reader = User.objects.create_user(
            username="reader-posts",
            email="reader-posts@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        detail_response = self.client.get(
            f"/api/posts/{rejected_post.id}",
            **self.auth_header_for(reader),
        )

        self.assertEqual(detail_response.status_code, 404, detail_response.content)

    def test_author_editing_rejected_reply_resubmits_it_for_review(self):
        rejected_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="需要补充说明",
            user=self.reporter,
        )
        PostService.reject_post(rejected_post, self.admin, note="请补充更完整的回复内容")

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
        reader_detail_response = self.client.get(
            f"/api/posts/{rejected_post.id}",
            **self.auth_header_for(reader),
        )
        self.assertEqual(reader_detail_response.status_code, 404, reader_detail_response.content)

        reader_list_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.auth_header_for(reader),
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

        with self.captureOnCommitCallbacks(execute=True):
            PostService.approve_post(pending_post, self.admin, note="已通过审核")

        pending_post.refresh_from_db()
        self.assertEqual(pending_post.approval_status, Post.APPROVAL_APPROVED)

        reader = User.objects.create_user(
            username="reader-posts-visible",
            email="reader-posts-visible@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        detail_response = self.client.get(
            f"/api/posts/{pending_post.id}",
            **self.auth_header_for(reader),
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.json()["approval_status"], "approved")

        list_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.auth_header_for(reader),
        )
        self.assertEqual(list_response.status_code, 200, list_response.content)
        self.assertTrue(any(item["id"] == pending_post.id for item in list_response.json()["data"]))
        approved_event = next(item for item in list_response.json()["data"] if item["type"] == "postApproved")
        self.assertEqual(
            approved_event["event_data"],
            {
                "kind": "postApproved",
                "note": "已通过审核",
                "previous_status": "pending",
                "target_post_id": pending_post.id,
                "target_post_number": pending_post.number,
            },
        )

    def test_rejecting_post_creates_post_rejected_event_post(self):
        pending_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="待拒绝回复",
            user=self.reporter,
        )

        with self.captureOnCommitCallbacks(execute=True):
            PostService.reject_post(pending_post, self.admin, note="回复质量不足")

        posts_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.admin_auth_header(),
        )
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        rejected_event = next(item for item in posts_response.json()["data"] if item["type"] == "postRejected")
        self.assertEqual(
            rejected_event["event_data"],
            {
                "kind": "postRejected",
                "note": "回复质量不足",
                "previous_status": "approved",
                "target_post_id": pending_post.id,
                "target_post_number": pending_post.number,
            },
        )

    def test_editing_rejected_post_creates_post_resubmitted_event_post(self):
        rejected_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="被拒绝的回复",
            user=self.reporter,
        )
        with self.captureOnCommitCallbacks(execute=True):
            PostService.reject_post(rejected_post, self.admin, note="请补充更多细节")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/posts/{rejected_post.id}",
                data='{"content":"修改后的回复内容"}',
                content_type="application/json",
                **self.auth_header(),
            )
        self.assertEqual(response.status_code, 200, response.content)

        posts_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.auth_header(),
        )
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        resubmitted_event = next(item for item in posts_response.json()["data"] if item["type"] == "postResubmitted")
        self.assertEqual(
            resubmitted_event["event_data"],
            {
                "kind": "postResubmitted",
                "note": "",
                "previous_status": "rejected",
                "target_post_id": rejected_post.id,
                "target_post_number": rejected_post.number,
            },
        )


class DiscussionApprovalForumApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="approval-discussion-author",
            email="approval-discussion-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.reader = User.objects.create_user(
            username="approval-discussion-reader",
            email="approval-discussion-reader@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_discussion_can_enter_approval_queue(self):
        trusted_group = Group.objects.create(name="Trusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps(discussion_resource_payload(
                title="Pending discussion",
                content="Needs approval",
                tag_ids=[],
            )),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["approval_status"], "pending")

    def test_author_can_still_view_rejected_discussion_and_note(self):
        discussion = DiscussionService.create_discussion(
            title="Rejected discussion",
            content="Needs moderation",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="approval-admin",
            email="approval-admin@example.com",
            password="password123",
        )
        DiscussionService.reject_discussion(discussion, admin, note="内容需要补充上下文")

        detail_response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.author),
        )

        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.json()["approval_status"], "rejected")
        self.assertEqual(detail_response.json()["approval_note"], "内容需要补充上下文")

        list_response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.author),
        )

        self.assertEqual(list_response.status_code, 200, list_response.content)
        items = list_response.json()["data"]
        self.assertTrue(any(item["id"] == discussion.id and item["approval_status"] == "rejected" for item in items))

    def test_other_member_cannot_view_rejected_discussion(self):
        discussion = DiscussionService.create_discussion(
            title="Rejected discussion",
            content="Needs moderation",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="approval-admin-other",
            email="approval-admin-other@example.com",
            password="password123",
        )
        DiscussionService.reject_discussion(discussion, admin, note="拒绝原因")

        detail_response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.reader),
        )

        self.assertEqual(detail_response.status_code, 404, detail_response.content)

    def test_author_editing_rejected_discussion_resubmits_it_for_review(self):
        discussion = DiscussionService.create_discussion(
            title="Rejected discussion",
            content="Needs moderation",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="approval-admin-resubmit",
            email="approval-admin-resubmit@example.com",
            password="password123",
        )
        DiscussionService.reject_discussion(discussion, admin, note="请补充上下文")

        response = self.client.patch(
            f"/api/discussions/{discussion.id}",
            data=json.dumps(discussion_resource_payload(
                title="Rejected discussion updated",
                content="Updated context for approval",
                tag_ids=[],
            )),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["approval_status"], "pending")

        detail_response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.author),
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        self.assertEqual(detail_response.json()["approval_status"], "pending")
        self.assertEqual(detail_response.json()["title"], "Rejected discussion updated")
        self.assertEqual(detail_response.json()["first_post"]["content"], "Updated context for approval")
        self.assertEqual(detail_response.json()["approval_note"], "")

        reader_response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.reader),
        )
        self.assertEqual(reader_response.status_code, 404, reader_response.content)

        reader_list_response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.reader),
        )
        self.assertEqual(reader_list_response.status_code, 200, reader_list_response.content)
        self.assertFalse(any(item["id"] == discussion.id for item in reader_list_response.json()["data"]))

    def test_approving_pending_discussion_makes_discussion_and_first_post_visible(self):
        trusted_group = Group.objects.create(name="Trusted2", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps(discussion_resource_payload(
                title="Pending discussion to approve",
                content="Needs approval first",
                tag_ids=[],
            )),
            content_type="application/json",
            **self.auth_header(self.author),
        )
        self.assertEqual(response.status_code, 200, response.content)
        discussion_id = response.json()["id"]

        discussion = Discussion.objects.get(id=discussion_id)
        self.assertEqual(discussion.approval_status, Discussion.APPROVAL_PENDING)

        admin = User.objects.create_superuser(
            username="approval-admin-visible",
            email="approval-admin-visible@example.com",
            password="password123",
        )
        with self.captureOnCommitCallbacks(execute=True):
            DiscussionService.approve_discussion(discussion, admin, note="已通过审核")

        discussion.refresh_from_db()
        self.assertEqual(discussion.approval_status, Discussion.APPROVAL_APPROVED)

        detail_response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.reader),
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        payload = detail_response.json()
        self.assertEqual(payload["approval_status"], "approved")
        self.assertEqual(payload["first_post"]["approval_status"], "approved")

        posts_response = self.client.get(f"/api/discussions/{discussion.id}/posts")
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        event_post = next(item for item in posts_response.json()["data"] if item["type"] == "discussionApproved")
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionApproved",
                "note": "已通过审核",
                "previous_status": "pending",
            },
        )

        list_response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.reader),
        )
        self.assertEqual(list_response.status_code, 200, list_response.content)
        self.assertTrue(any(item["id"] == discussion.id for item in list_response.json()["data"]))

    def test_rejecting_discussion_creates_discussion_rejected_event_post(self):
        discussion = DiscussionService.create_discussion(
            title="Reject me",
            content="Needs rejection",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="discussion-reject-admin",
            email="discussion-reject-admin@example.com",
            password="password123",
        )

        with self.captureOnCommitCallbacks(execute=True):
            DiscussionService.reject_discussion(discussion, admin, note="内容不符合要求")

        posts_response = self.client.get(
            f"/api/discussions/{discussion.id}/posts",
            **self.auth_header(admin),
        )
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        event_post = next(item for item in posts_response.json()["data"] if item["type"] == "discussionRejected")
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionRejected",
                "note": "内容不符合要求",
                "previous_status": "approved",
            },
        )

    def test_editing_rejected_discussion_creates_resubmitted_event_post(self):
        discussion = DiscussionService.create_discussion(
            title="Resubmit me",
            content="Original content",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="discussion-resubmit-admin",
            email="discussion-resubmit-admin@example.com",
            password="password123",
        )
        DiscussionService.reject_discussion(discussion, admin, note="请补充细节")

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/discussions/{discussion.id}",
                data=json.dumps({
                    "content": "Updated content for review",
                }),
                content_type="application/json",
                **self.auth_header(self.author),
            )

        self.assertEqual(response.status_code, 200, response.content)
        posts_response = self.client.get(
            f"/api/discussions/{discussion.id}/posts",
            **self.auth_header(self.author),
        )
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        event_post = next(item for item in posts_response.json()["data"] if item["type"] == "discussionResubmitted")
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionResubmitted",
                "note": "",
                "previous_status": "rejected",
            },
        )


class ApprovalSearchVisibilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="approval-searcher",
            email="approval-searcher@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_discussion_list_search_respects_post_approval_visibility(self):
        discussion = DiscussionService.create_discussion(
            title="普通讨论标题",
            content="首帖不包含目标词",
            user=self.user,
        )
        pending_author = User.objects.create_user(
            username="list-search-pending",
            email="list-search-pending@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        trusted_group = Group.objects.create(name="ListSearchTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")
        PostService.create_post(
            discussion_id=discussion.id,
            content="pendingreplyvisibilitykeyword",
            user=pending_author,
        )

        guest_discussions, guest_total = DiscussionService.get_discussion_list(q="pendingreplyvisibilitykeyword")
        author_discussions, author_total = DiscussionService.get_discussion_list(
            q="pendingreplyvisibilitykeyword",
            user=pending_author,
        )

        self.assertEqual(guest_total, 0)
        self.assertEqual(guest_discussions, [])
        self.assertEqual(author_total, 1)
        self.assertEqual(author_discussions[0].id, discussion.id)

    def test_search_api_respects_discussion_approval_visibility(self):
        admin = User.objects.create_superuser(
            username="search-approval-admin",
            email="search-approval-admin@example.com",
            password="password123",
        )
        approved = DiscussionService.create_discussion(
            title="统一搜索可见性",
            content="公开讨论内容",
            user=self.user,
        )
        trusted_group = Group.objects.create(name="SearchApprovalTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")
        pending_author = User.objects.create_user(
            username="search-pending-author",
            email="search-pending-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        pending = DiscussionService.create_discussion(
            title="统一搜索可见性",
            content="待审核讨论内容",
            user=pending_author,
        )
        rejected = DiscussionService.create_discussion(
            title="统一搜索可见性",
            content="被拒绝讨论内容",
            user=pending_author,
        )
        DiscussionService.reject_discussion(rejected, admin, note="测试拒绝")

        guest_response = self.client.get("/api/search", {"q": "统一搜索可见性", "type": "discussions"})
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        self.assertEqual({item["id"] for item in guest_response.json()["discussions"]}, {approved.id})

        author_response = self.client.get(
            "/api/search",
            {"q": "统一搜索可见性", "type": "discussions"},
            **self.auth_header(pending_author),
        )
        self.assertEqual(author_response.status_code, 200, author_response.content)
        self.assertEqual(
            {item["id"] for item in author_response.json()["discussions"]},
            {approved.id, pending.id, rejected.id},
        )

        admin_response = self.client.get(
            "/api/search",
            {"q": "统一搜索可见性", "type": "discussions"},
            **self.auth_header(admin),
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertEqual(
            {item["id"] for item in admin_response.json()["discussions"]},
            {approved.id, pending.id, rejected.id},
        )

    def test_search_api_respects_post_approval_visibility(self):
        admin = User.objects.create_superuser(
            username="search-post-admin",
            email="search-post-admin@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="搜索回复可见性",
            content="首帖公开",
            user=self.user,
        )
        approved_reply = PostService.create_post(
            discussion_id=discussion.id,
            content="统一回复搜索公开内容",
            user=self.user,
        )
        trusted_group = Group.objects.create(name="SearchPostTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="replyWithoutApproval")
        pending_author = User.objects.create_user(
            username="search-post-pending",
            email="search-post-pending@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        pending_reply = PostService.create_post(
            discussion_id=discussion.id,
            content="统一回复搜索待审核内容",
            user=pending_author,
        )
        rejected_reply = PostService.create_post(
            discussion_id=discussion.id,
            content="统一回复搜索被拒绝内容",
            user=pending_author,
        )
        PostService.reject_post(rejected_reply, admin, note="测试拒绝回复")

        guest_response = self.client.get("/api/search", {"q": "统一回复搜索", "type": "posts"})
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        self.assertEqual({item["id"] for item in guest_response.json()["posts"]}, {approved_reply.id})

        author_response = self.client.get(
            "/api/search",
            {"q": "统一回复搜索", "type": "posts"},
            **self.auth_header(pending_author),
        )
        self.assertEqual(author_response.status_code, 200, author_response.content)
        self.assertEqual(
            {item["id"] for item in author_response.json()["posts"]},
            {approved_reply.id, pending_reply.id, rejected_reply.id},
        )

        admin_response = self.client.get(
            "/api/search",
            {"q": "统一回复搜索", "type": "posts"},
            **self.auth_header(admin),
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertEqual(
            {item["id"] for item in admin_response.json()["posts"]},
            {approved_reply.id, pending_reply.id, rejected_reply.id},
        )


class ApprovalPostEventResourceTests(TestCase):
    def test_resolves_post_event_data_payload(self):
        payload = resolve_approval_event_data(
            SimpleNamespace(
                type="postApproved",
                content="note:已通过\nprevious_status:pending\ntarget_post_id:9\ntarget_post_number:3",
            ),
            {},
        )

        self.assertEqual(
            payload,
            {
                "kind": "postApproved",
                "note": "已通过",
                "previous_status": "pending",
                "target_post_id": 9,
                "target_post_number": 3,
            },
        )
