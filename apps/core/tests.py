import json
import os
from pathlib import Path
import shutil
from subprocess import CompletedProcess
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command, CommandError
from django.db import OperationalError
from django.test import TestCase, override_settings
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken
from unittest.mock import patch

from apps.core.bootstrap_config import load_site_bootstrap, read_site_config
from apps.core.models import Setting
from apps.core.file_service import FileUploadService
from apps.core.online_service import OnlineUserService
from apps.core.release import build_git_command, ensure_release_versions_aligned
from apps.core.settings_service import clear_runtime_setting_caches, get_setting_group
from apps.core.services import SearchService
from apps.core.test_runner import BiasDiscoverRunner
from apps.core.websocket_auth import get_user_from_token
from apps.discussions.services import DiscussionService
from apps.notifications.models import Notification
from apps.posts.models import PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.users.models import Group, Permission, User


def make_workspace_temp_dir() -> Path:
    path = Path.cwd() / f"tmp-test-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


class ChineseSearchTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="searcher",
            email="searcher@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

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

    def test_search_api_all_returns_section_totals(self):
        DiscussionService.create_discussion(
            title="搜索讨论标题",
            content="这里有搜索内容",
            user=self.user,
        )
        discussion = DiscussionService.create_discussion(
            title="另一个搜索讨论",
            content="讨论里包含搜索关键字",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="这是一条搜索帖子内容",
            user=self.user,
        )
        User.objects.create_user(
            username="search-keyword",
            email="search-keyword@example.com",
            password="password123",
            bio="搜索用户简介",
            is_email_confirmed=True,
        )

        response = self.client.get(
            "/api/search",
            {"q": "搜索", "type": "all"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertGreaterEqual(payload["discussion_total"], 2)
        self.assertGreaterEqual(payload["post_total"], 1)
        self.assertGreaterEqual(payload["user_total"], 1)

    def test_search_api_posts_type_returns_pagination_metadata(self):
        discussion = DiscussionService.create_discussion(
            title="分页搜索讨论",
            content="讨论首帖包含分页搜索关键字",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="第一页搜索帖子内容",
            user=self.user,
        )
        PostService.create_post(
            discussion_id=discussion.id,
            content="第二页搜索帖子内容",
            user=self.user,
        )

        response = self.client.get("/api/search", {"q": "搜索", "type": "posts", "page": 1, "limit": 1})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["type"], "posts")
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["limit"], 1)
        self.assertGreaterEqual(payload["total"], 2)
        self.assertGreaterEqual(payload["post_total"], 2)
        self.assertEqual(len(payload["posts"]), 1)

    def test_search_api_users_type_returns_user_totals(self):
        unique_keyword = "独有用户搜索键12345"
        User.objects.create_user(
            username="isolated-user",
            email="search-user-only@example.com",
            password="password123",
            bio=f"这是一个{unique_keyword}",
            is_email_confirmed=True,
        )

        response = self.client.get(
            "/api/search",
            {"q": unique_keyword, "type": "users"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["type"], "users")
        self.assertEqual(payload["user_total"], 1)
        self.assertEqual(payload["total"], 1)
        self.assertEqual(len(payload["users"]), 1)
        self.assertEqual(payload["users"][0]["username"], "isolated-user")

    def test_search_api_users_type_requires_search_permission(self):
        restricted_user = User.objects.create_user(
            username="search-no-user-permission",
            email="search-no-user-permission@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        restricted_group = Group.objects.create(name="NoUserSearch", color="#95a5a6")
        restricted_user.user_groups.add(restricted_group)

        response = self.client.get(
            "/api/search",
            {"q": "搜索", "type": "users"},
            **self.auth_header(restricted_user),
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限搜索用户")

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
            tag_ids=[hidden_tag.id],
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

    def test_search_discussions_does_not_fetch_first_post_per_result(self):
        DiscussionService.create_discussion(
            title="搜索摘要优化一",
            content="第一条摘要内容",
            user=self.user,
        )
        DiscussionService.create_discussion(
            title="搜索摘要优化二",
            content="第二条摘要内容",
            user=self.user,
        )

        with patch("apps.core.services.Post.objects.get", side_effect=AssertionError("不应逐条 get 首帖")):
            discussions, total = SearchService.search_discussions("搜索摘要优化", user=self.user)

        self.assertEqual(total, 2)
        self.assertEqual(len(discussions), 2)
        self.assertTrue(all(discussion.excerpt for discussion in discussions))

    def test_search_api_all_reuses_single_search_context(self):
        DiscussionService.create_discussion(
            title="上下文复用搜索",
            content="上下文复用内容",
            user=self.user,
        )

        with patch("apps.core.api.SearchService.build_search_context", wraps=SearchService.build_search_context) as build_context:
            response = self.client.get(
                "/api/search",
                {"q": "上下文复用", "type": "all"},
                **self.auth_header(),
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(build_context.call_count, 1)


class TestRunnerTests(TestCase):
    def test_default_runner_uses_app_test_modules_without_explicit_labels(self):
        runner = BiasDiscoverRunner()
        labels = [
            f"{app}.tests"
            for app in settings.INSTALLED_APPS
            if app.startswith("apps.")
        ]

        suite = runner.build_suite([])

        discovered = set()
        stack = [suite]
        while stack:
            item = stack.pop()
            if hasattr(item, "__iter__") and not hasattr(item, "_testMethodName"):
                stack.extend(list(item))
                continue
            module_name = item.__class__.__module__.split(".")[0:3]
            discovered.add(".".join(module_name[:2]) + ".tests")

        for label in labels:
            self.assertIn(label, discovered)


@override_settings(CACHES={
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'bias-online-tests',
    }
})
class OnlineUserServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="online-user",
            email="online-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.other_user = User.objects.create_user(
            username="online-other",
            email="online-other@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_multiple_connections_only_go_offline_after_last_disconnect(self):
        self.assertTrue(OnlineUserService.mark_user_online(self.user.id))
        self.assertFalse(OnlineUserService.mark_user_online(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        self.assertFalse(OnlineUserService.mark_user_offline(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        self.assertTrue(OnlineUserService.mark_user_offline(self.user.id))
        self.assertEqual(OnlineUserService.get_online_user_ids(), [])

    def test_touch_extends_presence_ttl(self):
        with patch.object(OnlineUserService, "_now_ts", return_value=100):
            OnlineUserService.mark_user_online(self.user.id)

        with patch.object(OnlineUserService, "_now_ts", return_value=150):
            self.assertTrue(OnlineUserService.touch_user_online(self.user.id))

        with patch.object(OnlineUserService, "_now_ts", return_value=200):
            self.assertEqual(OnlineUserService.get_online_user_ids(), [self.user.id])

        with patch.object(OnlineUserService, "_now_ts", return_value=241):
            self.assertEqual(OnlineUserService.get_online_user_ids(), [])

    def test_get_online_users_returns_only_marked_users(self):
        OnlineUserService.mark_user_online(self.other_user.id)
        OnlineUserService.mark_user_online(self.user.id)

        users = OnlineUserService.get_online_users(limit=10)

        self.assertEqual({item["id"] for item in users}, {self.user.id, self.other_user.id})
        self.assertTrue(all("username" in item for item in users))


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

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_settings_are_persisted(self):
        response = self.client.post(
            "/api/admin/settings",
            data=json.dumps({
                "forum_title": "中文社区",
                "seo_title": "中文社区 - 技术论坛",
                "seo_description": "这是一个专注 Django 与 Vue 的中文社区。",
                "seo_keywords": "Python, Django, Vue",
                "seo_robots_index": False,
                "seo_robots_follow": True,
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
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.seo_title").value),
            "中文社区 - 技术论坛",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="basic.seo_robots_index").value),
            False,
        )


    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_advanced_and_cache_endpoints_exist(self):
        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("cache_driver", payload)
        self.assertIn("storage_driver", payload)

        response = self.client.post(
            "/api/admin/cache/clear",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["message"], "缓存已清除")

    def test_advanced_settings_persist_storage_config(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "storage_driver": "r2",
                "storage_attachments_dir": "uploads/files",
                "storage_local_path": "custom-media",
                "storage_r2_bucket": "forum-assets",
                "storage_r2_endpoint": "https://example.r2.cloudflarestorage.com",
                "storage_r2_public_url": "https://cdn.example.com",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.storage_driver").value),
            "r2",
        )

        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["storage_driver"], "r2")
        self.assertEqual(payload["storage_attachments_dir"], "uploads/files")
        self.assertEqual(payload["storage_r2_bucket"], "forum-assets")
        self.assertEqual(payload["storage_r2_public_url"], "https://cdn.example.com")

    def test_advanced_settings_persist_human_verification_config(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "auth_human_verification_provider": "turnstile",
                "auth_turnstile_site_key": "site-key",
                "auth_turnstile_secret_key": "secret-key",
                "auth_human_verification_login_enabled": True,
                "auth_human_verification_register_enabled": False,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.auth_human_verification_provider").value),
            "turnstile",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.auth_turnstile_site_key").value),
            "site-key",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="advanced.auth_human_verification_register_enabled").value),
            False,
        )

        response = self.client.get(
            "/api/admin/advanced",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["auth_human_verification_provider"], "turnstile")
        self.assertEqual(payload["auth_turnstile_site_key"], "site-key")
        self.assertEqual(payload["auth_turnstile_secret_key"], "secret-key")
        self.assertTrue(payload["auth_human_verification_login_enabled"])
        self.assertFalse(payload["auth_human_verification_register_enabled"])

    def test_debug_mode_setting_is_read_only_runtime_value(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({
                "debug_mode": not settings.DEBUG,
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["debug_mode"], settings.DEBUG)
        self.assertFalse(Setting.objects.filter(key="advanced.debug_mode").exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_settings_affect_test_email_sender(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_driver": "smtp",
                "mail_from": "Bias Mailer <service@example.com>",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(response.json()["to_email"], "admin@example.com")
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertEqual(mail.outbox[0].from_email, "Bias Mailer <service@example.com>")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_test_endpoint_sends_to_current_admin_email(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "admin@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_test_endpoint_accepts_custom_recipient(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            data=json.dumps({"to_email": "real-recipient@example.com"}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "real-recipient@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["real-recipient@example.com"])

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_mail_test_endpoint_uses_saved_test_recipient(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
                "mail_test_recipient": "saved-recipient@example.com",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/admin/mail/test",
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "saved-recipient@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["saved-recipient@example.com"])

    def test_mail_settings_persist_mail_from_and_saved_test_recipient(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_driver": "smtp",
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_test_recipient": "saved-recipient@example.com",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["mail_from"], "Bias Mailer <service@example.com>")

        response = self.client.get(
            "/api/admin/mail",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["mail_from"], "Bias Mailer <service@example.com>")
        self.assertEqual(response.json()["mail_test_recipient"], "saved-recipient@example.com")
        self.assertEqual(response.json()["test_to_email"], "saved-recipient@example.com")

    def test_mail_settings_expose_default_templates(self):
        response = self.client.get(
            "/api/admin/mail",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("{{ site_name }}", payload["mail_verification_subject"])
        self.assertIn("{{ verification_url }}", payload["mail_verification_text"])
        self.assertIn("{{ reset_url }}", payload["mail_password_reset_html"])
        self.assertTrue(payload["mail_from"])
        self.assertEqual(list(payload["drivers"].keys()), ["smtp"])
        self.assertEqual(payload["driver_options"], [{"value": "smtp", "label": "SMTP"}])
        self.assertEqual(payload["mail_host"], "smtp.gmail.com")
        self.assertEqual(payload["mail_encryption"], "tls")
        self.assertIn("sending", payload)

    def test_smtp_driver_requires_host_before_sending(self):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
                "mail_host": "",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertFalse(payload["sending"])
        self.assertIn("mail_host", payload["errors"])

    def test_public_forum_settings_include_basic_and_appearance(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("运行时论坛名称")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_title",
            defaults={"value": json.dumps("运行时 SEO 标题")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_description",
            defaults={"value": json.dumps("运行时 SEO 描述")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_keywords",
            defaults={"value": json.dumps("Python, Django, Vue")},
        )
        Setting.objects.update_or_create(
            key="basic.seo_robots_index",
            defaults={"value": json.dumps(False)},
        )
        Setting.objects.update_or_create(
            key="basic.seo_robots_follow",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="basic.welcome_title",
            defaults={"value": json.dumps("欢迎来到运行时论坛")},
        )
        Setting.objects.update_or_create(
            key="appearance.primary_color",
            defaults={"value": json.dumps("#123456")},
        )
        Setting.objects.update_or_create(
            key="appearance.logo_url",
            defaults={"value": json.dumps("/media/runtime-logo.png")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_provider",
            defaults={"value": json.dumps("turnstile")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_turnstile_site_key",
            defaults={"value": json.dumps("public-site-key")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_turnstile_secret_key",
            defaults={"value": json.dumps("private-secret-key")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_login_enabled",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_register_enabled",
            defaults={"value": json.dumps(False)},
        )

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["forum_title"], "运行时论坛名称")
        self.assertEqual(payload["seo_title"], "运行时 SEO 标题")
        self.assertEqual(payload["seo_description"], "运行时 SEO 描述")
        self.assertEqual(payload["seo_keywords"], "Python, Django, Vue")
        self.assertFalse(payload["seo_robots_index"])
        self.assertTrue(payload["seo_robots_follow"])
        self.assertEqual(payload["welcome_title"], "欢迎来到运行时论坛")
        self.assertEqual(payload["primary_color"], "#123456")
        self.assertEqual(payload["logo_url"], "/media/runtime-logo.png")
        self.assertEqual(payload["auth_human_verification_provider"], "turnstile")
        self.assertEqual(payload["auth_turnstile_site_key"], "public-site-key")
        self.assertTrue(payload["auth_human_verification_login_enabled"])
        self.assertFalse(payload["auth_human_verification_register_enabled"])
        self.assertNotIn("auth_turnstile_secret_key", payload)

    @patch("apps.core.admin_api.FileUploadService.upload_site_asset")
    def test_admin_can_upload_appearance_logo(self, upload_site_asset):
        upload_site_asset.return_value = (
            "/media/appearance/logo/site-logo.png",
            {
                "original_name": "site-logo.png",
                "size": 1234,
                "mime_type": "image/png",
            },
        )
        file = SimpleUploadedFile("site-logo.png", b"png-data", content_type="image/png")

        response = self.client.post(
            "/api/admin/appearance/upload?target=logo",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["target"], "logo")
        self.assertEqual(payload["url"], "/media/appearance/logo/site-logo.png")
        upload_site_asset.assert_called_once()

    def test_admin_appearance_upload_rejects_invalid_target(self):
        file = SimpleUploadedFile("site-logo.png", b"png-data", content_type="image/png")

        response = self.client.post(
            "/api/admin/appearance/upload?target=avatar",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "仅支持上传 logo 或 favicon")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_cache_lifetime_controls_public_forum_settings_cache(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 A")},
        )
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(60)},
        )
        clear_runtime_setting_caches()

        first_response = self.client.get("/api/forum")
        self.assertEqual(first_response.status_code, 200, first_response.content)
        self.assertEqual(first_response.json()["forum_title"], "缓存标题 A")

        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 B")},
        )

        cached_response = self.client.get("/api/forum")
        self.assertEqual(cached_response.status_code, 200, cached_response.content)
        self.assertEqual(cached_response.json()["forum_title"], "缓存标题 A")

        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(0)},
        )
        clear_runtime_setting_caches()

        uncached_response = self.client.get("/api/forum")
        self.assertEqual(uncached_response.status_code, 200, uncached_response.content)
        self.assertEqual(uncached_response.json()["forum_title"], "缓存标题 B")

        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("缓存标题 C")},
        )
        direct_response = self.client.get("/api/forum")
        self.assertEqual(direct_response.status_code, 200, direct_response.content)
        self.assertEqual(direct_response.json()["forum_title"], "缓存标题 C")

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_maintenance_mode_blocks_public_api_but_keeps_admin_paths_available(self):
        Setting.objects.update_or_create(
            key="advanced.maintenance_mode",
            defaults={"value": json.dumps(True)},
        )
        Setting.objects.update_or_create(
            key="advanced.maintenance_message",
            defaults={"value": json.dumps("站点维护中，请稍后回来。")},
        )
        clear_runtime_setting_caches()

        public_settings_response = self.client.get("/api/forum")
        self.assertEqual(public_settings_response.status_code, 200, public_settings_response.content)
        self.assertTrue(public_settings_response.json()["maintenance_mode"])
        self.assertEqual(public_settings_response.json()["maintenance_message"], "站点维护中，请稍后回来。")

        blocked_response = self.client.get("/api/search", {"q": "维护"})
        self.assertEqual(blocked_response.status_code, 503, blocked_response.content)
        self.assertEqual(blocked_response.json()["error"], "站点维护中，请稍后回来。")
        self.assertTrue(blocked_response.json()["maintenance"])

        admin_response = self.client.get("/api/admin/advanced", **self.auth_header())
        self.assertEqual(admin_response.status_code, 200, admin_response.content)

        me_response = self.client.get("/api/users/me", **self.auth_header())
        self.assertEqual(me_response.status_code, 200, me_response.content)
        self.assertTrue(me_response.json()["is_staff"])

    @override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
    def test_log_queries_setting_logs_sql_statements(self):
        Setting.objects.update_or_create(
            key="advanced.cache_lifetime",
            defaults={"value": json.dumps(0)},
        )
        Setting.objects.update_or_create(
            key="advanced.log_queries",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        with self.assertLogs("bias.sql", level="INFO") as captured:
            response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        joined_output = "\n".join(captured.output)
        self.assertIn("/api/forum", joined_output)
        self.assertIn("total_queries=", joined_output)
        self.assertIn("SELECT", joined_output.upper())

    def test_markdown_preview_endpoint_returns_rendered_html(self):
        alice = User.objects.create_user(
            username="alice",
            email="alice@example.com",
            password="password123",
            is_email_confirmed=True,
        )

        response = self.client.post(
            "/api/preview",
            data=json.dumps({
                "content": "# 标题\n\n你好 @alice\n\n[官网](https://example.com)"
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        html = response.json()["html"]
        self.assertIn("<h1", html)
        self.assertIn(f'href="/u/{alice.id}"', html)
        self.assertIn(">官网</a>", html)
        self.assertIn('target="_blank"', html)

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

        suspended_notification = Notification.objects.get(
            user=self.user,
            type="userSuspended",
            subject_id=self.user.id,
        )
        self.assertEqual(suspended_notification.from_user_id, self.admin.id)
        self.assertEqual(suspended_notification.data["suspend_reason"], "spam")
        self.assertEqual(suspended_notification.data["suspend_message"], "请联系管理员处理")

    def test_admin_unsuspending_user_creates_recovery_notification(self):
        self.user.suspended_until = timezone.now() + timedelta(days=2)
        self.user.suspend_reason = "temporary"
        self.user.suspend_message = "请等待处理"
        self.user.save(update_fields=["suspended_until", "suspend_reason", "suspend_message"])

        response = self.client.put(
            f"/api/admin/users/{self.user.id}",
            data=json.dumps({
                "suspended_until": None,
                "suspend_reason": "",
                "suspend_message": "",
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_suspended)

        unsuspended_notification = Notification.objects.get(
            user=self.user,
            type="userUnsuspended",
            subject_id=self.user.id,
        )
        self.assertEqual(unsuspended_notification.from_user_id, self.admin.id)

    def test_admin_can_delete_user(self):
        response = self.client.delete(
            f"/api/admin/users/{self.user.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())

    def test_admin_cannot_delete_self(self):
        response = self.client.delete(
            f"/api/admin/users/{self.admin.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不能删除当前登录的管理员账号")
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())


class AdminDashboardStatsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="dashboard-admin",
            email="dashboard-admin@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_stats_returns_python_runtime_status(self):
        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["runtimeName"], "Python")
        self.assertTrue(payload["pythonVersion"])
        self.assertTrue(payload["djangoVersion"])
        self.assertIn("SQLite", payload["databaseLabel"])
        self.assertEqual(payload["cacheDriver"], "内存")
        self.assertEqual(payload["realtimeDriver"], "In-memory")
        self.assertEqual(payload["queueLabel"], "同步执行")
        self.assertFalse(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "disabled")
        self.assertFalse(payload["queueWorkerAvailable"])
        self.assertEqual(payload["queueMetrics"]["enqueued_count"], 0)
        self.assertEqual(payload["queueMetrics"]["sync_count"], 0)
        self.assertEqual(payload["queueMetrics"]["fallback_count"], 0)
        self.assertFalse(payload["redisEnabled"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://localhost:6379/0"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [("localhost", 6379)]}}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    @patch("apps.core.admin_api.QueueService.get_worker_status")
    def test_admin_stats_marks_redis_and_queue_status(self, get_worker_status):
        get_worker_status.return_value = {
            "status": "available",
            "label": "2 个 worker 在线",
            "available": True,
            "worker_count": 2,
            "message": "Celery worker 可用。",
        }
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["cacheDriver"], "Redis")
        self.assertEqual(payload["realtimeDriver"], "Redis")
        self.assertEqual(payload["queueDriver"], "redis")
        self.assertEqual(payload["queueLabel"], "Redis")
        self.assertTrue(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "available")
        self.assertEqual(payload["queueWorkerLabel"], "2 个 worker 在线")
        self.assertTrue(payload["queueWorkerAvailable"])
        self.assertEqual(payload["queueWorkerCount"], 2)
        self.assertTrue(payload["redisEnabled"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "dashboard-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="redis://localhost:6379/1",
    )
    def test_admin_stats_does_not_mark_redis_enabled_from_idle_broker_config(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(False)},
        )
        Setting.objects.update_or_create(
            key="advanced.queue_driver",
            defaults={"value": json.dumps("redis")},
        )
        clear_runtime_setting_caches()

        response = self.client.get("/api/admin/stats", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["cacheDriver"], "内存")
        self.assertEqual(payload["realtimeDriver"], "In-memory")
        self.assertEqual(payload["queueDriver"], "redis")
        self.assertEqual(payload["queueLabel"], "同步执行")
        self.assertFalse(payload["queueEnabled"])
        self.assertEqual(payload["queueWorkerStatus"], "disabled")
        self.assertFalse(payload["queueWorkerAvailable"])
        self.assertFalse(payload["redisEnabled"])

    @override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "queue-reset-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
    )
    def test_admin_can_reset_queue_metrics(self):
        from apps.core.queue_service import QueueService

        class DummyTask:
            name = "tests.reset_metric_task"

            def delay(self):
                raise AssertionError("queue should be disabled")

        QueueService.reset_metrics()
        QueueService.dispatch_celery_task(DummyTask(), fallback=lambda: "done")
        self.assertEqual(QueueService.get_metrics()["sync_count"], 1)

        response = self.client.post("/api/admin/queue/metrics/reset", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["message"], "队列运行指标已重置")
        self.assertEqual(payload["metrics"]["sync_count"], 0)
        self.assertEqual(payload["metrics"]["enqueued_count"], 0)
        self.assertEqual(payload["metrics"]["fallback_count"], 0)

    def test_non_staff_cannot_reset_queue_metrics(self):
        member = User.objects.create_user(
            username="queue-reset-member",
            email="queue-reset-member@example.com",
            password="password123",
        )
        token = RefreshToken.for_user(member).access_token

        response = self.client.post(
            "/api/admin/queue/metrics/reset",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403, response.content)


class QueueServiceTests(TestCase):
    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def test_queue_worker_status_reports_disabled_when_queue_is_off(self):
        from apps.core.queue_service import QueueService

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "disabled")
        self.assertFalse(status["available"])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    def test_queue_worker_status_reports_available_workers(self, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        inspect.return_value.ping.return_value = {
            "celery@worker-a": {"ok": "pong"},
            "celery@worker-b": {"ok": "pong"},
        }

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "available")
        self.assertTrue(status["available"])
        self.assertEqual(status["worker_count"], 2)

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    @patch("config.celery.app.control.inspect")
    def test_queue_worker_status_reports_unavailable_without_ping_response(self, inspect):
        from apps.core.queue_service import QueueService

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        inspect.return_value.ping.return_value = None

        status = QueueService.get_worker_status()

        self.assertEqual(status["status"], "unavailable")
        self.assertFalse(status["available"])
        self.assertEqual(status["worker_count"], 0)

    def test_queue_metrics_record_sync_dispatch(self):
        from apps.core.queue_service import QueueService

        class DummyTask:
            name = "tests.sync_task"

            def delay(self):
                raise AssertionError("queue should be disabled")

        QueueService.reset_metrics()
        result = QueueService.dispatch_celery_task(DummyTask(), fallback=lambda: "done")
        metrics = QueueService.get_metrics()

        self.assertEqual(result, "done")
        self.assertEqual(metrics["sync_count"], 1)
        self.assertEqual(metrics["enqueued_count"], 0)
        self.assertEqual(metrics["fallback_count"], 0)
        self.assertEqual(metrics["last_task"], "tests.sync_task")

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_queue_metrics_record_enqueue_and_fallback(self):
        from apps.core.queue_service import QueueService

        class SuccessfulTask:
            name = "tests.successful_task"

            def delay(self):
                return "queued"

        class FailingTask:
            name = "tests.failing_task"

            def delay(self):
                raise RuntimeError("queue down")

        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()
        QueueService.reset_metrics()

        self.assertEqual(
            QueueService.dispatch_celery_task(SuccessfulTask(), fallback=lambda: "sync"),
            "queued",
        )
        self.assertEqual(
            QueueService.dispatch_celery_task(FailingTask(), fallback=lambda: "fallback"),
            "fallback",
        )
        metrics = QueueService.get_metrics()

        self.assertEqual(metrics["enqueued_count"], 1)
        self.assertEqual(metrics["fallback_count"], 1)
        self.assertEqual(metrics["sync_count"], 0)
        self.assertEqual(metrics["last_task"], "tests.failing_task")
        self.assertEqual(metrics["last_error"], "queue down")


class ComposerUploadApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="composer-user",
            email="composer@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @patch("apps.core.api.FileUploadService.upload_attachment")
    def test_authenticated_user_can_upload_attachment(self, upload_attachment):
        upload_attachment.return_value = (
            f"/media/attachments/{self.user.id}/guide.pdf",
            {
                "original_name": "guide.pdf",
                "size": 128,
                "mime_type": "application/pdf",
                "hash": "abc123",
            },
        )
        file = SimpleUploadedFile("guide.pdf", b"dummy-pdf", content_type="application/pdf")

        response = self.client.post(
            "/api/uploads",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["url"], f"/media/attachments/{self.user.id}/guide.pdf")
        self.assertEqual(payload["original_name"], "guide.pdf")
        self.assertEqual(payload["mime_type"], "application/pdf")
        self.assertFalse(payload["is_image"])
        upload_attachment.assert_called_once()

    @patch("apps.core.api.FileUploadService.upload_attachment")
    def test_upload_image_marks_response_as_image(self, upload_attachment):
        upload_attachment.return_value = (
            f"/media/attachments/{self.user.id}/photo.png",
            {
                "original_name": "photo.png",
                "size": 256,
                "mime_type": "image/png",
                "hash": "def456",
            },
        )
        file = SimpleUploadedFile("photo.png", b"png-data", content_type="image/png")

        response = self.client.post(
            "/api/uploads",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["is_image"])

    def test_upload_requires_file(self):
        response = self.client.post(
            "/api/uploads",
            {},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "请选择要上传的文件")

    @patch("apps.core.api.FileUploadService.upload_attachment")
    def test_upload_validation_error_returns_400(self, upload_attachment):
        upload_attachment.side_effect = ValueError("不支持的文件格式")
        file = SimpleUploadedFile("virus.exe", b"bad", content_type="application/octet-stream")

        response = self.client.post(
            "/api/uploads",
            {"file": file},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不支持的文件格式")


class InstallForumCommandTests(TestCase):
    def _success_result(self, args):
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_writes_site_config_and_invokes_manage_steps(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "sqlite",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--admin-username",
                        "forum-admin",
                        "--admin-email",
                        "forum-admin@example.com",
                        "--admin-password",
                        "password123",
                        "--non-interactive",
                    )

            self.assertTrue(config_path.exists())
            config = read_site_config(config_path)
            self.assertEqual(config.database_mode, "sqlite")
            self.assertEqual(config.sqlite_name, "db.sqlite3")
            self.assertFalse(config.use_redis)
            self.assertEqual(config.resolved_frontend_url(), "http://localhost:5173")
            self.assertTrue(config.secret_key)
            self.assertTrue(config.jwt_secret_key)

            self.assertEqual(mock_run_manage_py.call_count, 4)
            invoked_steps = [call.args[0] for call in mock_run_manage_py.call_args_list]
            self.assertEqual(
                invoked_steps,
                [
                    ["init_groups"],
                    ["sync_forum_version"],
                    ["collectstatic", "--noinput"],
                    [
                        "ensure_admin",
                        "--username",
                        "forum-admin",
                        "--email",
                        "forum-admin@example.com",
                        "--password",
                        "password123",
                    ],
                ],
            )

            first_args, first_env = mock_run_manage_py.call_args_list[0].args
            self.assertEqual(first_args, ["init_groups"])
            self.assertEqual(
                first_env["BIAS_SITE_CONFIG"],
                str(config_path),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_writes_postgres_site_config_values(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--skip-admin",
                        "--db-name",
                        "community",
                        "--db-user",
                        "community_user",
                        "--db-password",
                        "community_pass",
                        "--db-host",
                        "db.internal",
                        "--db-port",
                        "5433",
                        "--frontend-url",
                        "http://forum.example.com",
                        "--non-interactive",
                    )

            self.assertTrue(config_path.exists())
            config = read_site_config(config_path)
            self.assertEqual(config.database_mode, "postgres")
            self.assertFalse(config.debug)
            self.assertTrue(config.use_redis)
            self.assertEqual(config.db_name, "community")
            self.assertEqual(config.db_user, "community_user")
            self.assertEqual(config.db_password, "community_pass")
            self.assertEqual(config.db_host, "db.internal")
            self.assertEqual(config.db_port, "5433")
            self.assertEqual(config.resolved_frontend_url(), "http://forum.example.com")

            self.assertEqual(mock_run_manage_py.call_count, 3)
            group_args, group_env = mock_run_manage_py.call_args_list[0].args
            self.assertEqual(group_args, ["init_groups"])
            self.assertEqual(group_env["BIAS_SITE_CONFIG"], str(config_path))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_command_allows_explicit_redis_override(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(os.environ, {}, clear=False):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "sqlite",
                        "--redis",
                        "on",
                        "--redis-host",
                        "cache.internal",
                        "--redis-port",
                        "6380",
                        "--redis-db",
                        "5",
                        "--config",
                        str(config_path),
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )

            config = read_site_config(config_path)
            self.assertTrue(config.use_redis)
            self.assertEqual(config.redis_host, "cache.internal")
            self.assertEqual(config.redis_port, "6380")
            self.assertEqual(config.redis_db, "5")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.install_forum.assert_database_connection")
    @patch("apps.core.management.commands.install_forum.run_manage_py")
    def test_install_forum_overwrite_preserves_existing_secrets(self, mock_run_manage_py, mock_assert_database_connection):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_assert_database_connection.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "secret_key": "secret-1",
                        "jwt_secret_key": "jwt-secret-1",
                        "database_mode": "postgres",
                        "db_name": "bias",
                        "db_user": "postgres",
                        "db_password": "postgres",
                        "db_host": "db",
                        "db_port": "5432",
                        "use_redis": True,
                        "redis_host": "redis",
                        "redis_port": "6379",
                        "redis_db": "0",
                        "site_domains": ["old.example.com"],
                        "site_scheme": "https",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=Path(temp_dir)):
                call_command(
                    "install_forum",
                    "--config",
                    str(config_path),
                    "--site-domains",
                    "bias.chat,www.bias.chat",
                    "--skip-migrate",
                    "--skip-admin",
                    "--overwrite",
                    "--non-interactive",
                )

            config = read_site_config(config_path)
            self.assertEqual(config.secret_key, "secret-1")
            self.assertEqual(config.jwt_secret_key, "jwt-secret-1")
            self.assertEqual(config.site_domains, ["bias.chat", "www.bias.chat"])
            self.assertEqual(config.db_host, "db")
            self.assertEqual(config.resolved_frontend_url(), "https://bias.chat")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_install_forum_validates_postgres_required_fields(self):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaisesMessage(
                CommandError,
                "PostgreSQL 模式缺少必要配置: db_name, db_user, db_password",
            ):
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--db-host",
                        "db.internal",
                        "--db-port",
                        "5432",
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=True)
    def test_install_forum_surfaces_old_volume_hint_when_role_missing(self, mock_running_in_docker, mock_connect):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  role "woniu" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(
                os.environ,
                {
                    "DB_NAME": "bias",
                    "DB_USER": "woniu",
                    "DB_PASSWORD": "woniu@woniu",
                },
                clear=False,
            ):
                with self.assertRaisesMessage(CommandError, "Docker 复用了旧的 postgres_data 卷"):
                    with override_settings(BASE_DIR=Path(temp_dir)):
                        call_command(
                            "install_forum",
                            "--database",
                            "postgres",
                            "--config",
                            str(config_path),
                            "--db-host",
                            "db",
                            "--db-port",
                            "5432",
                            "--skip-migrate",
                            "--skip-admin",
                            "--non-interactive",
                        )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=False)
    def test_install_forum_surfaces_native_postgres_hint_when_role_missing(
        self,
        mock_running_in_docker,
        mock_connect,
    ):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  role "bias_user" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaises(CommandError) as captured:
                with override_settings(BASE_DIR=Path(temp_dir)):
                    call_command(
                        "install_forum",
                        "--database",
                        "postgres",
                        "--config",
                        str(config_path),
                        "--db-name",
                        "bias",
                        "--db-user",
                        "bias_user",
                        "--db-password",
                        "secret",
                        "--db-host",
                        "127.0.0.1",
                        "--db-port",
                        "5432",
                        "--skip-migrate",
                        "--skip-admin",
                        "--non-interactive",
                    )

            message = str(captured.exception)
            self.assertIn("请先在 PostgreSQL 中创建对应用户", message)
            self.assertNotIn("postgres_data", message)
            self.assertNotIn(".env", message)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("psycopg2.connect")
    @patch("apps.core.management.commands.install_forum._running_in_docker", return_value=True)
    def test_install_forum_surfaces_old_volume_hint_when_database_missing(
        self,
        mock_running_in_docker,
        mock_connect,
    ):
        import psycopg2

        mock_connect.side_effect = psycopg2.OperationalError('FATAL:  database "bias" does not exist')

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            with patch.dict(
                os.environ,
                {
                    "DB_NAME": "bias",
                    "DB_USER": "woniu",
                    "DB_PASSWORD": "woniu@woniu",
                },
                clear=False,
            ):
                with self.assertRaises(CommandError) as captured:
                    with override_settings(BASE_DIR=Path(temp_dir)):
                        call_command(
                            "install_forum",
                            "--database",
                            "postgres",
                            "--config",
                            str(config_path),
                            "--db-host",
                            "db",
                            "--db-port",
                            "5432",
                            "--skip-migrate",
                            "--skip-admin",
                            "--non-interactive",
                        )

            message = str(captured.exception)
            self.assertIn("postgres_data 卷", message)
            self.assertIn("旧数据库名", message)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class BootstrapConfigFallbackTests(TestCase):
    def test_load_site_bootstrap_prefers_database_env_when_site_config_missing(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with patch("apps.core.bootstrap_config._is_test_process", return_value=False):
                with patch.dict(
                    os.environ,
                    {
                        "DB_NAME": "bias",
                        "DB_USER": "postgres",
                        "DB_PASSWORD": "postgres",
                        "DB_HOST": "db",
                        "DB_PORT": "5432",
                        "REDIS_HOST": "redis",
                        "REDIS_PORT": "6379",
                        "REDIS_DB": "0",
                    },
                    clear=False,
                ):
                    config = load_site_bootstrap(temp_dir)

            self.assertTrue(config.installed)
            self.assertEqual(config.source, "env")
            self.assertEqual(config.database_mode, "postgres")
            self.assertEqual(config.db_name, "bias")
            self.assertEqual(config.db_user, "postgres")
            self.assertEqual(config.db_host, "db")
            self.assertTrue(config.use_redis)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class SettingsServiceFallbackTests(TestCase):
    def test_get_setting_group_returns_defaults_when_settings_table_is_unavailable(self):
        defaults = {"log_queries": False, "maintenance_mode": False}

        with patch("apps.core.settings_service.Setting.objects.filter", side_effect=OperationalError("no such table")):
            values = get_setting_group("advanced", defaults)

        self.assertEqual(values, defaults)


class EnsureAdminCommandTests(TestCase):
    def test_ensure_admin_command_creates_admin_user_and_group_membership(self):
        call_command("init_groups")

        call_command(
            "ensure_admin",
            "--username",
            "forum-admin",
            "--email",
            "forum-admin@example.com",
            "--password",
            "password123",
        )

        admin = User.objects.get(username="forum-admin")
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.is_email_confirmed)
        self.assertTrue(admin.user_groups.filter(name="Admin").exists())
        self.assertTrue(admin.check_password("password123"))


class UpgradeForumCommandTests(TestCase):
    def _success_result(self, args):
        return CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    @patch("apps.core.management.commands.upgrade_forum.ensure_release_versions_aligned")
    @patch("apps.core.management.commands.upgrade_forum.run_manage_py")
    def test_upgrade_forum_runs_default_upgrade_steps(self, mock_run_manage_py, mock_ensure_versions):
        mock_run_manage_py.side_effect = lambda args, env: self._success_result(args)
        mock_ensure_versions.return_value = None

        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "upgrade_forum",
                "--config",
                str(config_path),
                "--non-interactive",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        self.assertEqual(mock_run_manage_py.call_count, 6)
        invoked_steps = [call.args[0] for call in mock_run_manage_py.call_args_list]
        self.assertEqual(
            invoked_steps,
            [
                ["check"],
                ["migrate", "--noinput"],
                ["init_groups"],
                ["sync_forum_version"],
                ["clear_runtime_cache"],
                ["collectstatic", "--noinput"],
            ],
        )
        self.assertEqual(mock_run_manage_py.call_args_list[0].args[1]["BIAS_SITE_CONFIG"], str(config_path))

    @patch(
        "apps.core.management.commands.upgrade_forum.ensure_release_versions_aligned",
        side_effect=ValueError("版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致"),
    )
    def test_upgrade_forum_requires_aligned_release_versions(self, mock_ensure_versions):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(
                CommandError,
                "版本校验失败: 版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致",
            ):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.upgrade_forum.run_manage_py")
    def test_upgrade_forum_dry_run_does_not_execute_steps(self, mock_run_manage_py):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "sqlite",
                        "sqlite_name": "db.sqlite3",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            call_command(
                "upgrade_forum",
                "--config",
                str(config_path),
                "--dry-run",
                "--non-interactive",
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        mock_run_manage_py.assert_not_called()

    def test_upgrade_forum_requires_existing_site_config(self):
        temp_dir = make_workspace_temp_dir()
        try:
            missing_config_path = Path(temp_dir) / "instance" / "site.json"
            with self.assertRaisesMessage(CommandError, f"站点配置不存在: {missing_config_path}。请先执行 python manage.py install_forum"):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(missing_config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_upgrade_forum_validates_postgres_required_fields(self):
        temp_dir = make_workspace_temp_dir()
        try:
            config_path = Path(temp_dir) / "instance" / "site.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "installed": True,
                        "source": "file",
                        "database_mode": "postgres",
                        "db_name": "",
                        "db_user": "",
                        "db_host": "",
                        "db_port": "",
                        "use_redis": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(CommandError, "PostgreSQL 模式缺少必要配置: db_name, db_user, db_host, db_port"):
                call_command(
                    "upgrade_forum",
                    "--config",
                    str(config_path),
                    "--non-interactive",
                )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ReleaseVersionControlTests(TestCase):
    def test_ensure_release_versions_aligned_raises_when_version_mismatch(self):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.1\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesMessage(
                ValueError,
                "版本不一致：VERSION 与 frontend/package.json 的 version 必须完全一致",
            ):
                ensure_release_versions_aligned(base_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.prepare_release.subprocess.run")
    def test_prepare_release_syncs_version_and_frontend_package_files(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout="",
            stderr="",
        )

        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps(
                    {
                        "name": "bias-frontend",
                        "version": "1.0.0",
                        "packages": {
                            "": {
                                "name": "bias-frontend",
                                "version": "1.0.0",
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                call_command("prepare_release", "--tag", "v1.2.3")

            self.assertEqual((base_dir / "VERSION").read_text(encoding="utf-8").strip(), "1.2.3")
            package_json = json.loads((base_dir / "frontend" / "package.json").read_text(encoding="utf-8"))
            package_lock = json.loads((base_dir / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
            self.assertEqual(package_json["version"], "1.2.3")
            self.assertEqual(package_lock["version"], "1.2.3")
            self.assertEqual(package_lock["packages"][""]["version"], "1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_prepare_release_rejects_mismatched_version_and_tag(self):
        with self.assertRaisesMessage(CommandError, "--set-version 与 --tag 不一致"):
            call_command("prepare_release", "--set-version", "1.0.1", "--tag", "v1.0.2", "--allow-dirty")

    @patch("apps.core.management.commands.prepare_release.subprocess.run")
    def test_prepare_release_requires_clean_git_state_by_default(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout=" M README.md\n",
            stderr="",
        )
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.0.0\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.0.0", "packages": {"": {"version": "1.0.0"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty",
                ):
                    call_command("prepare_release", "--set-version", "1.0.1")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_creates_git_tag_when_versions_match(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        base_dir = Path(temp_dir)
        mock_run.side_effect = [
            CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
            CompletedProcess(args=build_git_command(base_dir, "tag", "--list", "v1.2.3"), returncode=0, stdout="", stderr=""),
            CompletedProcess(
                args=build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
                returncode=0,
                stdout="",
                stderr="",
            ),
        ]
        try:
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                call_command("finalize_release", "--tag", "v1.2.3")

            self.assertEqual(
                mock_run.call_args_list[2].args[0],
                build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_rejects_mismatched_tag_and_version(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git tag 与代码版本不一致：tag=v1.2.4，VERSION=1.2.3",
                ):
                    call_command("finalize_release", "--tag", "v1.2.4", "--allow-dirty")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        mock_run.assert_not_called()

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_requires_clean_git_state_by_default(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        mock_run.return_value = CompletedProcess(
            args=build_git_command(Path(temp_dir), "status", "--short"),
            returncode=0,
            stdout=" M VERSION\n",
            stderr="",
        )
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(
                    CommandError,
                    "Git 工作区不干净，请先提交或 stash 改动；如需跳过请传 --allow-dirty",
                ):
                    call_command("finalize_release", "--tag", "v1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_rejects_existing_git_tag(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        base_dir = Path(temp_dir)
        mock_run.side_effect = [
            CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
            CompletedProcess(
                args=build_git_command(base_dir, "tag", "--list", "v1.2.3"),
                returncode=0,
                stdout="v1.2.3\n",
                stderr="",
            ),
        ]
        try:
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )

            with override_settings(BASE_DIR=base_dir):
                with self.assertRaisesMessage(CommandError, "Git tag 已存在: v1.2.3"):
                    call_command("finalize_release", "--tag", "v1.2.3")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    @patch("apps.core.management.commands.publish_release.subprocess.run")
    @patch("apps.core.management.commands.publish_release.call_command")
    def test_publish_release_runs_prepare_then_finalize_in_dry_run(self, mock_call_command, mock_subprocess_run):
        call_command(
            "publish_release",
            "--set-version",
            "1.2.3",
            "--dry-run",
            "--allow-dirty",
        )

        self.assertEqual(
            [call.args for call in mock_call_command.call_args_list],
            [
                ("prepare_release", "--set-version", "1.2.3", "--tag", "v1.2.3", "--allow-dirty", "--dry-run"),
                ("finalize_release", "--tag", "v1.2.3", "--dry-run"),
            ],
        )
        mock_subprocess_run.assert_not_called()

    @patch("apps.core.management.commands.publish_release.subprocess.run")
    @patch("apps.core.management.commands.publish_release.call_command")
    def test_publish_release_commits_then_tags_and_pushes(self, mock_call_command, mock_subprocess_run):
        base_dir = settings.BASE_DIR
        call_command(
            "publish_release",
            "--set-version",
            "1.2.3",
            "--push",
        )

        self.assertEqual(
            [call.args for call in mock_call_command.call_args_list],
            [
                ("prepare_release", "--set-version", "1.2.3", "--tag", "v1.2.3"),
                ("finalize_release", "--tag", "v1.2.3"),
            ],
        )
        self.assertEqual(
            [call.args[0] for call in mock_subprocess_run.call_args_list],
            [
                build_git_command(base_dir, "add", "VERSION", "frontend/package.json", "frontend/package-lock.json"),
                build_git_command(base_dir, "commit", "-m", "发布 1.2.3"),
                build_git_command(base_dir, "push", "origin", "main", "--tags"),
            ],
        )

    @patch("apps.core.management.commands.finalize_release.subprocess.run")
    def test_finalize_release_uses_safe_directory_git_commands(self, mock_run):
        temp_dir = make_workspace_temp_dir()
        try:
            base_dir = Path(temp_dir)
            (base_dir / "frontend").mkdir(parents=True, exist_ok=True)
            (base_dir / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (base_dir / "frontend" / "package.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3"}) + "\n",
                encoding="utf-8",
            )
            (base_dir / "frontend" / "package-lock.json").write_text(
                json.dumps({"name": "bias-frontend", "version": "1.2.3", "packages": {"": {"version": "1.2.3"}}}) + "\n",
                encoding="utf-8",
            )
            mock_run.side_effect = [
                CompletedProcess(args=build_git_command(base_dir, "status", "--short"), returncode=0, stdout="", stderr=""),
                CompletedProcess(args=build_git_command(base_dir, "tag", "--list", "v1.2.3"), returncode=0, stdout="", stderr=""),
                CompletedProcess(args=build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"), returncode=0, stdout="", stderr=""),
            ]

            with override_settings(BASE_DIR=base_dir):
                call_command("finalize_release", "--tag", "v1.2.3")

            self.assertEqual(mock_run.call_args_list[0].args[0], build_git_command(base_dir, "status", "--short"))
            self.assertEqual(mock_run.call_args_list[1].args[0], build_git_command(base_dir, "tag", "--list", "v1.2.3"))
            self.assertEqual(
                mock_run.call_args_list[2].args[0],
                build_git_command(base_dir, "tag", "-a", "v1.2.3", "-m", "Release v1.2.3"),
            )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

class SystemStatusApiTests(TestCase):
    def test_system_status_endpoint_returns_ready_state(self):
        response = self.client.get("/api/system/status")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["state"], "ready")
        self.assertIn("current_version", payload)


class LocalStorageSettingsTests(TestCase):
    def test_attachment_upload_respects_custom_local_storage_settings(self):
        tmpdir = Path.cwd() / "media" / f"storage-test-{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        try:
            Setting.objects.update_or_create(
                key="advanced.storage_driver",
                defaults={"value": json.dumps("local")},
            )
            Setting.objects.update_or_create(
                key="advanced.storage_local_path",
                defaults={"value": json.dumps(str(tmpdir))},
            )
            Setting.objects.update_or_create(
                key="advanced.storage_local_base_url",
                defaults={"value": json.dumps("/uploads/")},
            )
            Setting.objects.update_or_create(
                key="advanced.storage_attachments_dir",
                defaults={"value": json.dumps("forum-files")},
            )

            file = SimpleUploadedFile("guide.txt", b"hello storage", content_type="text/plain")

            file_url, file_info = FileUploadService.upload_attachment(file, 9)

            self.assertTrue(file_url.startswith("/uploads/forum-files/9/"))
            self.assertEqual(file_info["original_name"], "guide.txt")

            relative_key = file_url.removeprefix("/uploads/")
            stored_path = Path(tmpdir).joinpath(*relative_key.split("/"))
            self.assertTrue(stored_path.exists())
            self.assertEqual(stored_path.read_bytes(), b"hello storage")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class AdminGroupManagementApiTests(TestCase):
    def setUp(self):
        call_command("init_groups")
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
                "color": "#27ae60",
                "icon": "fas fa-life-ring",
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
                "color": "#8e44ad",
                "icon": "fas fa-headset",
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
        self.assertEqual(group.name_singular, "Support")
        self.assertEqual(group.name_plural, "Support")
        self.assertEqual(group.color, "#8e44ad")
        self.assertEqual(group.icon, "fas fa-headset")
        self.assertTrue(group.is_hidden)

    def test_admin_can_delete_custom_group(self):
        group = Group.objects.create(
            name="Helpers",
            name_singular="Helper",
            name_plural="Helpers",
            color="#27ae60",
        )
        Permission.objects.create(group=group, permission="discussion.reply")

        response = self.client.delete(
            f"/api/admin/groups/{group.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(Group.objects.filter(id=group.id).exists())
        self.assertFalse(Permission.objects.filter(group_id=group.id).exists())

    def test_admin_cannot_delete_builtin_group(self):
        response = self.client.delete(
            "/api/admin/groups/1",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "系统默认用户组不允许删除")
        self.assertTrue(Group.objects.filter(id=1, name="Admin").exists())


class AdminPermissionsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-permission-mgr",
            email="admin-permission-mgr@example.com",
            password="password123",
        )
        self.group = Group.objects.create(
            name="Editors",
            name_singular="Editor",
            name_plural="Editors",
            color="#4d698e",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_permissions_api_normalizes_legacy_codes_on_read(self):
        Permission.objects.create(group=self.group, permission="reply")
        Permission.objects.create(group=self.group, permission="editPosts")

        response = self.client.get(
            "/api/admin/permissions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        group_permissions = payload.get(str(self.group.id), payload.get(self.group.id, []))
        self.assertEqual(set(group_permissions), {"discussion.reply", "discussion.edit"})

    def test_permissions_api_normalizes_legacy_codes_on_save(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["reply", "editPosts", "reply"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            set(Permission.objects.filter(group=self.group).values_list("permission", flat=True)),
            {"discussion.reply", "discussion.edit"},
        )

    def test_permissions_api_rejects_unknown_permission(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["unknown.permission"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("未知权限", response.json()["error"])


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

    def test_admin_can_list_and_approve_queue(self):
        response = self.client.get(
            "/api/admin/approval-queue",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 2)

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
