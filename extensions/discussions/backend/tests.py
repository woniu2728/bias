import json
from dataclasses import replace
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, Client
from django.test import override_settings
from django.db import OperationalError
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from datetime import timedelta
from io import StringIO
from ninja_jwt.tokens import RefreshToken

from apps.core.forum_registry import get_forum_registry
from apps.core.models import AuditLog
from apps.core.resource_registry import (
    ResourceEndpointDefinition,
    ResourceRelationshipDefinition,
    ResourceRegistry,
    ResourceSortDefinition,
)
from extensions.testing import ExtensionRuntimeTestMixin
from extensions.discussions.backend.visibility import (
    build_discussion_visibility_q,
    build_post_visibility_q,
    scope_discussion_view,
)
from extensions.discussions.backend.handlers import discussion_resource_endpoints
from extensions.discussions.backend.models import Discussion, DiscussionUser
from extensions.discussions.backend.schemas import DiscussionCreateSchema, DiscussionUpdateSchema
from extensions.discussions.backend.services import DiscussionService
from apps.core.extensions.runtime_access import (
    create_runtime_post,
    get_runtime_post_model,
)
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
Post = RuntimeModelProxy(get_runtime_post_model)


class DiscussionRegistryTests(ExtensionRuntimeTestMixin, TestCase):
    def test_discussions_extension_registers_runtime_service_providers(self):
        application = self.bootstrap_extensions("discussions")
        service = application.get_service("discussions.service")
        timeline_service = application.get_service("discussions.timeline")

        self.assertIn("discussions.service", application.get_service_provider_keys(extension_id="discussions"))
        self.assertIn("discussions.timeline", application.get_service_provider_keys(extension_id="discussions"))
        self.assertIs(service["model"], Discussion)
        self.assertIs(service["state_model"], DiscussionUser)
        self.assertEqual(service["approval_approved"], Discussion.APPROVAL_APPROVED)
        for key in (
            "create",
            "update",
            "delete",
            "set_hidden_state",
            "list",
            "approve",
            "reply_notification_context",
            "validate_replyable",
            "lock_for_post_number",
            "apply_counted_filter",
            "refresh_approved_stats",
            "is_subscribed",
            "set_subscription",
            "follow_if_enabled",
            "mark_read",
        ):
            self.assertTrue(callable(service[key]), key)
        self.assertTrue(callable(timeline_service["create_from_builder"]))

    def test_discussions_capabilities_are_filtered_when_extension_disabled(self):
        self.disable_extension_for_test("discussions")

        registry = get_forum_registry()

        self.assertFalse(registry.get_module("discussions").enabled)
        self.assertNotIn("viewForum", registry.get_valid_permission_codes())
        self.assertNotIn("startDiscussion", registry.get_valid_permission_codes())
        self.assertNotIn("discussion.reply", registry.get_valid_permission_codes())
        self.assertNotIn("discussion.edit", registry.get_valid_permission_codes())
        self.assertFalse(any(item.module_id == "discussions" for item in registry.get_post_types()))
        self.assertFalse(any(item.module_id == "discussions" for item in registry.get_discussion_sorts()))
        self.assertFalse(any(item.module_id == "discussions" for item in registry.get_discussion_list_filters()))

    def test_extension_detail_api_surfaces_discussion_frontend_routes(self):
        admin = User.objects.create_superuser(
            username="discussion-detail-admin",
            email="discussion-detail-admin@example.com",
            password="password123",
        )
        token = RefreshToken.for_user(admin).access_token
        response = self.client.get(
            "/api/admin/extensions/discussions",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["id"], "discussions")
        self.assertEqual(payload["source"], "filesystem")
        self.assertEqual(payload["frontend_admin_entry"], "extensions/discussions/frontend/admin/index.js")
        self.assertEqual(payload["frontend_forum_entry"], "extensions/discussions/frontend/forum/index.js")
        self.assertIn("/admin/extensions/discussions/permissions", payload["permissions_pages"])
        frontend_routes = {
            item["name"]: item
            for item in payload["frontend_routes"]
            if item["frontend"] == "forum"
        }
        self.assertEqual(frontend_routes["home"]["path"], "/")
        self.assertEqual(frontend_routes["home"]["component"], "./DiscussionListView.vue")
        self.assertEqual(frontend_routes["home"]["module_id"], "discussions")
        self.assertEqual(frontend_routes["home"]["order"], 0)
        self.assertEqual(frontend_routes["discussion-detail"]["path"], "/d/:id")
        self.assertEqual(frontend_routes["discussion-detail"]["component"], "./DiscussionDetailView.vue")
        self.assertEqual(frontend_routes["discussion-create"]["path"], "/discussions/create")
        self.assertEqual(frontend_routes["discussion-create"]["component"], "./DiscussionCreateView.vue")
        self.assertTrue(frontend_routes["discussion-create"]["requires_auth"])

    def test_inspect_reports_discussions_models_as_extension_owned(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "discussions",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]

        self.assertEqual(extension["id"], "discussions")
        self.assertEqual(audit["owned_model_count"], 2)
        self.assertEqual(audit["app_label_migration_required_count"], 0)
        self.assertEqual(extension["django_app_label"], "discussions")
        self.assertEqual(audit["target_app_label"], "discussions")
        self.assertEqual(audit["target_app_label_source"], "manifest")
        self.assertTrue(all(
            item["target_app_label"] == "discussions"
            and item["target_app_label_source"] == "manifest"
            for item in audit["items"]
        ))
        self.assertIn("0001_record_model_ownership.py", extension["migration_plan"]["pending_files"])

    def test_discussions_extension_registers_discussion_sort_catalog(self):
        registry = get_forum_registry()

        sorts = registry.get_discussion_sorts()
        sort_codes = [item.code for item in sorts]
        self.assertIn("latest", sort_codes)
        self.assertIn("top", sort_codes)
        self.assertIn("unanswered", sort_codes)
        self.assertEqual(registry.get_default_discussion_sort_code(), "latest")
        newest_sort = next(item for item in sorts if item.code == "newest")
        unanswered_sort = next(item for item in sorts if item.code == "unanswered")
        oldest_sort = next(item for item in sorts if item.code == "oldest")
        self.assertEqual(newest_sort.module_id, "discussions")
        self.assertEqual(newest_sort.icon, "fas fa-file-alt")
        self.assertTrue(newest_sort.toolbar_visible)
        self.assertFalse(unanswered_sort.toolbar_visible)
        self.assertFalse(oldest_sort.toolbar_visible)

    def test_discussions_and_subscriptions_extensions_register_discussion_list_filters(self):
        registry = get_forum_registry()

        filters = registry.get_discussion_list_filters()
        filter_codes = [item.code for item in filters]
        self.assertIn("all", filter_codes)
        self.assertIn("following", filter_codes)
        self.assertIn("my", filter_codes)
        self.assertIn("unread", filter_codes)
        self.assertEqual(registry.get_default_discussion_list_filter_code(), "all")
        all_filter = next(item for item in filters if item.code == "all")
        following_filter = next(item for item in filters if item.code == "following")
        my_filter = next(item for item in filters if item.code == "my")
        unread_filter = next(item for item in filters if item.code == "unread")
        self.assertEqual(all_filter.module_id, "discussions")
        self.assertTrue(all_filter.sidebar_visible)
        self.assertEqual(all_filter.route_path, "/")
        self.assertEqual(following_filter.module_id, "subscriptions")
        self.assertTrue(following_filter.sidebar_visible)
        self.assertEqual(following_filter.route_path, "/following")
        self.assertFalse(my_filter.sidebar_visible)
        self.assertFalse(unread_filter.sidebar_visible)


def discussion_resource_payload(*, title=None, content=None):
    attributes = {}
    if title is not None:
        attributes["title"] = title
    if content is not None:
        attributes["content"] = content

    return {"data": {"type": "discussion", "attributes": attributes}}


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

    def test_discussion_core_schemas_do_not_expose_tag_ids(self):
        self.assertNotIn("tag_ids", DiscussionCreateSchema.__fields__)
        self.assertNotIn("tag_ids", DiscussionUpdateSchema.__fields__)

    def test_create_discussion_dispatches_created_event_after_commit(self):
        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                discussion = DiscussionService.create_discussion(
                    title="After commit discussion event",
                    content="Initial post",
                    user=self.author,
                )

        self.assertEqual(len(callbacks), 1)
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertEqual(event.discussion_id, discussion.id)

    def test_create_discussion_applies_runtime_private_checkers(self):
        class RuntimeModelService:
            def is_private(self, model, instance, *, default=False):
                return model is Discussion

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=RuntimeModelService()):
            discussion = DiscussionService.create_discussion(
                title="Private runtime discussion",
                content="Initial post",
                user=self.author,
            )

        first_post = Post.objects.get(id=discussion.first_post_id)
        self.assertTrue(discussion.is_private)
        self.assertTrue(first_post.is_private)
        self.assertFalse(Discussion.objects.filter(build_discussion_visibility_q(self.reader), id=discussion.id).exists())
        self.assertFalse(Post.objects.filter(build_post_visibility_q(self.reader), id=first_post.id).exists())

    def test_model_private_extender_refreshes_on_model_save(self):
        from types import SimpleNamespace

        from apps.core.extensions import ModelPrivateExtender
        from apps.core.extensions.application import ExtensionApplication

        app = ExtensionApplication()
        ModelPrivateExtender(Discussion).checker(
            lambda instance: "private" in instance.title.lower()
        ).extend(app, SimpleNamespace(extension_id="private-runtime"))
        app.make("models")

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=app.models):
            discussion = Discussion.objects.create(
                title="Private saved by signal",
                user=self.author,
                last_posted_user=self.author,
            )
            self.assertTrue(discussion.is_private)
            discussion.title = "Public saved by signal"
            discussion.save(update_fields=["title", "slug", "is_private"])

        self.assertFalse(discussion.is_private)

        discussion.refresh_from_db()
        self.assertFalse(discussion.is_private)

    def test_view_private_policy_allows_private_discussion_visibility(self):
        from apps.core.extensions.application import ExtensionApplication

        discussion = DiscussionService.create_discussion(
            title="Private visible through policy",
            content="Initial post",
            user=self.author,
        )
        Discussion.objects.filter(id=discussion.id).update(is_private=True)

        app = ExtensionApplication()
        app.policies.model_policy(
            "private-runtime",
            Discussion,
            lambda **context: True if context.get("ability") == "viewPrivate" else None,
        )

        with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=app):
            self.assertTrue(Discussion.objects.filter(build_discussion_visibility_q(self.reader), id=discussion.id).exists())

    def test_view_private_scoper_allows_matching_private_discussion_visibility(self):
        from apps.core.extensions.application import ExtensionApplication
        from apps.core.extensions.types import ExtensionModelVisibilityDefinition

        allowed = DiscussionService.create_discussion(
            title="Scoped private allowed",
            content="Initial post",
            user=self.author,
        )
        denied = DiscussionService.create_discussion(
            title="Scoped private denied",
            content="Initial post",
            user=self.author,
        )
        Discussion.objects.filter(id__in=[allowed.id, denied.id]).update(is_private=True)

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
            "private-runtime",
            ExtensionModelVisibilityDefinition(
                model=Discussion,
                ability="viewPrivate",
                scope=lambda queryset, context: queryset.filter(id=allowed.id),
            ),
        )

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=app.models):
            visible_ids = set(
                DiscussionService.apply_visibility_filters(
                    Discussion.objects.filter(id__in=[allowed.id, denied.id]),
                    self.reader,
                ).values_list("id", flat=True)
            )
            allowed.refresh_from_db()
            can_view_allowed = DiscussionService._can_view_discussion(allowed, self.reader)

        self.assertIn(allowed.id, visible_ids)
        self.assertNotIn(denied.id, visible_ids)
        self.assertTrue(can_view_allowed)

    def test_view_forum_permission_scopes_discussion_visibility_for_authenticated_user(self):
        blocked = User.objects.create_user(
            username="blocked-view-forum",
            email="blocked-view-forum@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        empty_group = Group.objects.create(name="NoForumView", color="#4d698e")
        blocked.user_groups.add(empty_group)
        discussion = DiscussionService.create_discussion(
            title="View forum gated discussion",
            content="Initial post",
            user=self.author,
        )

        visible_ids = set(
            DiscussionService.apply_visibility_filters(
                Discussion.objects.filter(id=discussion.id),
                blocked,
            ).values_list("id", flat=True)
        )

        self.assertNotIn(discussion.id, visible_ids)
        self.assertFalse(DiscussionService._can_view_discussion(discussion, blocked))

    def test_hide_scoper_allows_matching_hidden_discussion_visibility(self):
        from apps.core.extensions.application import ExtensionApplication
        from apps.core.extensions.types import ExtensionModelVisibilityDefinition

        allowed = DiscussionService.create_discussion(
            title="Scoped hidden allowed",
            content="Initial post",
            user=self.author,
        )
        denied = DiscussionService.create_discussion(
            title="Scoped hidden denied",
            content="Initial post",
            user=self.author,
        )
        Discussion.objects.filter(id__in=[allowed.id, denied.id]).update(hidden_at=timezone.now())

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
            "hidden-runtime",
            ExtensionModelVisibilityDefinition(
                model=Discussion,
                ability="hide",
                scope=lambda queryset, context: queryset.filter(id=allowed.id),
            ),
        )

        with patch("apps.core.extensions.runtime_access.get_runtime_model_service", return_value=app.models):
            visible_ids = set(
                DiscussionService.apply_visibility_filters(
                    Discussion.objects.filter(id__in=[allowed.id, denied.id]),
                    self.reader,
                ).values_list("id", flat=True)
            )
            allowed.refresh_from_db()
            can_view_allowed = DiscussionService._can_view_discussion(allowed, self.reader)

        self.assertIn(allowed.id, visible_ids)
        self.assertNotIn(denied.id, visible_ids)
        self.assertTrue(can_view_allowed)

    def test_approve_discussion_dispatches_event_after_commit(self):
        admin = User.objects.create_superuser(
            username="discussion-approver",
            email="discussion-approver@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="Pending discussion",
            content="Needs approval",
            user=self.author,
        )
        discussion.approval_status = Discussion.APPROVAL_PENDING
        discussion.save(update_fields=["approval_status"])

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                DiscussionService.approve_discussion(discussion, admin, note="ok")

        self.assertEqual(len(callbacks), 1)
        self.assertEqual(mocked_bus.dispatch.call_args.args[0].discussion_id, discussion.id)

    def test_create_discussion_accepts_bearer_token(self):
        response = self.client.post(
            "/api/discussions/",
            data=json.dumps(discussion_resource_payload(
                title="JWT backed discussion",
                content="Created through the API.",
            )),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["title"], "JWT backed discussion")
        self.assertEqual(payload["user"]["id"], self.author.id)

    def test_discussion_detail_exposes_user_primary_group_via_resource_payload(self):
        group = Group.objects.create(name="Authors", color="#2980b9", icon="fas fa-pen")
        Permission.objects.create(group=group, permission="startDiscussion")
        self.author.user_groups.add(group)
        discussion = DiscussionService.create_discussion(
            title="Primary group discussion",
            content="First post",
            user=self.author,
        )

        response = self.client.get(f"/api/discussions/{discussion.id}")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["user"]["primary_group"]["name"], group.name)

    def test_discussion_detail_supports_resource_field_selection(self):
        discussion = DiscussionService.create_discussion(
            title="字段裁剪讨论",
            content="用于验证 fields",
            user=self.author,
        )

        response = self.client.get(
            f"/api/discussions/{discussion.id}",
            {"fields[discussion]": "can_reply"},
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("can_reply", payload)
        self.assertNotIn("can_edit", payload)

    def test_discussion_detail_supports_explicit_relationship_includes(self):
        discussion = DiscussionService.create_discussion(
            title="关系包含讨论",
            content="用于验证 include",
            user=self.author,
        )

        response = self.client.get(
            f"/api/discussions/{discussion.id}",
            {"include": "user,last_posted_user"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["user"]["id"], self.author.id)
        self.assertEqual(payload["last_posted_user"]["id"], self.author.id)

    def test_discussion_list_avoids_n_plus_one_for_registered_user_relationships(self):
        for index in range(3):
            DiscussionService.create_discussion(
                title=f"预加载讨论 {index}",
                content="预加载内容",
                user=self.author,
            )

        with CaptureQueriesContext(connection) as context:
            response = self.client.get("/api/discussions/")

        self.assertEqual(response.status_code, 200, response.content)
        select_group_queries = [
            query["sql"]
            for query in context.captured_queries
            if "user_groups" in query["sql"].lower()
        ]
        self.assertLessEqual(len(select_group_queries), 2)

    def test_create_discussion_retries_on_transient_sqlite_lock(self):
        original_create = Discussion.objects.create
        state = {"failed": False}

        def flaky_create(*args, **kwargs):
            if not state["failed"]:
                state["failed"] = True
                raise OperationalError("database is locked")
            return original_create(*args, **kwargs)

        with patch("apps.core.db.time.sleep", return_value=None):
            with patch("extensions.discussions.backend.services.Discussion.objects.create", side_effect=flaky_create):
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
        create_runtime_post(
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

    def test_discussion_list_api_supports_core_registered_filters(self):
        my_discussion = DiscussionService.create_discussion(
            title="我的过滤 API",
            content="我的过滤内容",
            user=self.reader,
        )
        unread_discussion = DiscussionService.create_discussion(
            title="未读过滤 API",
            content="未读过滤内容",
            user=self.author,
        )

        DiscussionUser.objects.update_or_create(
            discussion=unread_discussion,
            user=self.reader,
            defaults={"is_subscribed": False, "last_read_post_number": 1},
        )
        create_runtime_post(
            discussion_id=unread_discussion.id,
            content="这会制造未读",
            user=self.author,
        )

        my_response = self.client.get(
            "/api/discussions/",
            {"filter": "my"},
            **self.auth_header(self.reader),
        )
        unread_response = self.client.get(
            "/api/discussions/",
            {"filter": "unread"},
            **self.auth_header(self.reader),
        )

        self.assertEqual(my_response.status_code, 200, my_response.content)
        self.assertEqual(unread_response.status_code, 200, unread_response.content)

        self.assertEqual([item["id"] for item in my_response.json()["data"]], [my_discussion.id])
        self.assertEqual([item["id"] for item in unread_response.json()["data"]], [unread_discussion.id])

    def test_discussion_list_api_normalizes_page_and_limit(self):
        DiscussionService.create_discussion(
            title="分页规范化讨论",
            content="测试分页参数收口",
            user=self.author,
        )

        response = self.client.get("/api/discussions/", {"page": 0, "limit": 999})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["limit"], 100)
        self.assertTrue(any(item["code"] == "my" and item["sidebar_visible"] is False for item in payload["available_filters"]))

    def test_discussion_list_static_route_uses_resource_endpoint_mutator(self):
        DiscussionService.create_discussion(
            title="资源端点讨论",
            content="测试静态路由进入资源端点",
            user=self.author,
        )

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
        for endpoint in discussion_resource_endpoints():
            registry.register_endpoint(endpoint)
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="index",
                module_id="test",
                operation="mutate",
                mutator=mutate_endpoint,
            )
        )

        with patch("extensions.discussions.backend.handlers.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                response = self.client.get("/api/discussions/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["mutated_by_resource_endpoint"])

    def test_discussion_list_static_route_honors_endpoint_default_include(self):
        discussion = DiscussionService.create_discussion(
            title="默认 include 讨论",
            content="测试静态路由读取资源端点默认 include",
            user=self.author,
        )

        registry = ResourceRegistry()
        for endpoint in discussion_resource_endpoints():
            registry.register_endpoint(endpoint)
        registry.register_relationship(
            ResourceRelationshipDefinition(
                resource="discussion",
                relationship="extension_marker",
                module_id="test",
                resolver=lambda item, context: f"included:{item.id}",
            )
        )
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="index",
                module_id="test",
                operation="mutate",
                mutator=lambda endpoint: replace(endpoint, default_include=("extension_marker",)),
            )
        )

        with patch("extensions.discussions.backend.handlers.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                response = self.client.get("/api/discussions/")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        item = next(item for item in payload["data"] if item["id"] == discussion.id)
        self.assertEqual(item["extension_marker"], f"included:{discussion.id}")

    def test_discussion_list_sort_catalog_uses_resource_sort_definitions(self):
        DiscussionService.create_discussion(
            title="资源排序目录讨论",
            content="测试排序目录进入资源定义",
            user=self.author,
        )

        registry = ResourceRegistry()
        registry.register_sort(
            ResourceSortDefinition(
                resource="discussion",
                sort="newest",
                module_id="test",
                operation="remove",
            )
        )

        with patch("extensions.discussions.backend.services.get_runtime_resource_registry", return_value=registry):
            response = self.client.get("/api/discussions/")

        self.assertEqual(response.status_code, 200, response.content)
        sort_codes = {item["code"] for item in response.json()["available_sorts"]}
        self.assertNotIn("newest", sort_codes)

    def test_discussion_detail_static_route_uses_resource_endpoint_mutator(self):
        discussion = DiscussionService.create_discussion(
            title="详情资源端点讨论",
            content="测试详情静态路由进入资源端点",
            user=self.author,
        )

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
        for endpoint in discussion_resource_endpoints():
            registry.register_endpoint(endpoint)
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="show",
                module_id="test",
                operation="mutate",
                mutator=mutate_endpoint,
            )
        )

        with patch("extensions.discussions.backend.handlers.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                response = self.client.get(f"/api/discussions/{discussion.id}")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["mutated_by_resource_endpoint"])

    def test_discussion_detail_static_route_honors_endpoint_default_include(self):
        discussion = DiscussionService.create_discussion(
            title="详情默认 include 讨论",
            content="测试详情静态路由读取资源端点默认 include",
            user=self.author,
        )

        registry = ResourceRegistry()
        for endpoint in discussion_resource_endpoints():
            registry.register_endpoint(endpoint)
        registry.register_relationship(
            ResourceRelationshipDefinition(
                resource="discussion",
                relationship="extension_marker",
                module_id="test",
                resolver=lambda item, context: f"included:{item.id}",
            )
        )
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="discussion",
                endpoint="show",
                module_id="test",
                operation="mutate",
                mutator=lambda endpoint: replace(endpoint, default_include=("extension_marker",)),
            )
        )

        with patch("extensions.discussions.backend.handlers.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                response = self.client.get(f"/api/discussions/{discussion.id}")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["extension_marker"], f"included:{discussion.id}")

    def test_discussion_detail_not_found_returns_structured_error_payload(self):
        response = self.client.get("/api/discussions/999999")

        self.assertEqual(response.status_code, 404, response.content)
        payload = response.json()
        self.assertEqual(payload["error"], "讨论不存在")
        self.assertEqual(payload["message"], "讨论不存在")
        self.assertEqual(payload["code"], "not_found")
        self.assertIn("request_id", payload)

    def test_discussion_detail_does_not_mark_everything_read_immediately(self):
        discussion = DiscussionService.create_discussion(
            title="Unread detail",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        create_runtime_post(
            discussion_id=discussion.id,
            content="Reply one",
            user=self.author,
        )
        create_runtime_post(
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

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "discussion-view-count-flush-test"}})
    def test_view_count_flushes_synchronously_when_queue_disabled(self):
        cache.clear()
        discussion = DiscussionService.create_discussion(
            title="View count sync flush",
            content="Initial post",
            user=self.author,
        )

        DiscussionService.record_view(discussion, self.reader)

        discussion.refresh_from_db()
        self.assertEqual(discussion.view_count, 1)
        self.assertEqual(
            cache.get(DiscussionService._view_count_pending_cache_key(discussion.id)),
            None,
        )

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "discussion-view-count-queue-test"}})
    def test_view_count_is_queued_when_queue_enabled(self):
        from extensions.discussions.backend.tasks import flush_discussion_view_count_task

        cache.clear()
        discussion = DiscussionService.create_discussion(
            title="View count queued flush",
            content="Initial post",
            user=self.author,
        )

        with patch("apps.core.queue_service.QueueService.get_runtime_config", return_value={"enabled": True, "driver": "redis"}):
            with patch.object(flush_discussion_view_count_task, "apply_async") as apply_async:
                DiscussionService.record_view(discussion, self.reader)

        discussion.refresh_from_db()
        self.assertEqual(discussion.view_count, 0)
        self.assertEqual(cache.get(DiscussionService._view_count_pending_cache_key(discussion.id)), 1)
        apply_async.assert_called_once()

        flushed_count = DiscussionService.flush_pending_view_count(discussion.id)
        discussion.refresh_from_db()
        self.assertEqual(flushed_count, 1)
        self.assertEqual(discussion.view_count, 1)

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "discussion-view-count-command-test"}})
    def test_flush_discussion_view_counts_command_flushes_pending_counts(self):
        cache.clear()
        discussion = DiscussionService.create_discussion(
            title="View count command flush",
            content="Initial post",
            user=self.author,
        )
        cache.set(DiscussionService._view_count_pending_cache_key(discussion.id), 3, 60)
        cache.set(DiscussionService.VIEW_COUNT_PENDING_IDS_CACHE_KEY, [discussion.id], 60)

        stdout = StringIO()
        call_command("flush_discussion_view_counts", stdout=stdout)

        discussion.refresh_from_db()
        self.assertEqual(discussion.view_count, 3)
        self.assertIn("已写回 3 次讨论浏览量", stdout.getvalue())

    def test_update_discussion_read_state_advances_progress(self):
        discussion = DiscussionService.create_discussion(
            title="Read state update",
            content="Initial post",
            user=self.author,
        )
        DiscussionService.get_discussion_by_id(discussion.id, self.reader)
        create_runtime_post(
            discussion_id=discussion.id,
            content="Reply one",
            user=self.author,
        )
        create_runtime_post(
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

    def test_suspended_user_cannot_create_discussion(self):
        self.author.suspended_until = timezone.now() + timedelta(days=1)
        self.author.suspend_message = "封禁期间不可发帖"
        self.author.save(update_fields=["suspended_until", "suspend_message"])

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps(discussion_resource_payload(
                title="Should fail",
                content="Blocked content",
            )),
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
            data=json.dumps(discussion_resource_payload(
                title="Should fail",
                content="Blocked until email verification",
            )),
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
            data=json.dumps(discussion_resource_payload(
                title="Should fail",
                content="Blocked by forum permission",
            )),
            content_type="application/json",
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限发起讨论")

    def test_discussion_approval_transitions_keep_author_counts_consistent(self):
        admin = User.objects.create_superuser(
            username="approval-count-admin",
            email="approval-count-admin@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="Approval count discussion",
            content="First post",
            user=self.author,
        )
        reply = create_runtime_post(
            discussion_id=discussion.id,
            content="Counted reply",
            user=self.reader,
        )

        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 1)
        self.assertEqual(self.reader.comment_count, 1)

        DiscussionService.approve_discussion(discussion, admin)
        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 1)
        self.assertEqual(self.reader.comment_count, 1)

        DiscussionService.reject_discussion(discussion, admin, note="下架")
        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 0)
        self.assertEqual(self.reader.comment_count, 0)

        discussion.refresh_from_db()
        DiscussionService.approve_discussion(discussion, admin, note="恢复")
        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        reply.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 1)
        self.assertEqual(self.reader.comment_count, 1)
        self.assertEqual(reply.approval_status, "approved")

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
        create_runtime_post(
            discussion_id=discussion.id,
            content="隐藏时需要扣回的回复",
            user=self.reader,
        )

        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 1)
        self.assertEqual(self.reader.comment_count, 1)

        hide_response = self.client.post(
            f"/api/discussions/{discussion.id}/hide",
            **self.auth_header(admin),
        )
        self.assertEqual(hide_response.status_code, 200, hide_response.content)
        hide_log = AuditLog.objects.get(action="admin.discussion.hide", target_id=discussion.id)
        self.assertEqual(hide_log.target_type, "discussion")
        self.assertEqual(hide_log.data["title"], "隐藏测试讨论")

        discussion.refresh_from_db()
        self.assertTrue(discussion.is_hidden)
        self.assertEqual(discussion.hidden_user_id, admin.id)
        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 0)
        self.assertEqual(self.reader.comment_count, 0)

        DiscussionService.set_hidden_state(discussion, admin, True)
        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 0)
        self.assertEqual(self.reader.comment_count, 0)

        guest_detail = self.client.get(f"/api/discussions/{discussion.id}")
        self.assertEqual(guest_detail.status_code, 404, guest_detail.content)

        restore_response = self.client.post(
            f"/api/discussions/{discussion.id}/hide",
            **self.auth_header(admin),
        )
        self.assertEqual(restore_response.status_code, 200, restore_response.content)
        restore_log = AuditLog.objects.get(action="admin.discussion.restore", target_id=discussion.id)
        self.assertEqual(restore_log.target_type, "discussion")

        discussion.refresh_from_db()
        self.assertFalse(discussion.is_hidden)
        self.assertIsNone(discussion.hidden_user_id)
        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 1)
        self.assertEqual(self.reader.comment_count, 1)

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

    def test_updating_discussion_title_creates_discussion_renamed_event_post(self):
        member_group = Group.objects.create(name="DiscussionRenameAuthor", color="#4d698e")
        Permission.objects.create(group=member_group, permission="startDiscussion")
        Permission.objects.create(group=member_group, permission="discussion.editOwn")
        self.author.user_groups.add(member_group)

        discussion = DiscussionService.create_discussion(
            title="Original title",
            content="Original content",
            user=self.author,
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/discussions/{discussion.id}",
                data=json.dumps({
                    "title": "Updated title",
                }),
                content_type="application/json",
                **self.auth_header(self.author),
            )

        self.assertEqual(response.status_code, 200, response.content)
        discussion.refresh_from_db()
        renamed_post = Post.objects.get(discussion=discussion, number=2)
        self.assertEqual(renamed_post.type, "discussionRenamed")
        self.assertEqual(renamed_post.content, "from: Original title\nto: Updated title")
        self.assertEqual(discussion.last_post_id, renamed_post.id)
        self.assertEqual(discussion.last_post_number, 2)
        self.assertEqual(discussion.comment_count, 1)

        posts_response = self.client.get(f"/api/discussions/{discussion.id}/posts")
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        payload = posts_response.json()["data"]
        event_post = next(item for item in payload if item["id"] == renamed_post.id)
        self.assertEqual(event_post["type"], "discussionRenamed")
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionRenamed",
                "old_title": "Original title",
                "new_title": "Updated title",
            },
        )

    def test_locking_discussion_creates_discussion_locked_event_post(self):
        discussion = DiscussionService.create_discussion(
            title="Lock me",
            content="Original content",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="discussion-lock-admin",
            email="discussion-lock-admin@example.com",
            password="password123",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/discussions/{discussion.id}/lock",
                **self.auth_header(admin),
            )

        self.assertEqual(response.status_code, 200, response.content)
        discussion.refresh_from_db()
        self.assertTrue(discussion.is_locked)
        locked_post = Post.objects.get(discussion=discussion, number=2)
        self.assertEqual(locked_post.type, "discussionLocked")
        self.assertEqual(locked_post.content, "locked")
        self.assertEqual(discussion.last_post_id, locked_post.id)
        self.assertEqual(discussion.comment_count, 1)

        posts_response = self.client.get(f"/api/discussions/{discussion.id}/posts")
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        payload = posts_response.json()["data"]
        event_post = next(item for item in payload if item["id"] == locked_post.id)
        self.assertEqual(event_post["type"], "discussionLocked")
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionLocked",
                "is_locked": True,
            },
        )
        self.assertEqual(
            event_post["post_type"],
            {
                "code": "discussionLocked",
                "label": "讨论锁定状态变更",
                "description": "记录讨论被锁定或解除锁定的系统事件帖，不计入回复统计和全文搜索。",
                "icon": "fas fa-lock",
                "module_id": "discussions",
                "is_default": False,
                "is_stream_visible": True,
                "counts_toward_discussion": False,
                "counts_toward_user": False,
                "searchable": False,
            },
        )

    def test_updating_discussion_locked_state_creates_discussion_locked_event_post(self):
        discussion = DiscussionService.create_discussion(
            title="Patch lock me",
            content="Original content",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="discussion-patch-lock-admin",
            email="discussion-patch-lock-admin@example.com",
            password="password123",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/discussions/{discussion.id}",
                data=json.dumps({
                    "is_locked": True,
                }),
                content_type="application/json",
                **self.auth_header(admin),
            )

        self.assertEqual(response.status_code, 200, response.content)
        discussion.refresh_from_db()
        self.assertTrue(discussion.is_locked)
        locked_post = Post.objects.get(discussion=discussion, number=2)
        self.assertEqual(locked_post.type, "discussionLocked")
        self.assertEqual(locked_post.content, "locked")

        posts_response = self.client.get(f"/api/discussions/{discussion.id}/posts")
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        payload = posts_response.json()["data"]
        event_post = next(item for item in payload if item["id"] == locked_post.id)
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionLocked",
                "is_locked": True,
            },
        )

    def test_sticky_discussion_creates_discussion_sticky_event_post(self):
        discussion = DiscussionService.create_discussion(
            title="Pin me",
            content="Original content",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="discussion-sticky-admin",
            email="discussion-sticky-admin@example.com",
            password="password123",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/discussions/{discussion.id}/pin",
                **self.auth_header(admin),
            )

        self.assertEqual(response.status_code, 200, response.content)
        discussion.refresh_from_db()
        self.assertTrue(discussion.is_sticky)
        sticky_post = Post.objects.get(discussion=discussion, number=2)
        self.assertEqual(sticky_post.type, "discussionSticky")
        self.assertEqual(sticky_post.content, "sticky")
        self.assertEqual(discussion.last_post_id, sticky_post.id)
        self.assertEqual(discussion.comment_count, 1)

        posts_response = self.client.get(f"/api/discussions/{discussion.id}/posts")
        self.assertEqual(posts_response.status_code, 200, posts_response.content)
        payload = posts_response.json()["data"]
        event_post = next(item for item in payload if item["id"] == sticky_post.id)
        self.assertEqual(event_post["type"], "discussionSticky")
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionSticky",
                "is_sticky": True,
            },
        )

    def test_hiding_discussion_creates_discussion_hidden_event_post(self):
        discussion = DiscussionService.create_discussion(
            title="Hide me",
            content="Original content",
            user=self.author,
        )
        admin = User.objects.create_superuser(
            username="discussion-hide-admin",
            email="discussion-hide-admin@example.com",
            password="password123",
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                f"/api/discussions/{discussion.id}/hide",
                **self.auth_header(admin),
            )

        self.assertEqual(response.status_code, 200, response.content)
        hidden_post = Post.objects.get(discussion=discussion, number=2)
        self.assertEqual(hidden_post.type, "discussionHidden")

        hidden_detail = self.client.get(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(admin),
        )
        self.assertEqual(hidden_detail.status_code, 200, hidden_detail.content)

        posts_response = self.client.get(
            f"/api/discussions/{discussion.id}/posts",
            **self.auth_header(admin),
        )
        payload = posts_response.json()["data"]
        event_post = next(item for item in payload if item["id"] == hidden_post.id)
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionHidden",
                "is_hidden": True,
            },
        )

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
        self.assertFalse(AuditLog.objects.filter(action="admin.discussion.delete").exists())

    def test_global_delete_discussion_permission_writes_admin_audit_log(self):
        moderator = User.objects.create_user(
            username="discussion-delete-moderator",
            email="discussion-delete-moderator@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        moderator_group = Group.objects.create(name="DiscussionDeleteModerator", color="#4d698e")
        Permission.objects.create(group=moderator_group, permission="discussion.delete")
        moderator.user_groups.add(moderator_group)
        discussion = DiscussionService.create_discussion(
            title="Moderator deletes discussion",
            content="Allowed by global permission",
            user=self.author,
        )

        response = self.client.delete(
            f"/api/discussions/{discussion.id}",
            **self.auth_header(moderator),
        )

        self.assertEqual(response.status_code, 200, response.content)
        audit_log = AuditLog.objects.get(action="admin.discussion.delete", target_id=discussion.id)
        self.assertEqual(audit_log.user_id, moderator.id)
        self.assertEqual(audit_log.target_type, "discussion")
        self.assertEqual(audit_log.data["title"], "Moderator deletes discussion")

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

    def test_delete_rejected_discussion_does_not_decrement_reply_author_counts_again(self):
        admin = User.objects.create_superuser(
            username="delete-rejected-discussion-admin",
            email="delete-rejected-discussion-admin@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="Rejected delete discussion",
            content="First post",
            user=self.author,
        )
        create_runtime_post(
            discussion_id=discussion.id,
            content="Counted reply before rejection",
            user=self.reader,
        )

        DiscussionService.reject_discussion(discussion, admin, note="下架")
        self.reader.refresh_from_db()
        self.assertEqual(self.reader.comment_count, 0)

        discussion.refresh_from_db()
        DiscussionService.delete_discussion(discussion.id, admin)

        self.reader.refresh_from_db()
        self.assertEqual(self.reader.comment_count, 0)

    def test_delete_hidden_discussion_does_not_decrement_counts_again(self):
        admin = User.objects.create_superuser(
            username="delete-hidden-discussion-admin",
            email="delete-hidden-discussion-admin@example.com",
            password="password123",
        )
        discussion = DiscussionService.create_discussion(
            title="Hidden delete discussion",
            content="First post",
            user=self.author,
        )
        create_runtime_post(
            discussion_id=discussion.id,
            content="Counted reply before hide",
            user=self.reader,
        )

        DiscussionService.set_hidden_state(discussion, admin, True)
        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 0)
        self.assertEqual(self.reader.comment_count, 0)

        discussion.refresh_from_db()
        DiscussionService.delete_discussion(discussion.id, admin)

        self.author.refresh_from_db()
        self.reader.refresh_from_db()
        self.assertEqual(self.author.discussion_count, 0)
        self.assertEqual(self.reader.comment_count, 0)


