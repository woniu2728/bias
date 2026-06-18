import json
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from ninja_jwt.tokens import RefreshToken
from types import SimpleNamespace
from unittest.mock import patch

from apps.core.forum_registry import get_forum_registry
from apps.core.extensions.runtime import (
    create_runtime_discussion,
)
from extensions.testing import ExtensionRuntimeTestMixin
from extensions.mentions.backend.models import PostMentionsUser
from apps.core.extensions.runtime import get_runtime_tag_model
from apps.core.extensions.runtime import (
    create_runtime_post,
    set_runtime_post_hidden_state,
    update_runtime_post,
)
from apps.core.extensions.runtime import (
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
Tag = RuntimeModelProxy(get_runtime_tag_model)


class MentionsExtensionDiagnosticsTests(ExtensionRuntimeTestMixin, TestCase):
    def test_mentions_extension_registers_runtime_service_provider(self):
        application = self.bootstrap_extensions("mentions")
        service = application.get_service("mentions.service")

        self.assertIn("mentions.service", application.get_service_provider_keys(extension_id="mentions"))
        self.assertIs(service["model"], PostMentionsUser)

    def test_mentions_capabilities_are_filtered_when_extension_disabled(self):
        self.disable_extension_for_test("mentions")

        registry = get_forum_registry()

        self.assertFalse(any(item.module_id == "mentions" for item in registry.get_search_filters()))
        self.assertFalse(any(item.module_id == "mentions" for item in registry.get_notification_types()))

    def test_inspect_reports_mentions_model_as_extension_native(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "mentions",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]
        owned_item = audit["items"][0]

        self.assertEqual(extension["id"], "mentions")
        self.assertIn("0001_state_post_mentions_user.py", extension["migration_plan"]["pending_files"])
        self.assertEqual(audit["extension_native_count"], 1)
        self.assertEqual(audit["app_label_migration_required_count"], 0)
        self.assertEqual(audit["app_label_migration_plan_required_count"], 0)
        self.assertTrue(all(item["storage_origin"] == "extension" for item in audit["items"]))
        self.assertTrue(all(item["model_module"].startswith("extensions.mentions") for item in audit["items"]))
        self.assertEqual(audit["app_label_migration_items"], [])
        self.assertEqual(owned_item["current_app_label"], "mentions")
        self.assertEqual(owned_item["target_app_label"], "mentions")
        self.assertEqual(owned_item["migration_risk"], "none")


class MentionsExtensionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="mention-author",
            email="mention-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.admin = User.objects.create_superuser(
            username="mention-admin",
            email="mention-admin@example.com",
            password="password123",
        )
        self.discussion = create_runtime_discussion(
            title="Mention discussion",
            content="First post",
            user=self.author,
        )
        self.post = create_runtime_post(
            discussion_id=self.discussion.id,
            content="需要提及的内容",
            user=self.author,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.author).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extension_detail_api_surfaces_registered_capabilities_for_mentions_extension(self):
        response = self.client.get(
            "/api/admin/extensions/mentions",
            **self.auth_header(self.admin),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_admin_entry"], "extensions/mentions/frontend/admin/index.js")
        self.assertTrue(any(item["module_id"] == "mentions" and item["name"] == "mentionGroups" for item in payload["permissions"]))
        self.assertTrue(any(item["code"] == "mentioned_me" for item in payload["search_filters"]))
        self.assertTrue(any(item["code"] == "userMentioned" for item in payload["notification_types"]))
        self.assertTrue(any(item["key"] == "notify_user_mentioned" for item in payload["user_preferences"]))
        self.assertTrue(
            any(
                item["event"] == "UserMentionedEvent"
                and item["module_id"] == "mentions"
                and item.get("source") == "runtime"
                for item in payload["event_listeners"]
            )
        )
        self.assertTrue(
            any(
                item["key"] == "mentions"
                and item["module_id"] == "mentions"
                and "apply_created" in item["phases"]
                and "apply_updated" in item["phases"]
                and "apply_approved" in item["phases"]
                and "apply_hidden" in item["phases"]
                and "prepare_delete" in item["phases"]
                for item in payload["post_lifecycle"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "mentions"
                and item["resource"] == "post"
                and item["relationship"] == "mentionsUsers"
                for item in payload["resource_relationships"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "mentions"
                and item["resource"] == "user_detail"
                and item["field"] == "canMentionGroups"
                for item in payload["resource_fields"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "mentions"
                and item["model"] == "Post"
                and item["name"] == "mentionsUsers"
                for item in payload["model_relations"]
            )
        )

    def test_markdown_preview_keeps_username_route_for_unknown_mentions(self):
        response = self.client.post(
            "/api/preview",
            data=json.dumps({
                "content": "你好 @ghost"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn('href="/u/ghost"', response.json()["html"])

    def test_mentions_extension_conditionally_renders_tag_mentions_when_tags_enabled(self):
        from apps.core.extensions import ConditionalExtender, ServiceProviderExtender
        from apps.core.extensions.application import ExtensionApplication
        from apps.core.extensions.formatter_service import apply_extension_formatter_render, clear_extension_formatter_cache
        from extensions.mentions.backend.ext import tag_mentions_extenders

        Tag.objects.create(name="产品发布", slug="release")
        tags_extension = SimpleNamespace(
            id="tags",
            runtime=SimpleNamespace(installed=True, enabled=True),
        )
        app = ExtensionApplication(extensions_to_boot=(tags_extension,))
        ServiceProviderExtender(
            "tags.service",
            "extensions.tags.backend.runtime.tag_service_provider",
        ).extend(app, SimpleNamespace(extension_id="tags"))
        app.make("providers")
        extension = SimpleNamespace(extension_id="mentions")
        ConditionalExtender().when_extension_enabled("tags", tag_mentions_extenders).extend(app, extension)
        app.make("formatters")

        clear_extension_formatter_cache()
        try:
            with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
                html = apply_extension_formatter_render("<p>查看 #release</p>")
        finally:
            clear_extension_formatter_cache()

        self.assertIn('<a href="/t/release" class="mention mention--tag">#产品发布</a>', html)

    def test_post_detail_exposes_mentions_users_when_included(self):
        mentioned = User.objects.create_user(
            username="mentioned-resource-user",
            email="mentioned-resource-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        reply = create_runtime_post(
            discussion_id=self.discussion.id,
            content=f"hello @{mentioned.username}",
            user=self.author,
        )

        response = self.client.get(
            f"/api/posts/{reply.id}",
            {"include": "mentionsUsers"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["mentionsUsers"][0]["id"], mentioned.id)
        self.assertEqual(payload["mentionsUsers"][0]["username"], mentioned.username)

    def test_user_detail_exposes_can_mention_groups_for_self(self):
        user = User.objects.create_user(
            username="mention-groups-profile",
            email="mention-groups-profile@example.com",
            password="password123",
        )
        group = Group.objects.create(name="Mentioners", color="#27ae60", icon="fas fa-at")
        Permission.objects.create(group=group, permission="mentionGroups")
        user.user_groups.add(group)
        token = RefreshToken.for_user(user).access_token

        response = self.client.get(
            f"/api/users/{user.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["canMentionGroups"])

        other = User.objects.create_user(
            username="mention-groups-other",
            email="mention-groups-other@example.com",
            password="password123",
        )
        other_response = self.client.get(
            f"/api/users/{other.id}",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(other_response.status_code, 200, other_response.content)
        self.assertNotIn("canMentionGroups", other_response.json())

    def test_search_api_supports_registered_mentioned_me_filter_syntax(self):
        mentioned_user = User.objects.create_user(
            username="mentioned-me-user",
            email="mentioned-me-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        other_user = User.objects.create_user(
            username="mentioned-other-user",
            email="mentioned-other-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        discussion = create_runtime_discussion(
            title="提及过滤讨论",
            content="首帖内容",
            user=self.author,
        )
        matched_post = create_runtime_post(
            discussion_id=discussion.id,
            content=f"Hello @{mentioned_user.username} 提及过滤关键字",
            user=self.author,
        )
        create_runtime_post(
            discussion_id=discussion.id,
            content=f"Hello @{other_user.username} 提及过滤关键字",
            user=self.author,
        )

        response = self.client.get(
            "/api/search",
            {"q": "提及过滤关键字 mentioned:me", "type": "posts"},
            **self.auth_header(mentioned_user),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["post_total"], 1)
        self.assertEqual([item["id"] for item in payload["posts"]], [matched_post.id])

    def test_search_api_supports_registered_mentioned_me_filter_for_first_post(self):
        mentioned_user = User.objects.create_user(
            username="mentioned-first-post-user",
            email="mentioned-first-post-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        discussion = create_runtime_discussion(
            title="首帖提及过滤讨论",
            content=f"Hello @{mentioned_user.username} 首帖提及过滤关键字",
            user=self.author,
        )

        response = self.client.get(
            "/api/search",
            {"q": "首帖提及过滤关键字 mentioned:me", "type": "posts"},
            **self.auth_header(mentioned_user),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["post_total"], 1)
        self.assertEqual([item["id"] for item in payload["posts"]], [discussion.first_post_id])

    def test_search_filters_api_exposes_registered_mentioned_me_filter_syntax(self):
        response = self.client.get("/api/search/filters", {"target": "posts"})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("mentioned:me", {item["syntax"] for item in response.json()["filters"]})

    def test_hiding_and_restoring_post_updates_mentions_through_post_lifecycle(self):
        mentioned = User.objects.create_user(
            username="hidden-mentioned-user",
            email="hidden-mentioned-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        update_runtime_post(self.post.id, self.author, f"hello @{mentioned.username}")
        self.post.refresh_from_db()
        self.assertTrue(PostMentionsUser.objects.filter(post=self.post, mentions_user=mentioned).exists())

        set_runtime_post_hidden_state(self.post, self.admin, True)

        self.assertFalse(PostMentionsUser.objects.filter(post=self.post).exists())

        set_runtime_post_hidden_state(self.post, self.admin, False)

        self.assertTrue(PostMentionsUser.objects.filter(post=self.post, mentions_user=mentioned).exists())


