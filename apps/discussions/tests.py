import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, Client
from django.test import override_settings
from django.db import OperationalError
from django.utils import timezone
from datetime import timedelta
from ninja_jwt.tokens import RefreshToken

from apps.discussions.models import Discussion
from apps.discussions.services import DiscussionService
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.users.models import Group, Permission, User


class DiscussionApiTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.author = User.objects.create_user(
            username="author",
            email="author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.reader = User.objects.create_user(
            username="reader",
            email="reader@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_create_discussion_accepts_bearer_token(self):
        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "JWT backed discussion",
                "content": "Created through the API.",
                "tag_ids": [],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["title"], "JWT backed discussion")
        self.assertEqual(payload["user"]["id"], self.author.id)

    def test_create_discussion_retries_on_transient_sqlite_lock(self):
        original_create = Discussion.objects.create
        state = {"failed": False}

        def flaky_create(*args, **kwargs):
            if not state["failed"]:
                state["failed"] = True
                raise OperationalError("database is locked")
            return original_create(*args, **kwargs)

        with patch("apps.core.db.time.sleep", return_value=None):
            with patch("apps.discussions.services.Discussion.objects.create", side_effect=flaky_create):
                discussion = DiscussionService.create_discussion(
                    title="Retry discussion",
                    content="Retry body",
                    user=self.author,
                )

        self.assertTrue(state["failed"])
        self.assertEqual(discussion.title, "Retry discussion")

    def test_discussion_list_exposes_unread_state_and_mark_all_read(self):
        discussion = DiscussionService.create_discussion(
            title="Unread tracking",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        PostService.create_post(
            discussion_id=discussion.id,
            content="A new reply",
            user=self.author,
        )

        response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        discussion_payload = response.json()["data"][0]
        self.assertTrue(discussion_payload["is_unread"])
        self.assertEqual(discussion_payload["unread_count"], 1)

        response = self.client.post(
            "/api/discussions/read-all",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        discussion_payload = response.json()["data"][0]
        self.assertFalse(discussion_payload["is_unread"])
        self.assertEqual(discussion_payload["unread_count"], 0)

    def test_discussion_detail_does_not_mark_everything_read_immediately(self):
        discussion = DiscussionService.create_discussion(
            title="Unread detail",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply one",
            user=self.author,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply two",
            user=self.author,
        )

        response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["last_read_post_number"], 1)
        self.assertEqual(payload["unread_count"], 2)
        self.assertTrue(payload["is_unread"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "discussion-view-count-test"}})
    def test_discussion_detail_throttles_view_count_per_viewer(self):
        cache.clear()
        discussion = DiscussionService.create_discussion(
            title="View count throttle",
            content="Initial post",
            user=self.author,
        )

        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)

        discussion.refresh_from_db()
        self.assertEqual(discussion.view_count, 1)

        DiscussionService.get_discussion_by_id(discussion.id, self.author)
        discussion.refresh_from_db()
        self.assertEqual(discussion.view_count, 2)

    def test_update_discussion_read_state_advances_progress(self):
        discussion = DiscussionService.create_discussion(
            title="Read state update",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply one",
            user=self.author,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply two",
            user=self.author,
        )

        response = self.client.post(
            f"/api/discussions/{discussion.id}/read",
            data=json.dumps({
                "last_read_post_number": 2,
            }),
            content_type="application/json",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["last_read_post_number"], 2)

        response = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["last_read_post_number"], 2)
        self.assertEqual(payload["unread_count"], 1)

    def test_discussion_list_filters_by_tag_slug(self):
        life_tag = Tag.objects.create(name="生活", slug="life", color="#4d698e")
        tech_tag = Tag.objects.create(name="技术", slug="tech", color="#3498db")

        life_discussion = DiscussionService.create_discussion(
            title="Life discussion",
            content="Only belongs to life.",
            user=self.author,
            tag_ids=[life_tag.id],
        )
        DiscussionService.create_discussion(
            title="Tech discussion",
            content="Only belongs to tech.",
            user=self.author,
            tag_ids=[tech_tag.id],
        )

        response = self.client.get("/api/discussions/", {"tag": life_tag.slug})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["id"], life_discussion.id)
        self.assertEqual(payload["data"][0]["tags"][0]["slug"], life_tag.slug)

    def test_suspended_user_cannot_create_discussion(self):
        self.author.suspended_until = timezone.now() + timedelta(days=1)
        self.author.suspend_message = "封禁期间不可发帖"
        self.author.save(update_fields=["suspended_until", "suspend_message"])

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Should fail",
                "content": "Blocked content",
                "tag_ids": [],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("账号已被封禁", response.json()["error"])
        self.assertIn("封禁期间不可发帖", response.json()["error"])

    def test_unverified_user_cannot_create_discussion(self):
        self.author.is_email_confirmed = False
        self.author.save(update_fields=["is_email_confirmed"])

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Should fail",
                "content": "Blocked until email verification",
                "tag_ids": [],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "请先完成邮箱验证后再发布讨论")

    def test_cannot_create_discussion_without_start_discussion_permission(self):
        restricted_group = Group.objects.create(name="ReadOnlyDiscussionMember", color="#95a5a6")
        self.author.user_groups.add(restricted_group)

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Should fail",
                "content": "Blocked by forum permission",
                "tag_ids": [],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限发起讨论")

    def test_discussion_can_enter_approval_queue(self):
        trusted_group = Group.objects.create(name="Trusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Pending discussion",
                "content": "Needs approval",
                "tag_ids": [],
            }),
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
            data=json.dumps({
                "title": "Rejected discussion updated",
                "content": "Updated context for approval",
                "tag_ids": [],
            }),
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
            data=json.dumps({
                "title": "Pending discussion to approve",
                "content": "Needs approval first",
                "tag_ids": [],
            }),
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

        list_response = self.client.get(
            "/api/discussions/",
            **self.auth_header(self.reader),
        )
        self.assertEqual(list_response.status_code, 200, list_response.content)
        self.assertTrue(any(item["id"] == discussion.id for item in list_response.json()["data"]))

    def test_discussion_list_hides_staff_only_tag_for_non_staff(self):
        staff_tag = Tag.objects.create(
            name="Staff",
            slug="staff-zone",
            view_scope=Tag.ACCESS_STAFF,
            start_discussion_scope=Tag.ACCESS_STAFF,
            reply_scope=Tag.ACCESS_STAFF,
        )
        admin = User.objects.create_superuser(
            username="discussion-admin",
            email="discussion-admin@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="仅管理员可见",
            content="内部讨论",
            user=admin,
            tag_ids=[staff_tag.id],
        )

        guest_response = self.client.get("/api/discussions/")
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        self.assertEqual(guest_response.json()["total"], 0)

        member_response = self.client.get("/api/discussions/", **self.auth_header(self.reader))
        self.assertEqual(member_response.status_code, 200, member_response.content)
        self.assertEqual(member_response.json()["total"], 0)

        admin_response = self.client.get("/api/discussions/", **self.auth_header(admin))
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertEqual(admin_response.json()["total"], 1)
        self.assertEqual(admin_response.json()["data"][0]["id"], discussion.id)

    def test_cannot_create_discussion_in_staff_only_tag(self):
        restricted_tag = Tag.objects.create(
            name="管理员专用",
            slug="staff-only-start",
            view_scope=Tag.ACCESS_PUBLIC,
            start_discussion_scope=Tag.ACCESS_STAFF,
            reply_scope=Tag.ACCESS_PUBLIC,
        )

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Should fail",
                "content": "Blocked by tag scope",
                "tag_ids": [restricted_tag.id],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("没有权限", response.json()["error"])

    def test_admin_can_hide_and_restore_discussion(self):
        admin = User.objects.create_superuser(
            username="hide-discussion-admin",
            email="hide-discussion-admin@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="隐藏测试讨论",
            content="用于验证隐藏接口",
            user=self.author,
        )

        hide_response = self.client.post(
            f"/api/discussions/{discussion.id}/hide",
            **self.auth_header(admin),
        )
        self.assertEqual(hide_response.status_code, 200, hide_response.content)

        discussion.refresh_from_db()
        self.assertTrue(discussion.is_hidden)
        self.assertEqual(discussion.hidden_user_id, admin.id)

        guest_detail = self.client.get(f"/api/discussions/{discussion.id}")
        self.assertEqual(guest_detail.status_code, 404, guest_detail.content)

        restore_response = self.client.post(
            f"/api/discussions/{discussion.id}/hide",
            **self.auth_header(admin),
        )
        self.assertEqual(restore_response.status_code, 200, restore_response.content)

        discussion.refresh_from_db()
        self.assertFalse(discussion.is_hidden)
        self.assertIsNone(discussion.hidden_user_id)

        guest_detail = self.client.get(f"/api/discussions/{discussion.id}")
        self.assertEqual(guest_detail.status_code, 200, guest_detail.content)

    def test_owner_without_edit_own_permission_cannot_edit_discussion(self):
        member_group = Group.objects.create(name="DiscussionAuthorNoEdit", color="#4d698e")
        Permission.objects.create(group=member_group, permission="startDiscussion")
        self.author.user_groups.add(member_group)

        discussion = DiscussionService.create_discussion(
            title="Original title",
            content="Original content",
            user=self.author,
        )

        response = self.client.patch(
            f"/api/discussions/{discussion.id}",
            data=json.dumps({
                "title": "Updated title",
                "content": "Updated content",
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限编辑此讨论")

    def test_owner_with_delete_own_permission_can_delete_discussion(self):
        member_group = Group.objects.create(name="DiscussionAuthorDeleteOwn", color="#4d698e")
        Permission.objects.create(group=member_group, permission="startDiscussion")
        Permission.objects.create(group=member_group, permission="discussion.deleteOwn")
        self.author.user_groups.add(member_group)

        discussion = DiscussionService.create_discussion(
            title="Delete own discussion",
            content="Allowed by permission",
            user=self.author,
        )

        response = self.client.delete(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Discussion.objects.filter(id=discussion.id).exists())

    def test_user_with_global_edit_permission_can_edit_others_discussion(self):
        editor_group = Group.objects.create(name="DiscussionEditor", color="#4d698e")
        Permission.objects.create(group=editor_group, permission="discussion.edit")
        self.reader.user_groups.add(editor_group)

        discussion = DiscussionService.create_discussion(
            title="Original title",
            content="Original content",
            user=self.author,
        )

        response = self.client.patch(
            f"/api/discussions/{discussion.id}",
            data=json.dumps({
                "title": "Edited by moderator",
                "content": "Edited content",
            }),
            content_type="application/json",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["title"], "Edited by moderator")

    def test_delete_pending_discussion_does_not_decrement_author_discussion_count(self):
        admin = User.objects.create_superuser(
            username="delete-pending-discussion-admin",
            email="delete-pending-discussion-admin@example.com",
            password="password123",
        )
        trusted_group = Group.objects.create(name="DeletePendingDiscussionTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")
        pending_author = User.objects.create_user(
            username="pending-delete-author",
            email="pending-delete-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        discussion = DiscussionService.create_discussion(
            title="待删除讨论",
            content="待审核讨论不会计入作者讨论数",
            user=pending_author,
        )

        pending_author.refresh_from_db()
        self.assertEqual(pending_author.discussion_count, 0)

        DiscussionService.delete_discussion(discussion.id, admin)

        pending_author.refresh_from_db()
        self.assertEqual(pending_author.discussion_count, 0)

    def test_cannot_create_discussion_with_secondary_tag_only(self):
        parent_tag = Tag.objects.create(name="开发", slug="dev")
        child_tag = Tag.objects.create(name="后端", slug="backend", parent=parent_tag)

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Invalid child only",
                "content": "Blocked by tag combination",
                "tag_ids": [child_tag.id],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("次标签", response.json()["error"])

    def test_cannot_create_discussion_with_two_primary_tags(self):
        first_tag = Tag.objects.create(name="前端", slug="frontend")
        second_tag = Tag.objects.create(name="后端", slug="backend-main")

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Too many primary tags",
                "content": "Blocked by primary count",
                "tag_ids": [first_tag.id, second_tag.id],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("主标签", response.json()["error"])

    def test_cannot_create_discussion_with_mismatched_parent_child_tags(self):
        first_tag = Tag.objects.create(name="前端", slug="frontend-main")
        second_tag = Tag.objects.create(name="后端", slug="backend-main")
        child_tag = Tag.objects.create(name="Vue", slug="vue-child", parent=first_tag)

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps({
                "title": "Mismatched tags",
                "content": "Blocked by parent child mismatch",
                "tag_ids": [second_tag.id, child_tag.id],
            }),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("主标签", response.json()["error"])
