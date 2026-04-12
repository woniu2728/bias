import json
from io import BytesIO
from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from PIL import Image
from ninja_jwt.tokens import RefreshToken

from apps.core.models import Setting
from apps.users.models import EmailToken, PasswordToken, User


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
            key="mail.mail_driver",
            defaults={"value": json.dumps("sendmail")},
        )
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

    def test_resend_email_verification_rejects_confirmed_user(self):
        self.user.is_email_confirmed = True
        self.user.save(update_fields=["is_email_confirmed"])

        response = self.client.post(
            "/api/users/me/resend-email-verification",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "当前邮箱已经验证")
