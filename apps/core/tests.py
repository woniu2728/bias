import json

from django.test import TestCase, override_settings
from ninja_jwt.tokens import RefreshToken

from apps.core.models import Setting
from apps.core.services import SearchService
from apps.discussions.services import DiscussionService
from apps.users.models import User


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
