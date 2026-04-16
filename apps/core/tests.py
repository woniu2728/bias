import json
from pathlib import Path
import shutil
import uuid

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from ninja_jwt.tokens import RefreshToken
from unittest.mock import patch

from apps.core.models import Setting
from apps.core.file_service import FileUploadService
from apps.core.settings_service import clear_runtime_setting_caches
from apps.core.services import SearchService
from apps.core.websocket_auth import get_user_from_token
from apps.discussions.services import DiscussionService
from apps.posts.models import PostFlag
from apps.posts.services import PostService
from apps.tags.models import Tag
from apps.users.models import Group, Permission, User


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
        )

        response = self.client.get("/api/search", {"q": "搜索", "type": "all"})

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
                "mail_driver": "sendmail",
                "mail_from_address": "service@example.com",
                "mail_from_name": "PyFlarum Mailer",
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
        self.assertEqual(mail.outbox[0].from_email, "PyFlarum Mailer <service@example.com>")

    def test_public_forum_settings_include_basic_and_appearance(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("运行时论坛名称")},
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

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["forum_title"], "运行时论坛名称")
        self.assertEqual(payload["welcome_title"], "欢迎来到运行时论坛")
        self.assertEqual(payload["primary_color"], "#123456")
        self.assertEqual(payload["logo_url"], "/media/runtime-logo.png")

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

        with self.assertLogs("pyflarum.sql", level="INFO") as captured:
            response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        joined_output = "\n".join(captured.output)
        self.assertIn("/api/forum", joined_output)
        self.assertIn("total_queries=", joined_output)
        self.assertIn("SELECT", joined_output.upper())

    def test_markdown_preview_endpoint_returns_rendered_html(self):
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
        self.assertIn('href="/u/alice"', html)
        self.assertIn('target="_blank"', html)


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
        )
        self.reporter = User.objects.create_user(
            username="flag-reporter",
            email="flag-reporter@example.com",
            password="password123",
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

        created_tag = Tag.objects.get(id=payload["id"])
        self.assertEqual(created_tag.parent_id, self.parent_tag.id)

        response = self.client.put(
            f"/api/admin/tags/{created_tag.id}",
            data=json.dumps({
                "name": "接口规范",
                "slug": "api-guidelines",
                "parent_id": None,
                "position": 6,
                "is_hidden": False,
                "is_restricted": False,
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

        created_tag.refresh_from_db()
        self.assertIsNone(created_tag.parent_id)
        self.assertEqual(created_tag.position, 6)

    def test_admin_cannot_delete_tag_with_children(self):
        response = self.client.delete(
            f"/api/admin/tags/{self.parent_tag.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertIn("子标签", response.json()["error"])


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
        Permission.objects.create(group=self.trusted_group, permission="startDiscussionWithoutApproval")
        Permission.objects.create(group=self.trusted_group, permission="replyWithoutApproval")

        self.author = User.objects.create_user(
            username="approval-author",
            email="approval-author@example.com",
            password="password123",
        )
        self.author.user_groups.add(self.trusted_group)
        self.pending_author = User.objects.create_user(
            username="approval-pending-author",
            email="approval-pending-author@example.com",
            password="password123",
        )
        self.replier = User.objects.create_user(
            username="approval-replier",
            email="approval-replier@example.com",
            password="password123",
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
