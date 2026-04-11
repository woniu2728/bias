import json

from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken

from apps.core.models import Setting
from apps.core.services import SearchService
from apps.core.websocket_auth import get_user_from_token
from apps.discussions.services import DiscussionService
from apps.users.models import Group, User


class ChineseSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="searcher",
            email="searcher@example.com",
            password="password123",
        )

    def test_chinese_query_matches_discussion_content(self):
        discussion = DiscussionService.create_discussion(
            title="无关标题",
            content="这里讨论中文分词搜索和数据库检索体验。",
            user=self.user,
        )

        discussions, total = SearchService.search_discussions("中文搜索")

        self.assertEqual(total, 1)
        self.assertEqual(discussions[0].id, discussion.id)

    def test_discussion_list_query_uses_chinese_content_search(self):
        discussion = DiscussionService.create_discussion(
            title="产品反馈",
            content="希望论坛原生支持中文搜索。",
            user=self.user,
        )

        discussions, total = DiscussionService.get_discussion_list(q="中文搜索")

        self.assertEqual(total, 1)
        self.assertEqual(discussions[0].id, discussion.id)

    def test_chinese_tokenizer_keeps_phrase_and_segments(self):
        tokens = SearchService.tokenize_query("中文搜索")

        self.assertIn("中文搜索", tokens)
        self.assertTrue({"中文", "搜索"}.intersection(tokens))


class WebSocketJwtAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="ws-user",
            email="ws-user@example.com",
            password="password123",
        )

    async def test_valid_token_resolves_user_for_websocket(self):
        token = str(RefreshToken.for_user(self.user).access_token)

        resolved_user = await get_user_from_token(token)

        self.assertEqual(resolved_user.id, self.user.id)

    async def test_invalid_token_returns_anonymous_user(self):
        resolved_user = await get_user_from_token("invalid-token")

        self.assertIsInstance(resolved_user, AnonymousUser)


class AdminSettingsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_settings_are_persisted(self):
        response = self.client.post(
            "/api/admin/settings",
            data=json.dumps({
                "forum_title": "中文社区",
                "show_language_selector": True,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.forum_title").value),
            "中文社区",
        )

        response = self.client.get(
            "/api/admin/settings",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["forum_title"], "中文社区")
        self.assertTrue(payload["show_language_selector"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_advanced_and_cache_endpoints_exist(self):
        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("cache_driver", response.json())

        response = self.client.post(
            "/api/admin/cache/clear",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["message"], "缓存已清除")


class AdminUserManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-user-mgr",
            email="admin-user-mgr@example.com",
            password="password123",
        )
        self.member_group = Group.objects.create(
            name="Member",
            name_singular="Member",
            name_plural="Members",
            color="#4d698e",
        )
        self.moderator_group = Group.objects.create(
            name="Moderator",
            name_singular="Moderator",
            name_plural="Moderators",
            color="#80349E",
        )
        self.user = User.objects.create_user(
            username="managed-user",
            email="managed@example.com",
            password="password123",
        )
        self.user.user_groups.add(self.member_group)

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_get_and_update_user(self):
        response = self.client.get(
            f"/api/admin/users/{self.user.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], "managed-user")
        self.assertEqual(len(response.json()["groups"]), 1)

        response = self.client.put(
            f"/api/admin/users/{self.user.id}",
            data=json.dumps({
                "username": "managed-user-updated",
                "email": "managed-updated@example.com",
                "display_name": "运营同学",
                "bio": "负责社区运营",
                "is_staff": True,
                "is_email_confirmed": True,
                "group_ids": [self.member_group.id, self.moderator_group.id],
                "suspended_until": "2030-01-02T03:04:05Z",
                "suspend_reason": "spam",
                "suspend_message": "请联系管理员处理",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["username"], "managed-user-updated")
        self.assertTrue(payload["is_staff"])
        self.assertTrue(payload["is_email_confirmed"])
        self.assertEqual(len(payload["groups"]), 2)

        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "managed-user-updated")
        self.assertEqual(self.user.email, "managed-updated@example.com")
        self.assertEqual(self.user.display_name, "运营同学")
        self.assertEqual(self.user.bio, "负责社区运营")
        self.assertTrue(self.user.is_staff)
        self.assertTrue(self.user.is_email_confirmed)
        self.assertEqual(self.user.suspend_reason, "spam")
        self.assertEqual(self.user.suspend_message, "请联系管理员处理")
        self.assertIsNotNone(self.user.suspended_until)
        self.assertGreater(self.user.suspended_until, timezone.now())
        self.assertEqual(
            set(self.user.user_groups.values_list("id", flat=True)),
            {self.member_group.id, self.moderator_group.id},
        )


class AdminGroupManagementApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-group-mgr",
            email="admin-group-mgr@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_create_and_update_group(self):
        response = self.client.post(
            "/api/admin/groups",
            data=json.dumps({
                "name": "Helpers",
                "name_singular": "Helper",
                "name_plural": "Helpers",
                "color": "#27ae60",
                "icon": "fas fa-hands-helping",
                "is_hidden": False,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        group_id = response.json()["id"]
        self.assertTrue(Group.objects.filter(id=group_id, name="Helpers").exists())

        response = self.client.put(
            f"/api/admin/groups/{group_id}",
            data=json.dumps({
                "name": "Support",
                "name_singular": "Support",
                "name_plural": "Support Team",
                "color": "#8e44ad",
                "icon": "fas fa-life-ring",
                "is_hidden": True,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["name"], "Support")
        self.assertTrue(payload["is_hidden"])

        group = Group.objects.get(id=group_id)
        self.assertEqual(group.name, "Support")
        self.assertEqual(group.name_plural, "Support Team")
        self.assertEqual(group.color, "#8e44ad")
        self.assertEqual(group.icon, "fas fa-life-ring")
        self.assertTrue(group.is_hidden)
