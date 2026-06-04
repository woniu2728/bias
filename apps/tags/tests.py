from django.core.management import call_command
from django.test import TestCase, override_settings
from ninja_jwt.tokens import RefreshToken
from io import StringIO
from unittest.mock import patch

from apps.discussions.services import DiscussionService
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceRegistry
from apps.core.settings_service import clear_runtime_setting_caches
from apps.tags.models import DiscussionTag, Tag
from extensions.tags.backend.services import TagService
from apps.users.models import User
from apps.users.models import Group, Permission
from extensions.tags.backend.ext import tag_resource_endpoints


def discussion_tags_payload(tag_ids):
    return {
        "data": {
            "relationships": {
                "tags": {
                    "data": [
                        {"type": "tag", "id": str(tag_id)}
                        for tag_id in tag_ids
                    ],
                },
            },
        },
    }


class TagStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tagger",
            email="tagger@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.tag = Tag.objects.create(
            name="生活",
            slug="life",
            color="#4d698e",
        )

    def test_create_discussion_refreshes_tag_count(self):
        with self.captureOnCommitCallbacks(execute=True):
            DiscussionService.create_discussion(
                title="生活讨论 1",
                content="第一条生活内容",
                user=self.user,
                extension_payload=discussion_tags_payload([self.tag.id]),
            )
        with self.captureOnCommitCallbacks(execute=True):
            DiscussionService.create_discussion(
                title="生活讨论 2",
                content="第二条生活内容",
                user=self.user,
                extension_payload=discussion_tags_payload([self.tag.id]),
            )

        self.tag.refresh_from_db()

        self.assertEqual(self.tag.discussion_count, 2)
        self.assertIsNotNone(self.tag.last_posted_discussion)

    def test_refresh_tag_stats_repairs_existing_discussion_count(self):
        discussion = DiscussionService.create_discussion(
            title="历史讨论",
            content="历史内容",
            user=self.user,
        )
        DiscussionTag.objects.create(discussion=discussion, tag=self.tag)
        Tag.objects.filter(id=self.tag.id).update(discussion_count=0)

        TagService.refresh_tag_stats([self.tag.id])
        self.tag.refresh_from_db()

        self.assertEqual(self.tag.discussion_count, 1)

    def test_refresh_tag_stats_command_repairs_all_tags(self):
        discussion = DiscussionService.create_discussion(
            title="命令刷新统计",
            content="命令刷新内容",
            user=self.user,
        )
        DiscussionTag.objects.create(discussion=discussion, tag=self.tag)
        Tag.objects.filter(id=self.tag.id).update(discussion_count=0)

        stdout = StringIO()
        call_command("refresh_tag_stats", stdout=stdout)
        self.tag.refresh_from_db()

        self.assertEqual(self.tag.discussion_count, 1)
        self.assertIn("已刷新全部标签统计", stdout.getvalue())

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_dispatch_refresh_tag_stats_queues_when_enabled(self):
        from apps.tags.tasks import refresh_tag_stats_task

        clear_runtime_setting_caches()
        with patch("apps.core.queue_service.QueueService.get_runtime_config", return_value={"enabled": True, "driver": "redis"}):
            with patch.object(refresh_tag_stats_task, "delay") as delay:
                with patch("extensions.tags.backend.services.TagService.refresh_tag_stats") as refresh_tag_stats:
                    with self.captureOnCommitCallbacks(execute=True):
                        result = TagService.dispatch_refresh_tag_stats([self.tag.id])

        self.assertEqual(result["mode"], "queued")
        delay.assert_called_once_with([self.tag.id])
        refresh_tag_stats.assert_not_called()

    def test_pending_discussion_is_not_counted_until_approved(self):
        trusted_group = Group.objects.create(name="TagTrusted", color="#4d698e")
        Permission.objects.create(group=trusted_group, permission="startDiscussionWithoutApproval")
        admin = User.objects.create_superuser(
            username="tag-admin",
            email="tag-admin@example.com",
            password="password123",
        )

        with self.captureOnCommitCallbacks(execute=True):
            discussion = DiscussionService.create_discussion(
                title="待审核标签讨论",
                content="等待审核",
                user=self.user,
                extension_payload=discussion_tags_payload([self.tag.id]),
            )
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.discussion_count, 0)
        self.assertIsNone(self.tag.last_posted_discussion)

        with self.captureOnCommitCallbacks(execute=True):
            DiscussionService.approve_discussion(discussion, admin)
        self.tag.refresh_from_db()
        self.assertEqual(self.tag.discussion_count, 1)
        self.assertEqual(self.tag.last_posted_discussion_id, discussion.id)

    def test_create_tag_generates_slug_when_missing(self):
        admin = User.objects.create_superuser(
            username="tag-admin-2",
            email="tag-admin-2@example.com",
            password="password123",
        )
        tag = TagService.create_tag(name="纯中文标签", user=admin)

        self.assertTrue(tag.slug)
        self.assertEqual(tag.slug, tag.slug.strip())

    def test_reply_refreshes_tag_last_posted_at(self):
        with self.captureOnCommitCallbacks(execute=True):
            discussion = DiscussionService.create_discussion(
                title="标签回复刷新",
                content="首帖",
                user=self.user,
                extension_payload=discussion_tags_payload([self.tag.id]),
            )
        self.tag.refresh_from_db()
        initial_last_posted_at = self.tag.last_posted_at

        from apps.posts.services import PostService
        with self.captureOnCommitCallbacks(execute=True):
            PostService.create_post(
                discussion_id=discussion.id,
                content="新的回复",
                user=self.user,
            )

        self.tag.refresh_from_db()
        self.assertIsNotNone(initial_last_posted_at)
        self.assertGreater(self.tag.last_posted_at, initial_last_posted_at)
        self.assertEqual(self.tag.last_posted_discussion_id, discussion.id)


class TagAccessApiTests(TestCase):
    def setUp(self):
        self.member = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.admin = User.objects.create_superuser(
            username="tag-admin",
            email="tag-admin@example.com",
            password="password123",
        )
        self.public_tag = Tag.objects.create(name="公开", slug="public-tag")
        self.members_tag = Tag.objects.create(
            name="成员区",
            slug="members-tag",
            view_scope=Tag.ACCESS_MEMBERS,
            start_discussion_scope=Tag.ACCESS_MEMBERS,
            reply_scope=Tag.ACCESS_MEMBERS,
        )
        self.staff_tag = Tag.objects.create(
            name="管理区",
            slug="staff-tag",
            view_scope=Tag.ACCESS_STAFF,
            start_discussion_scope=Tag.ACCESS_STAFF,
            reply_scope=Tag.ACCESS_STAFF,
        )

    def auth_header(self, user):
        token = RefreshToken.for_user(user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_guest_tag_list_hides_member_and_staff_tags(self):
        response = self.client.get("/api/tags")

        self.assertEqual(response.status_code, 200, response.content)
        slugs = [tag["slug"] for tag in response.json()["data"]]
        self.assertEqual(slugs, ["public-tag"])

    def test_member_tag_list_for_start_discussion_excludes_staff_only_tags(self):
        response = self.client.get(
            "/api/tags",
            {"purpose": "start_discussion"},
            **self.auth_header(self.member),
        )

        self.assertEqual(response.status_code, 200, response.content)
        slugs = {tag["slug"] for tag in response.json()["data"]}
        self.assertEqual(slugs, {"public-tag", "members-tag"})

    def test_tag_detail_exposes_registered_resource_fields(self):
        with self.captureOnCommitCallbacks(execute=True):
            discussion = DiscussionService.create_discussion(
                title="标签详情附加字段",
                content="用于验证资源注册输出",
                user=self.admin,
                extension_payload=discussion_tags_payload([self.members_tag.id]),
            )

        response = self.client.get(
            f"/api/tags/{self.members_tag.id}",
            **self.auth_header(self.admin),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["can_start_discussion"])
        self.assertTrue(payload["can_reply"])
        self.assertEqual(payload["last_posted_discussion"]["id"], discussion.id)

    def test_tag_detail_supports_resource_field_selection(self):
        DiscussionService.create_discussion(
            title="标签字段裁剪",
            content="用于裁剪",
            user=self.admin,
            extension_payload=discussion_tags_payload([self.members_tag.id]),
        )

        response = self.client.get(
            f"/api/tags/{self.members_tag.id}",
            {"fields[tag]": "can_reply"},
            **self.auth_header(self.admin),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("can_reply", payload)
        self.assertNotIn("can_start_discussion", payload)
        self.assertNotIn("last_posted_discussion", payload)

    def test_tag_detail_supports_resource_include_for_last_posted_discussion(self):
        discussion = DiscussionService.create_discussion(
            title="标签 include 讨论",
            content="用于 include",
            user=self.admin,
            extension_payload=discussion_tags_payload([self.members_tag.id]),
        )
        TagService.refresh_tag_stats([self.members_tag.id])

        response = self.client.get(
            f"/api/tags/{self.members_tag.id}",
            {"fields[tag]": "can_reply", "include": "last_posted_discussion"},
            **self.auth_header(self.admin),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("can_reply", payload)
        self.assertIn("last_posted_discussion", payload)
        self.assertEqual(payload["last_posted_discussion"]["id"], discussion.id)

    def test_tag_detail_static_route_uses_resource_endpoint_mutator(self):
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
        for endpoint in tag_resource_endpoints():
            registry.register_endpoint(endpoint)
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="tag",
                endpoint="show",
                module_id="test",
                operation="mutate",
                mutator=mutate_endpoint,
            )
        )

        with patch("extensions.tags.backend.handlers.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                response = self.client.get(
                    f"/api/tags/{self.members_tag.id}",
                    **self.auth_header(self.admin),
                )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["mutated_by_resource_endpoint"])

    def test_guest_cannot_view_staff_tag_detail(self):
        response = self.client.get(f"/api/tags/{self.staff_tag.id}")

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("没有权限", response.json()["error"])

    def test_tag_read_endpoints_do_not_refresh_stats(self):
        with patch("extensions.tags.backend.handlers.TagService.refresh_tag_stats") as refresh_stats:
            list_response = self.client.get("/api/tags")
            popular_response = self.client.get("/api/tags/popular")

        self.assertEqual(list_response.status_code, 200, list_response.content)
        self.assertEqual(popular_response.status_code, 200, popular_response.content)
        refresh_stats.assert_not_called()

    def test_tag_list_reuses_forbidden_tag_context_for_children(self):
        Tag.objects.create(
            name="公开子标签",
            slug="public-child",
            parent=self.public_tag,
        )
        Tag.objects.create(
            name="内部子标签",
            slug="staff-child",
            parent=self.public_tag,
            view_scope=Tag.ACCESS_STAFF,
            start_discussion_scope=Tag.ACCESS_STAFF,
            reply_scope=Tag.ACCESS_STAFF,
        )

        with patch(
            "extensions.tags.backend.handlers.TagService.get_forbidden_tag_ids",
            wraps=TagService.get_forbidden_tag_ids,
        ) as get_forbidden_tag_ids:
            response = self.client.get("/api/tags", {"include_children": True})

        self.assertEqual(response.status_code, 200, response.content)
        public_tag = next(tag for tag in response.json()["data"] if tag["slug"] == "public-tag")
        self.assertEqual([tag["slug"] for tag in public_tag["children"]], ["public-child"])
        self.assertEqual(get_forbidden_tag_ids.call_count, 1)
