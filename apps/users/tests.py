import json
from io import BytesIO
import httpx
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from PIL import Image
from ninja_jwt.tokens import RefreshToken

from apps.core.models import Setting
from apps.core.settings_service import clear_runtime_setting_caches
from apps.users.models import Group
from apps.users.models import EmailToken, PasswordToken, Permission, User


@override_settings(
    DEBUG=False,
    FRONTEND_URL="http://localhost:5173",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class PasswordResetApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="reset-user",
            email="reset@example.com",
            password="password123",
        )

    def test_forgot_password_creates_token(self):
        response = self.client.post(
            "/api/users/forgot-password",
            data=json.dumps({"email": self.user.email}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["message"], "重置密码邮件已发送")

        token = PasswordToken.objects.get(user=self.user)
        self.assertTrue(token.token)

    def test_forgot_password_uses_runtime_mail_settings(self):
        Setting.objects.update_or_create(
            key="mail.mail_from_address",
            defaults={"value": json.dumps("reset@example.com")},
        )
        Setting.objects.update_or_create(
            key="mail.mail_from_name",
            defaults={"value": json.dumps("Reset Service")},
        )

        response = self.client.post(
            "/api/users/forgot-password",
            data=json.dumps({"email": self.user.email}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "Reset Service <reset@example.com>")

    def test_forgot_password_uses_runtime_mail_templates(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("Bias 社区")},
        )
        Setting.objects.update_or_create(
            key="mail.mail_password_reset_subject",
            defaults={"value": json.dumps("重置 {{ site_name }} 密码")},
        )
        Setting.objects.update_or_create(
            key="mail.mail_password_reset_text",
            defaults={"value": json.dumps("你好 {{ username }}，请访问 {{ reset_url }}")},
        )
        Setting.objects.update_or_create(
            key="mail.mail_password_reset_html",
            defaults={"value": json.dumps("<p>{{ username }}</p><a href=\"{{ reset_url }}\">重置 {{ site_name }}</a>")},
        )

        response = self.client.post(
            "/api/users/forgot-password",
            data=json.dumps({"email": self.user.email}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "重置 Bias 社区 密码")
        self.assertIn("你好 reset-user", mail.outbox[0].body)
        self.assertIn("/reset-password?token=", mail.outbox[0].body)
        self.assertIn("重置 Bias 社区", mail.outbox[0].alternatives[0][0])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_forgot_password_queues_email_when_queue_enabled(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        with patch("apps.core.tasks.send_password_reset_email_task.delay") as delay:
            response = self.client.post(
                "/api/users/forgot-password",
                data=json.dumps({"email": self.user.email}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(PasswordToken.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        delay.assert_called_once()

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_forgot_password_falls_back_to_sync_when_queue_enqueue_fails(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        with patch("apps.core.tasks.send_password_reset_email_task.delay", side_effect=RuntimeError("queue down")):
            response = self.client.post(
                "/api/users/forgot-password",
                data=json.dumps({"email": self.user.email}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(PasswordToken.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)


class AvatarUploadApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="avatar-user",
            email="avatar@example.com",
            password="password123",
        )
        self.other_user = User.objects.create_user(
            username="other-user",
            email="other@example.com",
            password="password123",
        )
        self.token = str(RefreshToken.for_user(self.user).access_token)

    @patch("apps.users.api.FileUploadService.delete_file")
    @patch("apps.users.api.FileUploadService.upload_avatar")
    def test_upload_avatar_updates_user_avatar_url(self, upload_avatar, delete_file):
        upload_avatar.return_value = (f"/media/avatars/{self.user.id}/new-avatar.png", {})

        response = self.client.post(
            f"/api/users/{self.user.id}/avatar",
            data={"avatar": self._build_avatar_file()},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200, response.content)

        payload = response.json()
        self.assertEqual(payload["avatar_url"], f"/media/avatars/{self.user.id}/new-avatar.png")

        self.user.refresh_from_db()
        self.assertEqual(self.user.avatar_url, payload["avatar_url"])
        upload_avatar.assert_called_once()
        delete_file.assert_not_called()

    @patch("apps.users.api.FileUploadService.upload_avatar")
    def test_upload_avatar_for_other_user_is_forbidden(self, upload_avatar):
        response = self.client.post(
            f"/api/users/{self.other_user.id}/avatar",
            data={"avatar": self._build_avatar_file()},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.other_user.refresh_from_db()
        self.assertIsNone(self.other_user.avatar_url)
        upload_avatar.assert_not_called()

    def _build_avatar_file(self):
        buffer = BytesIO()
        Image.new("RGB", (32, 32), "#4d698e").save(buffer, format="PNG")
        buffer.seek(0)
        return SimpleUploadedFile("avatar.png", buffer.getvalue(), content_type="image/png")


class UserProfileApiTests(TestCase):
    def test_user_detail_exposes_primary_group_for_staff_user(self):
        user = User.objects.create_user(
            username="staff-profile",
            email="staff-profile@example.com",
            password="password123",
            is_staff=True,
        )

        response = self.client.get(f"/api/users/{user.id}")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["primary_group"]["name"], "Admin")
        self.assertEqual(payload["primary_group"]["icon"], "fas fa-user-shield")

    def test_user_detail_exposes_primary_group_for_regular_group_member(self):
        user = User.objects.create_user(
            username="group-profile",
            email="group-profile@example.com",
            password="password123",
        )
        group = Group.objects.create(name="Support", color="#27ae60", icon="fas fa-life-ring")
        user.user_groups.add(group)

        response = self.client.get(f"/api/users/{user.id}")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["primary_group"]["name"], "Support")
        self.assertEqual(payload["primary_group"]["icon"], "fas fa-life-ring")

    def test_current_user_exposes_forum_permissions(self):
        user = User.objects.create_user(
            username="permission-profile",
            email="permission-profile@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="PermissionGroup", color="#27ae60", icon="fas fa-key")
        Permission.objects.create(group=group, permission="startDiscussion")
        Permission.objects.create(group=group, permission="discussion.reply")
        user.user_groups.add(group)
        token = str(RefreshToken.for_user(user).access_token)

        response = self.client.get(
            "/api/users/me",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            set(response.json()["forum_permissions"]),
            {"startDiscussion", "discussion.reply"},
        )

    def test_list_users_requires_view_user_list_permission(self):
        user = User.objects.create_user(
            username="no-user-list",
            email="no-user-list@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="NoUserListPermission", color="#95a5a6")
        user.user_groups.add(group)
        token = str(RefreshToken.for_user(user).access_token)

        response = self.client.get(
            "/api/users",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限查看用户列表")

    def test_search_users_requires_search_users_permission(self):
        user = User.objects.create_user(
            username="no-user-search",
            email="no-user-search@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="NoSearchUsersPermission", color="#95a5a6")
        Permission.objects.create(group=group, permission="viewUserList")
        user.user_groups.add(group)
        token = str(RefreshToken.for_user(user).access_token)

        response = self.client.get(
            "/api/users",
            {"q": "profile"},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(response.json()["error"], "没有权限搜索用户")

    def test_list_users_exposes_primary_group(self):
        viewer = User.objects.create_user(
            username="user-list-viewer",
            email="user-list-viewer@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        viewer_group = Group.objects.create(name="Viewers", color="#2ecc71")
        Permission.objects.create(group=viewer_group, permission="viewUserList")
        Permission.objects.create(group=viewer_group, permission="viewForum")
        viewer.user_groups.add(viewer_group)

        listed_user = User.objects.create_user(
            username="listed-user",
            email="listed-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        support_group = Group.objects.create(name="Support", color="#3498db", icon="fas fa-life-ring")
        listed_user.user_groups.add(support_group)
        token = str(RefreshToken.for_user(viewer).access_token)

        response = self.client.get(
            "/api/users",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        listed_payload = next(item for item in payload if item["username"] == "listed-user")
        self.assertEqual(listed_payload["primary_group"]["name"], support_group.name)

    def test_search_users_exposes_primary_group(self):
        viewer = User.objects.create_user(
            username="user-search-viewer",
            email="user-search-viewer@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        viewer_group = Group.objects.create(name="Searchers", color="#9b59b6")
        Permission.objects.create(group=viewer_group, permission="viewForum")
        Permission.objects.create(group=viewer_group, permission="viewUserList")
        Permission.objects.create(group=viewer_group, permission="searchUsers")
        viewer.user_groups.add(viewer_group)

        matched_user = User.objects.create_user(
            username="search-profile-user",
            email="search-profile-user@example.com",
            password="password123",
            display_name="Search Profile User",
            is_email_confirmed=True,
        )
        support_group = Group.objects.create(name="Search Support", color="#f39c12", icon="fas fa-headset")
        matched_user.user_groups.add(support_group)
        token = str(RefreshToken.for_user(viewer).access_token)

        response = self.client.get(
            "/api/users",
            {"q": "Search Profile"},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        matched_payload = next(item for item in payload if item["username"] == "search-profile-user")
        self.assertEqual(matched_payload["primary_group"]["name"], support_group.name)


class SuspendedUserAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="suspended-user",
            email="suspended@example.com",
            password="password123",
            suspended_until=timezone.now() + timedelta(days=3),
            suspend_message="请联系管理员申诉",
        )

    def test_login_returns_suspension_notice(self):
        response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "suspended-user",
                "password": "password123",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401, response.content)
        self.assertIn("账号已被封禁", response.json()["error"])
        self.assertIn("请联系管理员申诉", response.json()["error"])


@override_settings(DEBUG=False)
class TokenCookieAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="token-cookie-user",
            email="token-cookie@example.com",
            password="password123",
        )

    def test_login_sets_refresh_token_cookie_without_exposing_refresh_body(self):
        response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "token-cookie-user",
                "password": "password123",
            }),
            content_type="application/json",
            secure=True,
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["access"])
        self.assertNotIn("refresh", payload)

        cookie = response.cookies.get("bias_refresh_token")
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/api/users")

    def test_refresh_access_token_uses_cookie(self):
        login_response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "token-cookie-user",
                "password": "password123",
            }),
            content_type="application/json",
            secure=True,
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)

        response = self.client.post("/api/users/token/refresh", secure=True)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["access"])
        self.assertNotIn("refresh", response.json())

    def test_refresh_access_token_requires_cookie(self):
        response = self.client.post("/api/users/token/refresh", secure=True)

        self.assertEqual(response.status_code, 401, response.content)
        self.assertEqual(response.json()["error"], "登录状态已过期，请重新登录")

    def test_logout_clears_refresh_token_cookie(self):
        login_response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "token-cookie-user",
                "password": "password123",
            }),
            content_type="application/json",
            secure=True,
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)

        response = self.client.post("/api/users/logout", secure=True)

        self.assertEqual(response.status_code, 200, response.content)
        cookie = response.cookies.get("bias_refresh_token")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie["path"], "/api/users")


class HumanVerificationAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="human-check-user",
            email="human-check@example.com",
            password="password123",
        )

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def enable_turnstile(self, *, login_enabled=True, register_enabled=True):
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_provider",
            defaults={"value": json.dumps("turnstile")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_turnstile_site_key",
            defaults={"value": json.dumps("site-key")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_turnstile_secret_key",
            defaults={"value": json.dumps("secret-key")},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_login_enabled",
            defaults={"value": json.dumps(login_enabled)},
        )
        Setting.objects.update_or_create(
            key="advanced.auth_human_verification_register_enabled",
            defaults={"value": json.dumps(register_enabled)},
        )
        clear_runtime_setting_caches()

    def test_login_requires_human_verification_when_enabled(self):
        self.enable_turnstile(login_enabled=True, register_enabled=False)

        response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "human-check-user",
                "password": "password123",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "请先完成真人验证")

    @patch("apps.core.human_verification.httpx.post")
    def test_login_accepts_valid_human_verification_token(self, mock_post):
        self.enable_turnstile(login_enabled=True, register_enabled=False)
        mock_post.return_value = self._build_turnstile_response({"success": True})

        response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "human-check-user",
                "password": "password123",
                "human_verification_token": "turnstile-ok",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["access"])
        self.assertNotIn("refresh", response.json())
        self.assertIsNotNone(response.cookies.get("bias_refresh_token"))
        mock_post.assert_called_once()
        self.assertEqual(mock_post.call_args.kwargs["data"]["secret"], "secret-key")
        self.assertEqual(mock_post.call_args.kwargs["data"]["response"], "turnstile-ok")

    @patch("apps.core.human_verification.httpx.post")
    def test_register_accepts_valid_human_verification_token(self, mock_post):
        self.enable_turnstile(login_enabled=False, register_enabled=True)
        mock_post.return_value = self._build_turnstile_response({"success": True})

        response = self.client.post(
            "/api/users/register",
            data=json.dumps({
                "username": "verified-register",
                "email": "verified-register@example.com",
                "password": "password123",
                "human_verification_token": "turnstile-register",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], "verified-register")
        self.assertTrue(User.objects.filter(username="verified-register").exists())

    @patch("apps.core.human_verification.httpx.post")
    def test_login_returns_service_unavailable_when_turnstile_verification_breaks(self, mock_post):
        self.enable_turnstile(login_enabled=True, register_enabled=False)
        mock_post.side_effect = httpx.ConnectError("boom")

        response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "human-check-user",
                "password": "password123",
                "human_verification_token": "turnstile-ok",
            }),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503, response.content)
        self.assertEqual(response.json()["error"], "真人验证服务暂时不可用，请稍后再试")

    @staticmethod
    def _build_turnstile_response(payload):
        class MockResponse:
            def __init__(self, body):
                self._body = body

            def raise_for_status(self):
                return None

            def json(self):
                return self._body

        return MockResponse(payload)


@override_settings(
    DEBUG=False,
    FRONTEND_URL="http://localhost:5173",
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class EmailVerificationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="verify-user",
            email="verify@example.com",
            password="password123",
            is_email_confirmed=False,
        )
        self.token = str(RefreshToken.for_user(self.user).access_token)

    def test_resend_email_verification_sends_new_mail(self):
        response = self.client.post(
            "/api/users/me/resend-email-verification",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["message"], "验证邮件已重新发送")
        self.assertEqual(EmailToken.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verify-email?token=", mail.outbox[0].body)

    def test_resend_email_verification_uses_runtime_templates(self):
        Setting.objects.update_or_create(
            key="basic.forum_title",
            defaults={"value": json.dumps("Bias 社区")},
        )
        Setting.objects.update_or_create(
            key="mail.mail_verification_subject",
            defaults={"value": json.dumps("验证 {{ site_name }} 邮箱")},
        )
        Setting.objects.update_or_create(
            key="mail.mail_verification_text",
            defaults={"value": json.dumps("你好 {{ username }}，请访问 {{ verification_url }}")},
        )
        Setting.objects.update_or_create(
            key="mail.mail_verification_html",
            defaults={"value": json.dumps("<p>{{ username }}</p><a href=\"{{ verification_url }}\">验证 {{ site_name }}</a>")},
        )

        response = self.client.post(
            "/api/users/me/resend-email-verification",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "验证 Bias 社区 邮箱")
        self.assertIn("你好 verify-user", mail.outbox[0].body)
        self.assertIn("/verify-email?token=", mail.outbox[0].body)
        self.assertIn("验证 Bias 社区", mail.outbox[0].alternatives[0][0])

    @override_settings(CELERY_BROKER_URL="redis://localhost:6379/1")
    def test_resend_email_verification_queues_mail_when_queue_enabled(self):
        Setting.objects.update_or_create(
            key="advanced.queue_enabled",
            defaults={"value": json.dumps(True)},
        )
        clear_runtime_setting_caches()

        with patch("apps.core.tasks.send_verification_email_task.delay") as delay:
            response = self.client.post(
                "/api/users/me/resend-email-verification",
                HTTP_AUTHORIZATION=f"Bearer {self.token}",
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(EmailToken.objects.filter(user=self.user).count(), 1)
        self.assertEqual(len(mail.outbox), 0)
        delay.assert_called_once()

    def test_resend_email_verification_rejects_confirmed_user(self):
        self.user.is_email_confirmed = True
        self.user.save(update_fields=["is_email_confirmed"])

        response = self.client.post(
            "/api/users/me/resend-email-verification",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "当前邮箱已经验证")
