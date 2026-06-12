import json
from io import StringIO

from django.core.management import call_command
from django.db import OperationalError
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from ninja_jwt.tokens import RefreshToken
from types import SimpleNamespace
from unittest.mock import Mock, patch

from apps.core.forum_registry import get_forum_registry
from apps.core.extensions.runtime_access import (
    create_runtime_discussion,
    delete_runtime_discussion,
    get_runtime_discussion_model,
    get_runtime_discussion_state_model,
    set_runtime_discussion_hidden_state,
)
from apps.core.models import AuditLog
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceRegistry
from apps.core.search_index_service import get_search_index_definitions
from extensions.testing import ExtensionRuntimeTestMixin
from extensions.posts.backend.resources import resolve_post_event_data
from extensions.discussions.backend.visibility import (
    build_post_visibility_q,
    scope_discussion_view,
    scope_post_view,
)
from extensions.posts.backend.handlers import post_resource_endpoints
from extensions.posts.backend.models import Post
from extensions.posts.backend.services import PostService
from apps.core.extensions.runtime_access import (
    get_runtime_group_model,
    get_runtime_permission_model,
    get_runtime_user_model,
)


class RuntimeModelProxy:
    def __init__(self, resolver):
        self._resolver = resolver

    def __getattr__(self, name):
        return getattr(self._resolver(), name)


User = RuntimeModelProxy(get_runtime_user_model)
Group = RuntimeModelProxy(get_runtime_group_model)
Permission = RuntimeModelProxy(get_runtime_permission_model)
Discussion = RuntimeModelProxy(get_runtime_discussion_model)
DiscussionUser = RuntimeModelProxy(get_runtime_discussion_state_model)


class PostsExtensionDiagnosticsTests(ExtensionRuntimeTestMixin, TestCase):
    def test_posts_extension_registers_runtime_service_provider(self):
        application = self.bootstrap_extensions("posts")
        service = application.get_service("posts.service")

        self.assertIn("posts.service", application.get_service_provider_keys(extension_id="posts"))
        self.assertIs(service["model"], Post)
        self.assertEqual(service["approval_approved"], Post.APPROVAL_APPROVED)
        self.assertEqual(service["approval_pending"], Post.APPROVAL_PENDING)
        self.assertEqual(service["approval_rejected"], Post.APPROVAL_REJECTED)
        for key in (
            "can_view",
            "get_by_id",
            "create",
            "update",
            "delete",
            "set_hidden_state",
            "reply_notification_context",
            "notification_context",
            "get_number",
            "create_first_post",
            "get_first_post",
            "update_first_post_content",
            "resubmit_first_post",
            "approve_first_post",
            "reject_first_post",
            "approved_reply_counts_by_author",
            "approved_discussion_stats",
            "delete_discussion_posts",
            "serialize_by_id",
        ):
            self.assertTrue(callable(service[key]), key)

    def test_posts_capabilities_are_filtered_when_extension_disabled(self):
        self.disable_extension_for_test("posts")

        registry = get_forum_registry()

        self.assertFalse(registry.get_module("posts").enabled)
        self.assertFalse(any(item.module_id == "posts" for item in registry.get_post_types()))
        self.assertEqual(registry.get_default_post_type_code(), "")
        self.assertNotIn("comment", registry.get_stream_post_type_codes())
        self.assertNotIn("comment", registry.get_searchable_post_type_codes())

    def test_posts_extension_registers_reply_permission_codes(self):
        application = self.bootstrap_extensions("posts")
        permission_codes = {item.code for item in application.forum_registry.get_all_permissions()}

        self.assertIn("post.editOwn", permission_codes)
        self.assertIn("post.deleteOwn", permission_codes)
        self.assertIn("post.edit", permission_codes)
        self.assertIn("post.delete", permission_codes)

    def test_inspect_reports_posts_model_as_extension_owned(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "posts",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]

        self.assertEqual(extension["id"], "posts")
        self.assertEqual(audit["owned_model_count"], 1)
        self.assertEqual(audit["app_label_migration_required_count"], 0)
        self.assertEqual(extension["django_app_label"], "posts")
        self.assertEqual(audit["target_app_label"], "posts")
        self.assertEqual(audit["target_app_label_source"], "manifest")
        self.assertTrue(all(
            item["target_app_label"] == "posts"
            and item["target_app_label_source"] == "manifest"
            for item in audit["items"]
        ))
        self.assertIn("0001_initial.py", extension["migration_plan"]["pending_files"])
        self.assertIn("0005_transfer_extension_owned_models_state.py", extension["migration_plan"]["pending_files"])


class PostRegistryTests(TestCase):
    def test_posts_extension_registers_default_comment_post_type(self):
        registry = get_forum_registry()

        self.assertEqual(registry.get_default_post_type_code(), "comment")
        self.assertIn("comment", registry.get_stream_post_type_codes())
        self.assertIn("comment", registry.get_searchable_post_type_codes())
        self.assertIn("comment", registry.get_discussion_counted_post_type_codes())
        self.assertIn("comment", registry.get_user_counted_post_type_codes())

    def test_posts_extension_search_index_limits_to_searchable_post_types(self):
        definitions = get_search_index_definitions()
        post_index = next(definition for definition in definitions if definition["name"] == "posts_content_fts_idx")

        self.assertEqual(post_index["module_id"], "posts")
        self.assertIn("WHERE type IN ('comment')", post_index["create"])


class PostEventResourceTests(TestCase):
    def test_resolve_post_event_data_parses_post_hidden_payload(self):
        payload = resolve_post_event_data(
            SimpleNamespace(
                type="postHidden",
                content="state:hidden\ntarget_post_id:12\ntarget_post_number:5",
            ),
            {},
        )

        self.assertEqual(
            payload,
            {
                "kind": "postHidden",
                "is_hidden": True,
                "target_post_id": 12,
                "target_post_number": 5,
            },
        )


class PostPaginationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="poster",
            email="poster@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_get_page_for_near_post(self):
        discussion = create_runtime_discussion(
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

    def test_get_post_window_supports_near_before_after(self):
        discussion = create_runtime_discussion(
            title="Windowed pagination",
            content="First post",
            user=self.user,
        )

        for index in range(2, 46):
            PostService.create_post(
                discussion_id=discussion.id,
                content=f"Reply {index}",
                user=self.user,
            )

        near_window = PostService.get_post_window(
            discussion_id=discussion.id,
            near=21,
            limit=5,
            user=self.user,
        )
        self.assertEqual([post.number for post in near_window.posts], [21, 22, 23, 24, 25])
        self.assertEqual(near_window.current_start, 21)
        self.assertEqual(near_window.current_end, 25)
        self.assertTrue(near_window.has_previous)
        self.assertTrue(near_window.has_more)

        before_window = PostService.get_post_window(
            discussion_id=discussion.id,
            before=21,
            limit=5,
            user=self.user,
        )
        self.assertEqual([post.number for post in before_window.posts], [16, 17, 18, 19, 20])
        self.assertEqual(before_window.current_start, 16)
        self.assertEqual(before_window.current_end, 20)

        after_window = PostService.get_post_window(
            discussion_id=discussion.id,
            after=25,
            limit=5,
            user=self.user,
        )
        self.assertEqual([post.number for post in after_window.posts], [26, 27, 28, 29, 30])
        self.assertEqual(after_window.current_start, 26)
        self.assertEqual(after_window.current_end, 30)

    def test_create_post_retries_on_transient_sqlite_lock(self):
        discussion = create_runtime_discussion(
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
            with patch("extensions.posts.backend.services.Post.objects.create", side_effect=flaky_create):
                post = PostService.create_post(
                    discussion_id=discussion.id,
                    content="Retry reply",
                    user=self.user,
                )

        self.assertTrue(state["failed"])
        self.assertEqual(post.content, "Retry reply")

    def test_create_post_applies_runtime_private_checkers(self):
        discussion = create_runtime_discussion(
            title="Private reply discussion",
            content="First post",
            user=self.user,
        )

        class RuntimeModelService:
            def is_private(self, model, instance, *, default=False):
                return model is Post and getattr(instance, "number", 0) > 1

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=RuntimeModelService()):
            reply = PostService.create_post(
                discussion_id=discussion.id,
                content="Private reply",
                user=self.user,
            )

        self.assertTrue(reply.is_private)
        self.assertFalse(Post.objects.filter(build_post_visibility_q(self.user), id=reply.id).exists())

    def test_approve_post_refreshes_runtime_private_state(self):
        discussion = create_runtime_discussion(
            title="Private approved reply discussion",
            content="First post",
            user=self.user,
        )
        admin = User.objects.create_user(
            username="moderator",
            email="moderator@example.com",
            password="password123",
            is_staff=True,
            is_email_confirmed=True,
        )
        reply = PostService.create_post(
            discussion_id=discussion.id,
            content="Pending reply",
            user=self.user,
        )
        reply.approval_status = Post.APPROVAL_PENDING
        reply.is_private = False
        reply.save(update_fields=["approval_status", "is_private"])

        class RuntimeModelService:
            def is_private(self, model, instance, *, default=False):
                return model is Post and instance.id == reply.id

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=RuntimeModelService()):
            approved = PostService.approve_post(reply, admin)

        self.assertTrue(approved.is_private)

    def test_view_private_scoper_allows_matching_private_post_visibility(self):
        from apps.core.extensions.application import ExtensionApplication
        from apps.core.extensions.types import ExtensionModelVisibilityDefinition

        discussion_model = get_runtime_discussion_model()
        reader = User.objects.create_user(
            username="post-private-reader",
            email="post-private-reader@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        discussion = create_runtime_discussion(
            title="Scoped private posts",
            content="First post",
            user=self.user,
        )
        allowed = PostService.create_post(
            discussion_id=discussion.id,
            content="Scoped private allowed",
            user=self.user,
        )
        denied = PostService.create_post(
            discussion_id=discussion.id,
            content="Scoped private denied",
            user=self.user,
        )
        Post.objects.filter(id__in=[allowed.id, denied.id]).update(is_private=True)

        app = ExtensionApplication()
        app.models.register_visibility(
            "discussions",
            ExtensionModelVisibilityDefinition(
                model=discussion_model,
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
                scope=lambda queryset, context: queryset.filter(id=allowed.id),
            ),
        )

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=app.models):
            visible_ids = set(
                PostService.apply_visibility_filters(
                    Post.objects.filter(id__in=[allowed.id, denied.id]),
                    reader,
                ).values_list("id", flat=True)
            )

        self.assertIn(allowed.id, visible_ids)
        self.assertNotIn(denied.id, visible_ids)

    def test_hide_posts_scoper_allows_matching_hidden_post_visibility(self):
        from apps.core.extensions.application import ExtensionApplication
        from apps.core.extensions.types import ExtensionModelVisibilityDefinition

        discussion_model = get_runtime_discussion_model()
        reader = User.objects.create_user(
            username="post-hidden-reader",
            email="post-hidden-reader@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        allowed_discussion = create_runtime_discussion(
            title="Scoped hidden post allowed",
            content="First post",
            user=self.user,
        )
        denied_discussion = create_runtime_discussion(
            title="Scoped hidden post denied",
            content="First post",
            user=self.user,
        )
        allowed = PostService.create_post(
            discussion_id=allowed_discussion.id,
            content="Scoped hidden allowed",
            user=self.user,
        )
        denied = PostService.create_post(
            discussion_id=denied_discussion.id,
            content="Scoped hidden denied",
            user=self.user,
        )
        Post.objects.filter(id__in=[allowed.id, denied.id]).update(hidden_at=timezone.now())

        app = ExtensionApplication()
        app.models.register_visibility(
            "discussions",
            ExtensionModelVisibilityDefinition(
                model=discussion_model,
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
            "hidden-runtime",
            ExtensionModelVisibilityDefinition(
                model=discussion_model,
                ability="hidePosts",
                scope=lambda queryset, context: queryset.filter(id=allowed_discussion.id),
            ),
        )

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=app.models):
            visible_ids = set(
                PostService.apply_visibility_filters(
                    Post.objects.filter(id__in=[allowed.id, denied.id]),
                    reader,
                ).values_list("id", flat=True)
            )
            allowed.refresh_from_db()
            can_view_allowed = PostService._can_view_post(allowed, reader)

        self.assertIn(allowed.id, visible_ids)
        self.assertNotIn(denied.id, visible_ids)
        self.assertTrue(can_view_allowed)

    def test_own_reply_advances_read_state_without_auto_follow(self):
        self.user.preferences = {"follow_after_reply": False}
        self.user.save(update_fields=["preferences"])

        discussion = create_runtime_discussion(
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

    def test_create_post_locks_discussion_before_allocating_floor_number(self):
        discussion = create_runtime_discussion(
            title="Locked numbering discussion",
            content="First post",
            user=self.user,
        )

        with patch(
            "extensions.posts.backend.services.PostService._lock_discussion_for_post_number",
            wraps=PostService._lock_discussion_for_post_number,
        ) as lock_discussion_mock:
            PostService.create_post(
                discussion_id=discussion.id,
                content="Reply with lock",
                user=self.user,
            )

        self.assertTrue(lock_discussion_mock.called)

    def test_refresh_discussion_stats_recomputes_discussion_counters(self):
        discussion = create_runtime_discussion(
            title="Stats refresh discussion",
            content="First post",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="Reply for stats",
            user=self.user,
        )

        PostService._refresh_discussion_approved_stats(discussion)
        discussion.refresh_from_db()

        self.assertEqual(discussion.comment_count, 2)
        self.assertEqual(discussion.last_post_number, 2)

    def test_create_post_dispatches_created_event_after_commit(self):
        discussion = create_runtime_discussion(
            title="After commit post discussion",
            content="First post",
            user=self.user,
        )

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                post = PostService.create_post(
                    discussion_id=discussion.id,
                    content="Reply after commit",
                    user=self.user,
                )

        self.assertEqual(len(callbacks), 1)
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertEqual(event.post_id, post.id)


class PostApiTests(TestCase):
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
        self.discussion = create_runtime_discussion(
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

    def test_post_detail_renders_missing_content_html_from_content(self):
        self.post.content = "正文 **加粗**"
        self.post.content_html = ""
        self.post.save(update_fields=["content", "content_html"])

        response = self.client.get(f"/api/posts/{self.post.id}")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("正文", payload["content_html"])
        self.assertIn("<strong>加粗</strong>", payload["content_html"])

    def test_discussion_post_list_renders_missing_content_html_from_content(self):
        self.post.content = "列表正文"
        self.post.content_html = ""
        self.post.save(update_fields=["content", "content_html"])

        response = self.client.get(f"/api/discussions/{self.discussion.id}/posts")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        item = next(post for post in payload["data"] if post["id"] == self.post.id)
        self.assertIn("列表正文", item["content_html"])

    def test_post_detail_supports_resource_field_selection(self):
        response = self.client.get(
            f"/api/posts/{self.post.id}",
            {"fields[post]": "post_type"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("post_type", payload)
        self.assertNotIn("can_edit", payload)
        self.assertNotIn("open_flags", payload)

    def test_post_detail_supports_explicit_relationship_includes(self):
        response = self.client.get(
            f"/api/posts/{self.post.id}",
            {"include": "edited_user"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("edited_user", payload)

    def test_post_detail_static_route_uses_resource_endpoint_mutator(self):
        def mutate_endpoint(endpoint):
            def handler(context):
                payload = endpoint.handler(context)
                payload["mutated_by_resource_endpoint"] = True
                return payload

            return ResourceEndpointDefinition(
                resource=endpoint.resource,
                endpoint=endpoint.endpoint,
                module_id="test",
                handler=handler,
                methods=endpoint.methods,
            )

        registry = ResourceRegistry()
        for endpoint in post_resource_endpoints():
            registry.register_endpoint(endpoint)
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="post",
                endpoint="show",
                module_id="test",
                operation="mutate",
                mutator=mutate_endpoint,
            )
        )

        with patch("extensions.posts.backend.handlers.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                response = self.client.get(f"/api/posts/{self.post.id}")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["mutated_by_resource_endpoint"])

    def test_post_list_avoids_n_plus_one_for_registered_user_summary(self):
        for index in range(3):
            PostService.create_post(
                discussion_id=self.discussion.id,
                content=f"额外回复 {index}",
                user=self.author,
            )

        with CaptureQueriesContext(connection) as context:
            response = self.client.get(f"/api/discussions/{self.discussion.id}/posts")

        self.assertEqual(response.status_code, 200, response.content)
        select_group_queries = [
            query["sql"]
            for query in context.captured_queries
            if "user_groups" in query["sql"].lower()
        ]
        self.assertLessEqual(len(select_group_queries), 2)

    def test_discussion_posts_api_supports_windowed_queries(self):
        for index in range(3, 13):
            PostService.create_post(
                discussion_id=self.discussion.id,
                content=f"窗口回复 {index}",
                user=self.reporter,
            )

        near_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            {"near": 6, "limit": 4},
            **self.auth_header(),
        )
        self.assertEqual(near_response.status_code, 200, near_response.content)
        near_payload = near_response.json()
        self.assertEqual([item["number"] for item in near_payload["data"]], [6, 7, 8, 9])
        self.assertEqual(near_payload["current_start"], 6)
        self.assertEqual(near_payload["current_end"], 9)
        self.assertTrue(near_payload["has_previous"])
        self.assertTrue(near_payload["has_more"])

        before_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            {"before": 6, "limit": 3},
            **self.auth_header(),
        )
        self.assertEqual(before_response.status_code, 200, before_response.content)
        self.assertEqual([item["number"] for item in before_response.json()["data"]], [3, 4, 5])

        after_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            {"after": 9, "limit": 3},
            **self.auth_header(),
        )
        self.assertEqual(after_response.status_code, 200, after_response.content)
        self.assertEqual([item["number"] for item in after_response.json()["data"]], [10, 11, 12])

    def test_suspended_user_cannot_reply(self):
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

        delete_runtime_discussion(self.discussion.id, self.admin)

        self.reporter.refresh_from_db()
        self.assertEqual(self.reporter.comment_count, 0)

    def test_hiding_post_creates_post_hidden_event_post_and_updates_counts(self):
        self.author.refresh_from_db()
        self.assertEqual(self.author.comment_count, 1)

        with self.captureOnCommitCallbacks(execute=True):
            hidden_post = PostService.set_hidden_state(self.post, self.admin, True)

        hidden_post.refresh_from_db()
        self.assertTrue(hidden_post.is_hidden)
        self.discussion.refresh_from_db()
        self.author.refresh_from_db()
        self.assertEqual(self.discussion.comment_count, 1)
        self.assertEqual(self.author.comment_count, 0)

        posts_response = self.client.get(
            f"/api/discussions/{self.discussion.id}/posts",
            **self.admin_auth_header(),
        )
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        event_post = next(item for item in posts_response.json()["data"] if item["type"] == "postHidden")
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "postHidden",
                "is_hidden": True,
                "target_post_id": self.post.id,
                "target_post_number": self.post.number,
            },
        )

        PostService.set_hidden_state(self.post, self.admin, False)
        self.discussion.refresh_from_db()
        self.author.refresh_from_db()
        self.assertEqual(self.discussion.comment_count, 2)
        self.assertEqual(self.author.comment_count, 1)

    def test_post_hide_endpoint_toggles_hidden_state_for_admin(self):
        response = self.client.post(
            f"/api/posts/{self.post.id}/hide",
            **self.admin_auth_header(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["is_hidden"])

        self.post.refresh_from_db()
        self.assertTrue(self.post.is_hidden)

        response = self.client.post(
            f"/api/posts/{self.post.id}/hide",
            **self.admin_auth_header(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(response.json()["is_hidden"])

    def test_non_staff_cannot_hide_post(self):
        response = self.client.post(
            f"/api/posts/{self.post.id}/hide",
            **self.auth_header(),
        )
        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("只有管理员", response.json()["error"])

    def test_hiding_post_writes_admin_audit_log(self):
        response = self.client.post(
            f"/api/posts/{self.post.id}/hide",
            **self.admin_auth_header(),
        )
        self.assertEqual(response.status_code, 200, response.content)

        audit_log = AuditLog.objects.get(action="admin.post.hide", target_id=self.post.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "post")
        self.assertEqual(audit_log.data["discussion_id"], self.discussion.id)
        self.assertEqual(audit_log.data["number"], self.post.number)
        self.assertTrue(audit_log.data["is_hidden"])

        response = self.client.post(
            f"/api/posts/{self.post.id}/hide",
            **self.admin_auth_header(),
        )
        self.assertEqual(response.status_code, 200, response.content)

        restore_log = AuditLog.objects.get(action="admin.post.restore", target_id=self.post.id)
        self.assertEqual(restore_log.user_id, self.admin.id)
        self.assertFalse(restore_log.data["is_hidden"])

    def test_all_posts_list_respects_hidden_discussion_visibility(self):
        set_runtime_discussion_hidden_state(self.discussion, self.admin, True)

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
        Permission.objects.create(group=member_group, permission="post.deleteOwn")
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

    def test_legacy_discussion_delete_own_permission_can_delete_reply(self):
        member_group = Group.objects.create(name="ReplyAuthorLegacyDeleteOwn", color="#4d698e")
        Permission.objects.create(group=member_group, permission="discussion.reply")
        Permission.objects.create(group=member_group, permission="discussion.deleteOwn")
        self.reporter.user_groups.add(member_group)

        reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="旧权限仍允许删除自己的回复",
            user=self.reporter,
        )

        response = self.client.delete(
            f"/api/posts/{reply.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Post.objects.filter(id=reply.id).exists())

    def test_owner_with_edit_own_permission_can_edit_reply(self):
        member_group = Group.objects.create(name="ReplyAuthorEditOwn", color="#4d698e")
        Permission.objects.create(group=member_group, permission="discussion.reply")
        Permission.objects.create(group=member_group, permission="post.editOwn")
        self.reporter.user_groups.add(member_group)

        reply = PostService.create_post(
            discussion_id=self.discussion.id,
            content="允许编辑自己的回复",
            user=self.reporter,
        )

        response = self.client.patch(
            f"/api/posts/{reply.id}",
            data='{"content":"已经修改"}',
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        reply.refresh_from_db()
        self.assertEqual(reply.content, "已经修改")

    def test_user_with_global_delete_permission_can_delete_others_reply(self):
        moderator = User.objects.create_user(
            username="reply-moderator",
            email="reply-moderator@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        moderator_group = Group.objects.create(name="ReplyDeleteModerator", color="#4d698e")
        Permission.objects.create(group=moderator_group, permission="post.delete")
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


