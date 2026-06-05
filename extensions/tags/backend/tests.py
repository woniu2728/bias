import json

from django.core.management import call_command
from django.test import TestCase, override_settings
from ninja_jwt.tokens import RefreshToken
from io import StringIO
from unittest.mock import Mock, patch

from apps.discussions.services import DiscussionService
from apps.core.models import AuditLog
from apps.core.resource_registry import ResourceEndpointDefinition, ResourceRegistry
from apps.core.settings_service import clear_runtime_setting_caches
from apps.posts.models import Post
from apps.tags.models import DiscussionTag, Tag
from extensions.tags.backend.events import DiscussionTaggedEvent, TagStatsRefreshRequestedEvent
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


def discussion_resource_payload(*, title=None, content=None, tag_ids=None):
    attributes = {}
    if title is not None:
        attributes["title"] = title
    if content is not None:
        attributes["content"] = content

    payload = {"data": {"type": "discussion", "attributes": attributes}}
    if tag_ids is not None:
        payload["data"]["relationships"] = discussion_tags_payload(tag_ids)["data"]["relationships"]
    return payload


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

    def test_refresh_tag_stats_extension_command_repairs_all_tags(self):
        discussion = DiscussionService.create_discussion(
            title="命令刷新统计",
            content="命令刷新内容",
            user=self.user,
        )
        DiscussionTag.objects.create(discussion=discussion, tag=self.tag)
        Tag.objects.filter(id=self.tag.id).update(discussion_count=0)

        stdout = StringIO()
        call_command("extension_console", "tags.refresh_stats", stdout=stdout)
        self.tag.refresh_from_db()

        self.assertEqual(self.tag.discussion_count, 1)
        self.assertIn("已刷新全部标签统计", stdout.getvalue())

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_dispatch_refresh_tag_stats_queues_when_enabled(self):
        from extensions.tags.backend.tasks import refresh_tag_stats_task

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


class TagForumSettingsTests(TestCase):
    def setUp(self):
        clear_runtime_setting_caches()
        self.admin = User.objects.create_superuser(
            username="tag-forum-admin",
            email="tag-forum-admin@example.com",
            password="password123",
        )

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extension_detail_api_surfaces_registered_resources_for_tags_extension(self):
        response = self.client.get(
            "/api/admin/extensions/tags",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertGreaterEqual(payload["capability_summary"]["resource_field_count"], 1)
        self.assertTrue(any(item["module_id"] == "tags" for item in payload["resource_fields"]))
        self.assertTrue(
            any(
                item["module_id"] == "tags"
                and item["resource"] == "forum"
                and item["field"] == "tags"
                for item in payload["resource_fields"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "tags"
                and item["resource"] == "post"
                and item["relationship"] == "eventPostMentionsTags"
                for item in payload["resource_relationships"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "tags"
                and item["model"] == "Post"
                and item["name"] == "eventPostMentionsTags"
                for item in payload["model_relations"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "tags"
                and item["model"] == "Tag"
                and item["model_label"] == "tags.Tag"
                for item in payload["owned_models"]
            )
        )
        self.assertTrue(
            any(
                item["module_id"] == "tags"
                and item["model"] == "DiscussionTag"
                and item["model_label"] == "tags.DiscussionTag"
                for item in payload["owned_models"]
            )
        )
        self.assertGreaterEqual(payload["capability_summary"]["event_listener_count"], 1)
        self.assertTrue(
            any(
                item["event"] == "DiscussionTaggedEvent"
                and item["module_id"] == "tags"
                and item.get("source") == "runtime"
                for item in payload["event_listeners"]
            )
        )

    def test_public_forum_settings_expose_tags_forum_resource_fields(self):
        parent = Tag.objects.create(
            name="Announcements",
            slug="announcements",
            position=1,
        )
        Tag.objects.create(
            name="News",
            slug="news",
            parent=parent,
            position=1,
        )
        Tag.objects.create(
            name="Staff",
            slug="staff",
            view_scope=Tag.ACCESS_STAFF,
            position=2,
        )

        guest_response = self.client.get("/api/forum")
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        guest_payload = guest_response.json()
        tags_extension = next(item for item in guest_payload["enabled_extensions"] if item["id"] == "tags")
        self.assertEqual(tags_extension["frontend_forum_entry"], "extensions/tags/frontend/forum/index.js")
        self.assertTrue(
            any(
                route["path"] == "/tags"
                and route["name"] == "tags"
                and route["component"] == "TagsView"
                for route in tags_extension["frontend_routes"]
            )
        )
        self.assertFalse(guest_payload["can_bypass_tag_counts"])
        self.assertEqual([item["slug"] for item in guest_payload["tags"]], ["announcements"])
        self.assertEqual(guest_payload["tags"][0]["children"][0]["slug"], "news")

        staff_response = self.client.get("/api/forum", **self.auth_header())
        self.assertEqual(staff_response.status_code, 200, staff_response.content)
        staff_payload = staff_response.json()
        self.assertTrue(staff_payload["can_bypass_tag_counts"])
        self.assertEqual(
            [item["slug"] for item in staff_payload["tags"]],
            ["announcements", "staff"],
        )


class TagSearchApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tag-search-user",
            email="tag-search-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_search_api_hides_discussions_in_staff_only_tags(self):
        admin = User.objects.create_superuser(
            username="search-admin",
            email="search-admin@example.com",
            password="password123",
        )
        hidden_tag = Tag.objects.create(
            name="管理搜索区",
            slug="search-staff",
            view_scope=Tag.ACCESS_STAFF,
            start_discussion_scope=Tag.ACCESS_STAFF,
            reply_scope=Tag.ACCESS_STAFF,
        )
        DiscussionService.create_discussion(
            title="搜索内网讨论",
            content="这里有搜索关键字",
            user=admin,
            extension_payload=discussion_tags_payload([hidden_tag.id]),
        )

        guest_response = self.client.get("/api/search", {"q": "搜索", "type": "discussions"})
        self.assertEqual(guest_response.status_code, 200, guest_response.content)
        self.assertEqual(guest_response.json()["discussion_total"], 0)
        self.assertEqual(guest_response.json()["discussions"], [])

        admin_response = self.client.get(
            "/api/search",
            {"q": "搜索", "type": "discussions"},
            **self.auth_header(admin),
        )
        self.assertEqual(admin_response.status_code, 200, admin_response.content)
        self.assertGreaterEqual(admin_response.json()["discussion_total"], 1)

    def test_search_api_supports_registered_tag_filter_syntax(self):
        target_tag = Tag.objects.create(name="扩展搜索标签", slug="extension-search-tag")
        other_tag = Tag.objects.create(name="其他标签", slug="other-search-tag")
        matched = DiscussionService.create_discussion(
            title="模块搜索过滤命中",
            content="使用注册式过滤器检索标签。",
            user=self.user,
            extension_payload=discussion_tags_payload([target_tag.id]),
        )
        DiscussionService.create_discussion(
            title="模块搜索过滤未命中",
            content="同样包含搜索关键字，但标签不同。",
            user=self.user,
            extension_payload=discussion_tags_payload([other_tag.id]),
        )

        response = self.client.get(
            "/api/search",
            {"q": "搜索 tag:extension-search-tag", "type": "discussions"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["discussion_total"], 1)
        self.assertEqual([item["id"] for item in payload["discussions"]], [matched.id])

    def test_search_filters_api_exposes_registered_tag_filter_syntax(self):
        response = self.client.get("/api/search/filters", {"target": "discussions"})

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("tag:<slug>", {item["syntax"] for item in response.json()["filters"]})


class TagDiscussionForumApiTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="tag-discussion-author",
            email="tag-discussion-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.reader = User.objects.create_user(
            username="tag-discussion-reader",
            email="tag-discussion-reader@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.author).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_discussion_list_filters_by_tag_slug(self):
        life_tag = Tag.objects.create(name="生活", slug="life", color="#4d698e")
        tech_tag = Tag.objects.create(name="技术", slug="tech", color="#3498db")

        life_discussion = DiscussionService.create_discussion(
            title="Life discussion",
            content="Only belongs to life.",
            user=self.author,
            extension_payload=discussion_tags_payload([life_tag.id]),
        )
        DiscussionService.create_discussion(
            title="Tech discussion",
            content="Only belongs to tech.",
            user=self.author,
            extension_payload=discussion_tags_payload([tech_tag.id]),
        )

        response = self.client.get("/api/discussions/", {"tag": life_tag.slug})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["data"]), 1)
        self.assertEqual(payload["data"][0]["id"], life_discussion.id)
        self.assertEqual(payload["data"][0]["tags"][0]["slug"], life_tag.slug)

    def test_discussion_detail_field_selection_keeps_tags_relationship(self):
        tag = Tag.objects.create(name="字段裁剪标签", slug="field-selection-tag", color="#4d698e")
        discussion = DiscussionService.create_discussion(
            title="字段裁剪讨论",
            content="用于验证 fields",
            user=self.author,
            extension_payload=discussion_tags_payload([tag.id]),
        )

        response = self.client.get(
            f"/api/discussions/{discussion.id}",
            {"fields[discussion]": "can_reply"},
            **self.auth_header(self.author),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("tags", payload)
        self.assertEqual(payload["tags"][0]["slug"], tag.slug)

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
            extension_payload=discussion_tags_payload([staff_tag.id]),
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
            data=json.dumps(discussion_resource_payload(
                title="Should fail",
                content="Blocked by tag scope",
                tag_ids=[restricted_tag.id],
            )),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("没有权限", response.json()["error"])

    def test_cannot_reply_in_tag_without_reply_permission(self):
        member_group = Group.objects.create(name="TagReplyMember", color="#4d698e")
        Permission.objects.create(group=member_group, permission="discussion.reply")
        self.reader.user_groups.add(member_group)
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
            extension_payload=discussion_tags_payload([restricted_tag.id]),
        )

        response = self.client.post(
            f"/api/discussions/{restricted_discussion.id}/posts",
            data='{"content":"尝试回复"}',
            content_type="application/json",
            **self.auth_header(self.reader),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertIn("没有权限", response.json()["error"])

    def test_update_discussion_dispatches_tag_stats_refresh_request_event(self):
        tag_a = Tag.objects.create(name="标签A", slug="tag-a", color="#3498db")
        tag_b = Tag.objects.create(name="标签B", slug="tag-b", color="#2ecc71")
        discussion = DiscussionService.create_discussion(
            title="Tag stats event discussion",
            content="Initial post",
            user=self.author,
            extension_payload=discussion_tags_payload([tag_a.id]),
        )

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True):
                DiscussionService.update_discussion(
                    discussion_id=discussion.id,
                    user=self.author,
                    extension_payload=discussion_tags_payload([tag_b.id]),
                )

        events = [call.args[0] for call in mocked_bus.dispatch.call_args_list]
        tag_refresh_event = next(
            event for event in events if isinstance(event, TagStatsRefreshRequestedEvent)
        )
        self.assertEqual(tag_refresh_event.tag_ids, tuple(sorted((tag_a.id, tag_b.id))))

    def test_update_discussion_dispatches_discussion_tagged_event_with_all_affected_tag_ids(self):
        parent_tag = Tag.objects.create(name="父标签", slug="parent-tag", color="#3498db")
        old_child_tag = Tag.objects.create(
            name="旧子标签",
            slug="old-child-tag",
            color="#2ecc71",
            parent=parent_tag,
        )
        new_child_tag = Tag.objects.create(
            name="新子标签",
            slug="new-child-tag",
            color="#e67e22",
            parent=parent_tag,
        )
        discussion = DiscussionService.create_discussion(
            title="Discussion tagged event",
            content="Initial post",
            user=self.author,
            extension_payload=discussion_tags_payload([parent_tag.id, old_child_tag.id]),
        )

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True):
                DiscussionService.update_discussion(
                    discussion_id=discussion.id,
                    user=self.author,
                    extension_payload=discussion_tags_payload([parent_tag.id, new_child_tag.id]),
                )

        events = [call.args[0] for call in mocked_bus.dispatch.call_args_list]
        tagged_event = next(
            event for event in events if isinstance(event, DiscussionTaggedEvent)
        )
        self.assertEqual(
            tagged_event.tag_ids,
            tuple(sorted((parent_tag.id, old_child_tag.id, new_child_tag.id))),
        )

    def test_updating_discussion_tags_creates_discussion_tagged_event_post(self):
        member_group = Group.objects.create(name="DiscussionTagEditor", color="#4d698e")
        Permission.objects.create(group=member_group, permission="startDiscussion")
        Permission.objects.create(group=member_group, permission="discussion.editOwn")
        self.author.user_groups.add(member_group)

        original_tag = Tag.objects.create(name="后端", slug="backend", color="#2980b9")
        new_tag = Tag.objects.create(name="前端", slug="frontend", color="#e67e22")
        discussion = DiscussionService.create_discussion(
            title="Retag me",
            content="Original content",
            user=self.author,
            extension_payload=discussion_tags_payload([original_tag.id]),
        )

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.patch(
                f"/api/discussions/{discussion.id}",
                data=json.dumps(discussion_tags_payload([new_tag.id])),
                content_type="application/json",
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        tagged_post = Post.objects.get(discussion=discussion, number=2)
        self.assertEqual(tagged_post.type, "discussionTagged")

        posts_response = self.client.get(f"/api/discussions/{discussion.id}/posts")
        payload = posts_response.json()["data"]
        event_post = next(item for item in payload if item["id"] == tagged_post.id)
        self.assertEqual(
            event_post["event_data"],
            {
                "kind": "discussionTagged",
                "added_tags": [new_tag.name],
                "removed_tags": [original_tag.name],
            },
        )

    def test_delete_discussion_dispatches_tag_refresh_through_extension_lifecycle(self):
        admin = User.objects.create_superuser(
            username="discussion-delete-tag-admin",
            email="discussion-delete-tag-admin@example.com",
            password="password123",
        )
        tag = Tag.objects.create(name="删除刷新标签", slug="delete-refresh-tag", color="#4d698e")
        discussion = DiscussionService.create_discussion(
            title="Delete tagged discussion",
            content="Refresh tag stats after delete",
            user=admin,
            extension_payload=discussion_tags_payload([tag.id]),
        )

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True):
                DiscussionService.delete_discussion(discussion.id, admin)

        events = [call.args[0] for call in mocked_bus.dispatch.call_args_list]
        refresh_event = next(
            event for event in events if isinstance(event, TagStatsRefreshRequestedEvent)
        )
        self.assertEqual(refresh_event.tag_ids, (tag.id,))

    def test_cannot_create_discussion_with_secondary_tag_only(self):
        parent_tag = Tag.objects.create(name="开发", slug="dev")
        child_tag = Tag.objects.create(name="后端", slug="backend", parent=parent_tag)

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps(discussion_resource_payload(
                title="Invalid child only",
                content="Blocked by tag combination",
                tag_ids=[child_tag.id],
            )),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("次标签", response.json()["error"])

    def test_cannot_create_discussion_with_two_primary_tags(self):
        first_tag = Tag.objects.create(name="前端", slug="frontend")
        second_tag = Tag.objects.create(name="后端", slug="backend-main")

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps(discussion_resource_payload(
                title="Too many primary tags",
                content="Blocked by primary count",
                tag_ids=[first_tag.id, second_tag.id],
            )),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("主标签", response.json()["error"])

    def test_cannot_create_discussion_with_mismatched_parent_child_tags(self):
        first_tag = Tag.objects.create(name="前端", slug="frontend-main")
        second_tag = Tag.objects.create(name="后端", slug="backend-main")
        child_tag = Tag.objects.create(name="Vue", slug="vue-child", parent=first_tag)

        response = self.client.post(
            "/api/discussions/",
            data=json.dumps(discussion_resource_payload(
                title="Mismatched tags",
                content="Blocked by parent child mismatch",
                tag_ids=[second_tag.id, child_tag.id],
            )),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("主标签", response.json()["error"])


class AdminTagManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-tag-mgr",
            email="admin-tag@example.com",
            password="password123",
        )
        self.other_root_tag = Tag.objects.create(
            name="产品",
            slug="product",
            color="#e67e22",
            position=2,
        )
        self.parent_tag = Tag.objects.create(
            name="开发",
            slug="development",
            color="#4d698e",
            position=0,
        )
        self.child_tag = Tag.objects.create(
            name="后端",
            slug="backend",
            color="#0f766e",
            position=1,
            parent=self.parent_tag,
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_create_update_and_clear_tag_parent(self):
        response = self.client.post(
            "/api/admin/tags",
            data=json.dumps({
                "name": "接口设计",
                "slug": "api-design",
                "description": "讨论接口约定",
                "color": "#3c78d8",
                "icon": "fas fa-code",
                "parent_id": self.parent_tag.id,
                "position": 3,
                "is_hidden": True,
                "is_restricted": True,
                "view_scope": "members",
                "start_discussion_scope": "staff",
                "reply_scope": "members",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["slug"], "api-design")
        self.assertEqual(payload["parent_id"], self.parent_tag.id)
        self.assertEqual(payload["parent_name"], self.parent_tag.name)
        self.assertTrue(payload["is_hidden"])
        self.assertTrue(payload["is_restricted"])
        self.assertEqual(payload["view_scope"], "members")
        self.assertEqual(payload["start_discussion_scope"], "staff")
        self.assertEqual(payload["reply_scope"], "members")

        created_tag = Tag.objects.get(id=payload["id"])
        self.assertEqual(created_tag.parent_id, self.parent_tag.id)
        self.assertEqual(created_tag.view_scope, "members")

        response = self.client.put(
            f"/api/admin/tags/{created_tag.id}",
            data=json.dumps({
                "name": "接口规范",
                "slug": "api-guidelines",
                "parent_id": None,
                "position": 6,
                "is_hidden": False,
                "is_restricted": False,
                "view_scope": "public",
                "start_discussion_scope": "members",
                "reply_scope": "staff",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["name"], "接口规范")
        self.assertEqual(payload["slug"], "api-guidelines")
        self.assertIsNone(payload["parent_id"])
        self.assertIsNone(payload["parent_name"])
        self.assertFalse(payload["is_hidden"])
        self.assertFalse(payload["is_restricted"])
        self.assertEqual(payload["view_scope"], "public")
        self.assertEqual(payload["start_discussion_scope"], "members")
        self.assertEqual(payload["reply_scope"], "staff")

        created_tag.refresh_from_db()
        self.assertIsNone(created_tag.parent_id)
        self.assertEqual(created_tag.position, 6)
        self.assertEqual(created_tag.reply_scope, "staff")

    def test_admin_cannot_delete_tag_with_children(self):
        response = self.client.delete(
            f"/api/admin/tags/{self.parent_tag.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("子标签", response.json()["error"])

    def test_admin_cannot_create_grandchild_tag(self):
        response = self.client.post(
            "/api/admin/tags",
            data=json.dumps({
                "name": "Django ORM",
                "slug": "django-orm",
                "parent_id": self.child_tag.id,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("顶级标签", response.json()["error"])

    def test_admin_cannot_turn_parent_tag_with_children_into_child(self):
        response = self.client.put(
            f"/api/admin/tags/{self.parent_tag.id}",
            data=json.dumps({
                "parent_id": self.other_root_tag.id,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("已有子标签", response.json()["error"])

    def test_admin_cannot_set_posting_scopes_wider_than_view_scope(self):
        response = self.client.post(
            "/api/admin/tags",
            data=json.dumps({
                "name": "内部运营",
                "slug": "internal-ops",
                "view_scope": "staff",
                "start_discussion_scope": "members",
                "reply_scope": "staff",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("发帖权限不能比查看权限更宽松", response.json()["error"])

        response = self.client.put(
            f"/api/admin/tags/{self.parent_tag.id}",
            data=json.dumps({
                "view_scope": "members",
                "reply_scope": "public",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("回帖权限不能比查看权限更宽松", response.json()["error"])

    def test_admin_can_move_root_tag_up(self):
        response = self.client.post(
            f"/api/admin/tags/{self.other_root_tag.id}/move",
            data=json.dumps({"direction": "up"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["moved"])

        self.other_root_tag.refresh_from_db()
        self.parent_tag.refresh_from_db()
        self.assertEqual(self.other_root_tag.position, 0)
        self.assertEqual(self.parent_tag.position, 1)

    def test_admin_can_move_child_tag_within_same_parent(self):
        sibling_child = Tag.objects.create(
            name="前端",
            slug="frontend",
            color="#3c78d8",
            position=2,
            parent=self.parent_tag,
        )

        response = self.client.post(
            f"/api/admin/tags/{sibling_child.id}/move",
            data=json.dumps({"direction": "up"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["moved"])

        sibling_child.refresh_from_db()
        self.child_tag.refresh_from_db()
        self.parent_tag.refresh_from_db()

        self.assertEqual(sibling_child.position, 0)
        self.assertEqual(self.child_tag.position, 1)
        self.assertEqual(self.parent_tag.position, 0)

    @patch("extensions.tags.backend.admin_api.TagService.dispatch_refresh_tag_stats")
    def test_admin_can_refresh_tag_stats(self, dispatch_refresh_tag_stats):
        dispatch_refresh_tag_stats.return_value = {
            "mode": "sync",
            "tag_ids": None,
            "message": "标签统计已同步刷新",
        }

        response = self.client.post(
            "/api/admin/tags/stats/refresh",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        dispatch_refresh_tag_stats.assert_called_once_with()
        self.assertEqual(response.json()["message"], "标签统计已同步刷新")
        audit_log = AuditLog.objects.get(action="admin.tag.refresh_stats")
        self.assertEqual(audit_log.target_type, "tag")
        self.assertEqual(audit_log.data["mode"], "sync")
