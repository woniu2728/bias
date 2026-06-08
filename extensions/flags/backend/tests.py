import json
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken

from apps.core.forum_events import PostFlagCreatedEvent, PostFlagsDeletedEvent
from apps.core.models import AuditLog, Setting
from apps.core.settings_service import clear_runtime_setting_caches
from extensions.discussions.backend.models import Discussion
from extensions.discussions.backend.services import DiscussionService
from extensions.discussions.backend.visibility import scope_discussion_view, scope_post_view
from extensions.posts.backend.models import Post
from extensions.posts.backend.services import PostService
from extensions.users.backend.models import Group, Permission, User
from extensions.flags.backend.models import PostFlag
from extensions.flags.backend.services import report_post


class FlagsExtensionTests(TestCase):
    def setUp(self):
        clear_runtime_setting_caches()
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

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def auth_header_for(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def auth_header(self):
        return self.auth_header_for(self.reporter)

    def admin_auth_header(self):
        return self.auth_header_for(self.admin)

    def test_extension_detail_api_surfaces_registered_capabilities_for_flags_extension(self):
        response = self.client.get(
            "/api/admin/extensions/flags",
            **self.admin_auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertTrue(
            any(
                permission["name"] == "admin.flag.view"
                for section in payload["permission_sections"]
                for permission in section["permissions"]
            )
        )
        self.assertTrue(
            any(item["module_id"] == "flags" and item["path"] == "/admin/flags" for item in payload["admin_page_details"])
        )
        self.assertTrue(any(item["key"] == "guidelines_url" for item in payload["settings_schema"]))
        self.assertTrue(any(item["key"] == "can_flag_own" for item in payload["settings_schema"]))
        self.assertTrue(
            any(item["module_id"] == "flags" and item["field"] == "can_flag" for item in payload["resource_fields"])
        )
        self.assertTrue(
            any(item["module_id"] == "flags" and item["field"] == "open_flags" for item in payload["resource_fields"])
        )
        self.assertTrue(
            any(item["module_id"] == "flags" and item["field"] == "new_flag_count" for item in payload["resource_fields"])
        )
        self.assertTrue(any(item["module_id"] == "flags" and item["resource"] == "flag" for item in payload["resource_definitions"]))
        self.assertTrue(
            any(
                item["module_id"] == "flags"
                and item["resource"] == "post"
                and item["relationship"] == "flags"
                for item in payload["resource_relationships"]
            )
        )
        self.assertTrue(
            any(
                item["model"] == "PostFlag"
                and item["ability"] == "view"
                for item in payload["model_visibility"]
            )
        )
        self.assertTrue(
            any(item["module_id"] == "flags" and item["endpoint"] == "report" for item in payload["resource_endpoints"])
        )
        self.assertTrue(
            any(item["module_id"] == "flags" and item["endpoint"] == "flags/resolve" for item in payload["resource_endpoints"])
        )
        self.assertTrue(
            any(item["module_id"] == "flags" and item["endpoint"] == "flags/delete" for item in payload["resource_endpoints"])
        )
        self.assertTrue(
            any(
                item["module_id"] == "flags"
                and item["resource"] == "flag"
                and item["endpoint"] == "create"
                for item in payload["resource_endpoints"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "flags"
                and item["resource"] == "flag"
                and item["endpoint"] == "index"
                for item in payload["resource_endpoints"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "flags"
                and item["event"] == "PostFlagCreatedEvent"
                and item.get("source") == "runtime"
                for item in payload["event_listeners"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "flags"
                and item["event"] == "PostFlagsDeletedEvent"
                and item.get("source") == "runtime"
                for item in payload["event_listeners"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "flags"
                and item["key"] == "flags"
                and "prepare_delete" in item["phases"]
                and item.get("source") == "runtime"
                for item in payload["post_lifecycle"]
            )
        )

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

    def test_flag_resource_create_creates_flag_via_jsonapi(self):
        payload = {
            "data": {
                "type": "flag",
                "attributes": {
                    "reason": "违规内容",
                    "reason_detail": "JSON:API 举报",
                },
                "relationships": {
                    "post": {
                        "data": {
                            "type": "post",
                            "id": str(self.post.id),
                        },
                    },
                },
            },
        }

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                response = self.client.post(
                    "/api/resources/flag/create",
                    data=payload,
                    content_type="application/json",
                    **self.auth_header(),
                )

        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(len(callbacks), 1)
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertIsInstance(event, PostFlagCreatedEvent)
        self.assertEqual(PostFlag.objects.count(), 1)

        flag = PostFlag.objects.get(post=self.post, user=self.reporter)
        self.assertEqual(flag.reason, "违规内容")
        self.assertEqual(flag.message, "JSON:API 举报")

        data = response.json()["data"]
        self.assertEqual(data["type"], "flag")
        self.assertEqual(data["id"], str(flag.id))
        self.assertEqual(data["attributes"]["reason"], "违规内容")
        self.assertEqual(data["attributes"]["reason_detail"], "JSON:API 举报")
        self.assertEqual(data["relationships"]["post"]["data"], {"type": "post", "id": str(self.post.id)})
        self.assertEqual(data["relationships"]["user"]["data"], {"type": "user_summary", "id": str(self.reporter.id)})

    def test_public_forum_settings_expose_flags_forum_resource_fields_for_staff(self):
        PostFlag.objects.create(
            post=self.post,
            user=self.reporter,
            reason="spam",
            message="flag count",
        )

        guest_response = self.client.get("/api/forum")
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        guest_payload = guest_response.json()
        flags_extension = next(item for item in guest_payload["enabled_extensions"] if item["id"] == "flags")
        self.assertEqual(flags_extension["frontend_forum_entry"], "extensions/flags/frontend/forum/index.js")
        self.assertFalse(guest_payload["can_view_flags"])
        self.assertNotIn("flag_count", guest_payload)

        staff_response = self.client.get("/api/forum", **self.admin_auth_header())
        self.assertEqual(staff_response.status_code, 200, staff_response.content)
        payload = staff_response.json()
        self.assertTrue(payload["can_view_flags"])
        self.assertEqual(payload["flag_count"], 1)

    def test_flag_resource_index_lists_latest_visible_open_flags_for_staff(self):
        report_post(
            self.post.id,
            self.reporter,
            reason="第一次举报",
            message="应被后续同帖举报折叠",
        )
        second_reporter = User.objects.create_user(
            username="second-reporter",
            email="second-reporter@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        latest_flag = report_post(
            self.post.id,
            second_reporter,
            reason="第二次举报",
            message="同帖最新举报",
        )

        response = self.client.get(
            "/api/resources/flag/index",
            **self.admin_auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["meta"]["total"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["id"], str(latest_flag.id))
        self.assertEqual(payload["data"][0]["attributes"]["reason"], "第二次举报")
        self.assertEqual(payload["data"][0]["relationships"]["post"]["data"], {"type": "post", "id": str(self.post.id)})
        self.assertEqual(payload["data"][0]["relationships"]["user"]["data"], {"type": "user_summary", "id": str(second_reporter.id)})

        reporter_response = self.client.get(
            "/api/resources/flag/index",
            **self.auth_header(),
        )
        self.assertEqual(reporter_response.status_code, 200, reporter_response.content)
        self.assertEqual(reporter_response.json()["data"], [])

    def test_flag_visibility_uses_post_view_private_scoper(self):
        from apps.core.extensions.application import ExtensionApplication
        from apps.core.extensions.types import ExtensionModelVisibilityDefinition
        from extensions.flags.backend.resources import scope_flag_visibility

        allowed_flag = report_post(
            self.post.id,
            self.reporter,
            reason="允许查看的私有帖举报",
            message="允许查看",
        )
        denied_post = PostService.create_post(
            discussion_id=self.discussion.id,
            content="另一个私有帖",
            user=self.author,
        )
        second_reporter = User.objects.create_user(
            username="private-flag-reporter",
            email="private-flag-reporter@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        denied_flag = report_post(
            denied_post.id,
            second_reporter,
            reason="不允许查看的私有帖举报",
            message="不允许查看",
        )
        viewer = User.objects.create_user(
            username="private-flag-viewer",
            email="private-flag-viewer@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        flag_group = Group.objects.create(name="PrivateFlagViewer", color="#4d698e")
        Permission.objects.create(group=flag_group, permission="admin.flag.view")
        viewer.user_groups.add(flag_group)
        Post.objects.filter(id__in=[self.post.id, denied_post.id]).update(is_private=True)

        app = ExtensionApplication()
        app.models.register_visibility(
            "discussions",
            ExtensionModelVisibilityDefinition(
                model=Discussion,
                ability="view",
                scope=scope_discussion_view,
            ),
        )
        app.models.register_visibility(
            "discussions",
            ExtensionModelVisibilityDefinition(
                model=Post,
                ability="view",
                scope=scope_post_view,
            ),
        )
        app.models.register_visibility(
            "private-runtime",
            ExtensionModelVisibilityDefinition(
                model=Post,
                ability="viewPrivate",
                scope=lambda queryset, context: queryset.filter(id=self.post.id),
            ),
        )

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=app.models):
            visible_flag_ids = set(
                scope_flag_visibility(
                    PostFlag.objects.filter(id__in=[allowed_flag.id, denied_flag.id]),
                    {"user": viewer},
                ).values_list("id", flat=True)
            )

        self.assertIn(allowed_flag.id, visible_flag_ids)
        self.assertNotIn(denied_flag.id, visible_flag_ids)

    def test_flags_extension_adds_flags_to_post_default_includes_for_staff(self):
        flag = PostFlag.objects.create(
            post=self.post,
            user=self.reporter,
            reason="默认 include",
            message="Bias flags include",
        )

        detail_response = self.client.get(
            f"/api/posts/{self.post.id}",
            **self.admin_auth_header(),
        )
        self.assertEqual(detail_response.status_code, 200, detail_response.content)
        detail_payload = detail_response.json()
        self.assertEqual(detail_payload["flags"], [{"type": "flag", "id": str(flag.id)}])

        list_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.admin_auth_header(),
        )
        self.assertEqual(list_response.status_code, 200, list_response.content)
        target = next(item for item in list_response.json()["data"] if item["id"] == self.post.id)
        self.assertEqual(target["flags"], [{"type": "flag", "id": str(flag.id)}])

        reporter_response = self.client.get(
            f"/api/posts/{self.post.id}",
            **self.auth_header(),
        )
        self.assertEqual(reporter_response.status_code, 200, reporter_response.content)
        self.assertNotIn("flags", reporter_response.json())

    def test_staff_can_delete_post_flags_through_flags_extension_endpoint(self):
        first = PostFlag.objects.create(
            post=self.post,
            user=self.reporter,
            reason="第一条",
            message="待删除",
        )
        second_reporter = User.objects.create_user(
            username="delete-flags-reporter",
            email="delete-flags-reporter@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        second = PostFlag.objects.create(
            post=self.post,
            user=second_reporter,
            reason="第二条",
            message="待删除",
        )

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                response = self.client.delete(
                    f"/api/posts/{self.post.id}/flags",
                    **self.admin_auth_header(),
                )

        self.assertEqual(response.status_code, 204, response.content)
        self.assertEqual(len(callbacks), 1)
        self.assertFalse(PostFlag.objects.filter(post=self.post).exists())
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertIsInstance(event, PostFlagsDeletedEvent)
        self.assertEqual(set(event.flag_ids), {first.id, second.id})
        self.assertEqual(event.post_id, self.post.id)

    def test_deleting_post_cleans_flags_through_flags_post_lifecycle(self):
        first = PostFlag.objects.create(
            post=self.post,
            user=self.reporter,
            reason="第一条",
            message="随帖子删除",
        )
        second_reporter = User.objects.create_user(
            username="delete-post-flag-reporter",
            email="delete-post-flag-reporter@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        second = PostFlag.objects.create(
            post=self.post,
            user=second_reporter,
            reason="第二条",
            message="随帖子删除",
        )

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True):
                deleted = PostService.delete_post(self.post.id, self.admin)

        self.assertTrue(deleted)
        self.assertFalse(PostFlag.objects.filter(post_id=self.post.id).exists())
        dispatched_events = [call.args[0] for call in mocked_bus.dispatch.call_args_list]
        flags_deleted_event = next(
            event for event in dispatched_events if isinstance(event, PostFlagsDeletedEvent)
        )
        self.assertEqual(set(flags_deleted_event.flag_ids), {first.id, second.id})
        self.assertEqual(flags_deleted_event.post_id, self.post.id)

    def test_non_staff_cannot_delete_post_flags_through_flags_extension_endpoint(self):
        PostFlag.objects.create(
            post=self.post,
            user=self.reporter,
            reason="越权删除",
            message="应保留",
        )

        response = self.client.delete(
            f"/api/posts/{self.post.id}/flags",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(PostFlag.objects.filter(post=self.post).count(), 1)

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
        self.assertTrue(target["can_flag"])

    def test_author_can_flag_post_when_flags_extension_setting_allows_it(self):
        denied_response = self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"补充说明","message":"作者默认不能举报自己"}',
            content_type="application/json",
            **self.auth_header_for(self.author),
        )
        self.assertEqual(denied_response.status_code, 400, denied_response.content)

        Setting.objects.update_or_create(
            key="extensions.flags.can_flag_own",
            defaults={"value": "true"},
        )

        response = self.client.get(
            f"/api/posts/{self.post.id}",
            **self.auth_header_for(self.author),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["can_flag"])

        report_response = self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"补充说明","message":"设置允许作者举报自己"}',
            content_type="application/json",
            **self.auth_header_for(self.author),
        )
        self.assertEqual(report_response.status_code, 200, report_response.content)
        self.assertEqual(report_response.json()["user"]["id"], self.author.id)

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
        self.assertEqual(len(target["flags"]), 1)
        self.assertTrue(target["can_moderate_flags"])

        me_response = self.client.get("/api/users/me", **self.admin_auth_header())
        self.assertEqual(me_response.status_code, 200, me_response.content)
        self.assertEqual(me_response.json()["new_flag_count"], 1)

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
        self.assertEqual(response.json()["message"], response.json()["error"])
        self.assertEqual(response.json()["code"], "forbidden")

    def test_suspended_user_cannot_report_post(self):
        self.reporter.suspended_until = timezone.now() + timedelta(days=2)
        self.reporter.suspend_message = "封禁期间不可互动"
        self.reporter.save(update_fields=["suspended_until", "suspend_message"])

        response = self.client.post(
            f"/api/posts/{self.post.id}/report",
            data='{"reason":"违规内容","message":"尝试举报"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("封禁期间不可互动", response.json()["error"])


class AdminFlagManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-flag-mgr",
            email="admin-flag-mgr@example.com",
            password="password123",
        )
        self.author = User.objects.create_user(
            username="flag-author",
            email="flag-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.reporter = User.objects.create_user(
            username="flag-reporter",
            email="flag-reporter@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        discussion = DiscussionService.create_discussion(
            title="Flag target",
            content="First",
            user=self.author,
        )
        post = PostService.create_post(
            discussion_id=discussion.id,
            content="这是一条被举报的帖子",
            user=self.author,
        )
        self.flag = PostFlag.objects.create(
            post=post,
            user=self.reporter,
            reason="违规内容",
            message="请管理员处理",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_list_and_resolve_flags(self):
        response = self.client.get(
            "/api/admin/flags",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["total"], 1)
        self.assertEqual(response.json()["data"][0]["reason"], "违规内容")

        response = self.client.post(
            f"/api/admin/flags/{self.flag.id}/resolve",
            data=json.dumps({
                "status": "resolved",
                "resolution_note": "已联系发帖人并隐藏内容",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.flag.refresh_from_db()
        self.assertEqual(self.flag.status, "resolved")
        self.assertEqual(self.flag.resolution_note, "已联系发帖人并隐藏内容")
        self.assertEqual(self.flag.resolved_by_id, self.admin.id)
        audit_log = AuditLog.objects.get(action="admin.flag.resolve", target_id=self.flag.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "post_flag")
        self.assertEqual(audit_log.data["status"], "resolved")

    def test_admin_without_flag_permission_is_denied(self):
        with patch("extensions.flags.backend.admin_api.UserService.has_forum_permission", return_value=False):
            list_response = self.client.get(
                "/api/admin/flags",
                **self.auth_header(),
            )
            self.assertEqual(list_response.status_code, 403, list_response.content)

            resolve_response = self.client.post(
                f"/api/admin/flags/{self.flag.id}/resolve",
                data=json.dumps({
                    "status": "resolved",
                    "resolution_note": "尝试越权处理举报",
                }),
                content_type="application/json",
                **self.auth_header(),
            )
            self.assertEqual(resolve_response.status_code, 403, resolve_response.content)
