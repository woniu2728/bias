import json
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from ninja_jwt.tokens import RefreshToken

from apps.core.extension_settings_service import save_extension_settings
from apps.core.models import Setting
from apps.core.settings_service import clear_runtime_setting_caches
from extensions.uploads.backend.services import UploadService
from extensions.users.backend.models import User


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

    @patch("extensions.uploads.backend.api.UploadService.upload_attachment")
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

    @patch("extensions.uploads.backend.api.UploadService.upload_attachment")
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

    @patch("extensions.uploads.backend.api.UploadService.upload_attachment")
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


class AdminAppearanceUploadApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="upload-admin",
            email="upload-admin@example.com",
            password="password123",
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    @patch("extensions.uploads.backend.api.UploadService.upload_site_asset")
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

    def test_non_staff_cannot_upload_appearance_asset(self):
        member = User.objects.create_user(
            username="upload-member",
            email="upload-member@example.com",
            password="password123",
        )
        file = SimpleUploadedFile("site-logo.png", b"png-data", content_type="image/png")

        response = self.client.post(
            "/api/admin/appearance/upload?target=logo",
            {"file": file},
            **self.auth_header(member),
        )

        self.assertEqual(response.status_code, 403, response.content)

    def test_site_asset_upload_limit_is_saved_through_advanced_settings(self):
        response = self.client.post(
            "/api/admin/advanced",
            data=json.dumps({"upload_site_asset_max_size_mb": 4}),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["upload_site_asset_max_size_mb"], 4)
        self.assertEqual(UploadService.get_site_asset_upload_limit_mb(), 4)


class UploadStorageSettingsTests(TestCase):
    def setUp(self):
        from extensions.testing import bootstrap_enabled_extension_application

        bootstrap_enabled_extension_application("uploads")
        clear_runtime_setting_caches()

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

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
            save_extension_settings("uploads", {"attachments_dir": "forum-files"})

            file = SimpleUploadedFile("guide.txt", b"hello storage", content_type="text/plain")

            file_url, file_info = UploadService.upload_attachment(file, 9)

            self.assertTrue(file_url.startswith("/uploads/forum-files/9/"))
            self.assertEqual(file_info["original_name"], "guide.txt")

            relative_key = file_url.removeprefix("/uploads/")
            stored_path = Path(tmpdir).joinpath(*relative_key.split("/"))
            self.assertTrue(stored_path.exists())
            self.assertEqual(stored_path.read_bytes(), b"hello storage")
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_attachment_upload_respects_runtime_size_limit(self):
        save_extension_settings("uploads", {"attachment_max_size_mb": 1})
        file = SimpleUploadedFile("too-large.txt", b"x" * (1024 * 1024 + 1), content_type="text/plain")

        with self.assertRaisesMessage(ValueError, "文件大小超过限制"):
            UploadService.upload_attachment(file, 9)

    def test_upload_policy_exposes_runtime_limits(self):
        user = User.objects.create_user(
            username="upload-policy-user",
            email="upload-policy-user@example.com",
            password="password123",
        )
        Setting.objects.update_or_create(
            key="extensions.uploads.attachment_max_size_mb",
            defaults={"value": json.dumps(7)},
        )
        token = RefreshToken.for_user(user).access_token

        response = self.client.get(
            "/api/uploads/policy",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["attachment_max_size_mb"], 7)
        self.assertIn(".pdf", response.json()["allowed_attachment_extensions"])
