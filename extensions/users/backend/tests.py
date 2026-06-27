import json
from io import BytesIO
from io import StringIO
import httpx
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.core import mail
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta
from PIL import Image
from ninja_jwt.tokens import RefreshToken

from extensions.users.backend.events import UserSuspendedEvent, UserUnsuspendedEvent
from apps.core.extension_settings_service import save_extension_settings
from apps.core.forum_registry import get_forum_registry
from apps.core.models import AuditLog, Setting
from apps.core.jwt_auth import ACCESS_TOKEN_COOKIE_NAME
from apps.core.extensions import ResourceEndpointDefinition
from extensions.testing import ResourceRegistry
from extensions.testing import bootstrap_enabled_extension_application
from apps.core.settings_service import clear_runtime_setting_caches
from apps.core.extensions.runtime import get_runtime_notification_model
from extensions.testing import ExtensionRuntimeTestMixin
from extensions.users.backend.handlers import user_resource_endpoints
from extensions.users.backend.avatar_upload import UserAvatarUploadService
from extensions.users.backend.models import Group
from extensions.users.backend.models import EmailToken, PasswordToken, Permission, User
from extensions.users.backend.resources import serialize_user_payload, serialize_user_summary
from extensions.users.backend.services import UserService


class RuntimeModelProxy:
    def __init__(self, resolver):
        self._resolver = resolver

    def __getattr__(self, name):
        return getattr(self._resolver(), name)


Notification = RuntimeModelProxy(get_runtime_notification_model)


class UserPreferencesApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="prefs-user",
            email="prefs-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.user).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_preferences_api_returns_ui_values_defaults(self):
        response = self.client.get("/api/users/me/preferences", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["ui_values"], {})
        self.assertIn("values", payload)
        self.assertIn("definitions", payload)

    def test_preferences_api_updates_ui_values(self):
        response = self.client.patch(
            "/api/users/me/preferences",
            data=json.dumps({
                "values": {
                    "notify_user_mentioned": False,
                },
                "ui_values": {},
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.user.refresh_from_db()
        self.assertEqual(self.user.preferences_ui, {})
        self.assertFalse(self.user.preferences["notify_user_mentioned"])
        self.assertEqual(response.json()["ui_values"], {})


class UsersExtensionDiagnosticsTests(ExtensionRuntimeTestMixin, TestCase):
    def test_users_extension_registers_runtime_service_provider(self):
        application = self.bootstrap_extensions("users")
        service = application.get_service("users.service")

        self.assertIn("users.service", application.get_service_provider_keys(extension_id="users"))
        self.assertIs(service["model"], User)
        self.assertIs(service["group_model"], Group)
        self.assertIs(service["permission_model"], Permission)
        for key in (
            "get_by_id",
            "get_by_username",
            "list_by_usernames",
            "username_id_map",
            "ensure_not_suspended",
            "has_forum_permission",
            "get_preference",
            "increment_discussion_count",
            "increment_comment_count",
            "apply_comment_count_deltas",
        ):
            self.assertTrue(callable(service[key]), key)

        provider_definition = application.get_service("user").get_definitions()[0].callback
        provider_payload = provider_definition({}, {}) if callable(provider_definition) else provider_definition
        provider = provider_payload["provider"]()
        for key in ("get_by_username", "list_by_usernames", "username_id_map", "serialize"):
            self.assertTrue(callable(provider[key]), key)

    def test_users_capabilities_are_filtered_when_extension_disabled(self):
        self.disable_extension_for_test("users")

        registry = get_forum_registry()

        self.assertFalse(registry.get_module("users").enabled)
        self.assertFalse(any(item.module_id == "users" for item in registry.get_admin_pages()))
        self.assertNotIn("viewUserList", registry.get_valid_permission_codes())
        self.assertNotIn("searchUsers", registry.get_valid_permission_codes())
        self.assertNotIn("user.edit", registry.get_valid_permission_codes())
        self.assertNotIn("user.suspend", registry.get_valid_permission_codes())

    def test_extension_detail_api_surfaces_user_frontend_routes(self):
        admin = User.objects.create_superuser(
            username="user-detail-admin",
            email="user-detail-admin@example.com",
            password="password123",
        )
        token = RefreshToken.for_user(admin).access_token
        response = self.client.get(
            "/api/admin/extensions/users",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_forum_entry"], "extensions/users/frontend/forum/index.js")
        users_routes = {
            item["name"]: item
            for item in payload["frontend_routes"]
            if item["frontend"] == "forum"
        }
        self.assertEqual(users_routes["login"]["path"], "/login")
        self.assertEqual(users_routes["login"]["component"], "./AuthRouteView.vue")
        self.assertEqual(users_routes["login"]["module_id"], "users")
        self.assertEqual(users_routes["register"]["path"], "/register")
        self.assertEqual(users_routes["register"]["component"], "./AuthRouteView.vue")
        self.assertEqual(users_routes["forgot-password"]["path"], "/forgot-password")
        self.assertEqual(users_routes["forgot-password"]["component"], "./AuthRouteView.vue")
        self.assertEqual(users_routes["verify-email"]["path"], "/verify-email")
        self.assertEqual(users_routes["verify-email"]["component"], "./VerifyEmailView.vue")
        self.assertEqual(users_routes["reset-password"]["path"], "/reset-password")
        self.assertEqual(users_routes["reset-password"]["component"], "./ResetPasswordView.vue")
        self.assertEqual(users_routes["profile"]["path"], "/profile")
        self.assertEqual(users_routes["profile"]["component"], "./ProfileView.vue")
        self.assertEqual(users_routes["profile"]["module_id"], "users")
        self.assertTrue(users_routes["profile"]["requires_auth"])
        self.assertEqual(users_routes["user-profile"]["path"], "/u/:id")
        self.assertEqual(users_routes["user-profile"]["component"], "./ProfileView.vue")
        self.assertEqual(users_routes["user-profile"]["module_id"], "users")

    def test_inspect_reports_users_models_as_extension_owned(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "users",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]

        self.assertEqual(extension["id"], "users")
        self.assertEqual(audit["owned_model_count"], 6)
        self.assertEqual(audit["app_label_migration_required_count"], 0)
        self.assertEqual(extension["django_app_label"], "users")
        self.assertEqual(audit["target_app_label"], "users")
        self.assertEqual(audit["target_app_label_source"], "manifest")
        self.assertTrue(all(
            item["target_app_label"] == "users"
            and item["target_app_label_source"] == "manifest"
            for item in audit["items"]
        ))
        self.assertTrue(
            any(str(name).startswith("0001_") for name in extension["migration_plan"]["pending_files"])
        )


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AdminMailTestEmailApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="mail-admin",
            email="admin@example.com",
            password="password123",
        )

    def auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def save_mail_settings(self, payload=None):
        response = self.client.post(
            "/api/admin/mail",
            data=json.dumps({
                "mail_from": "Bias Mailer <service@example.com>",
                "mail_driver": "smtp",
                **(payload or {}),
            }),
            content_type="application/json",
            **self.auth_header(),
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response

    def test_mail_settings_affect_test_email_sender(self):
        self.save_mail_settings()

        response = self.client.post("/api/admin/mail/test", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(response.json()["to_email"], "admin@example.com")
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])
        self.assertEqual(mail.outbox[0].from_email, "Bias Mailer <service@example.com>")

    def test_mail_test_endpoint_sends_to_current_admin_email(self):
        self.save_mail_settings()

        response = self.client.post("/api/admin/mail/test", **self.auth_header())

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "admin@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["admin@example.com"])

    def test_mail_test_endpoint_accepts_custom_recipient(self):
        self.save_mail_settings()

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

    def test_mail_test_endpoint_uses_saved_test_recipient(self):
        self.save_mail_settings({"mail_test_recipient": "saved-recipient@example.com"})

        response = self.client.post(
            "/api/admin/mail/test",
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["to_email"], "saved-recipient@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["saved-recipient@example.com"])


class UserResourceSerializationTests(TestCase):
    def test_serialize_user_payload_keeps_registered_primary_group_field(self):
        user = User.objects.create_user(
            username="resource-user",
            email="resource-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="ResourceGroup", color="#16a085", icon="fas fa-user")
        user.user_groups.add(group)

        summary_payload = serialize_user_summary(user)
        discussion_payload = serialize_user_payload(user, resource="discussion_user")

        self.assertEqual(summary_payload["username"], user.username)
        self.assertEqual(summary_payload["primary_group"]["name"], group.name)
        self.assertEqual(discussion_payload["primary_group"]["name"], group.name)


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

        with patch("extensions.users.backend.tasks.send_password_reset_email_task.delay") as delay:
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

        with patch("extensions.users.backend.tasks.send_password_reset_email_task.delay", side_effect=RuntimeError("queue down")):
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
        bootstrap_enabled_extension_application("uploads")
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

    @patch("extensions.users.backend.handlers.UserAvatarUploadService.delete_avatar")
    @patch("extensions.users.backend.handlers.UserAvatarUploadService.upload_avatar")
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

    @patch("extensions.users.backend.handlers.UserAvatarUploadService.upload_avatar")
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

    def test_avatar_upload_limit_comes_from_uploads_extension_settings(self):
        save_extension_settings("uploads", {"avatar_max_size_mb": 3, "avatars_dir": "profile-images"})

        self.assertEqual(UserAvatarUploadService.get_avatar_upload_limit_mb(), 3)
        self.assertEqual(UserAvatarUploadService.get_avatar_upload_limit_bytes(), 3 * 1024 * 1024)
        self.assertEqual(UserAvatarUploadService.get_avatars_dir(), "profile-images")

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

    def test_user_detail_supports_resource_field_selection(self):
        user = User.objects.create_user(
            username="group-profile-fields",
            email="group-profile-fields@example.com",
            password="password123",
            bio="这段简介不应返回",
        )
        group = Group.objects.create(name="SupportFields", color="#27ae60", icon="fas fa-life-ring")
        user.user_groups.add(group)

        response = self.client.get(f"/api/users/{user.id}", {"fields[user_detail]": "primary_group"})

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["primary_group"]["name"], "SupportFields")
        self.assertIn("bio", payload)

    def test_user_detail_supports_resource_include_for_groups(self):
        user = User.objects.create_user(
            username="group-profile-include",
            email="group-profile-include@example.com",
            password="password123",
        )
        group = Group.objects.create(name="SupportInclude", color="#27ae60", icon="fas fa-life-ring")
        user.user_groups.add(group)

        response = self.client.get(
            f"/api/users/{user.id}",
            {"fields[user_detail]": "primary_group", "include": "groups"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["primary_group"]["name"], "SupportInclude")
        self.assertIn("groups", payload)
        self.assertEqual(payload["groups"][0]["name"], "SupportInclude")

    def test_user_detail_static_route_uses_resource_endpoint_mutator(self):
        user = User.objects.create_user(
            username="resource-profile",
            email="resource-profile@example.com",
            password="password123",
        )

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
        for endpoint in user_resource_endpoints():
            registry.register_endpoint(endpoint)
        registry.register_endpoint(
            ResourceEndpointDefinition(
                resource="user_detail",
                endpoint="show",
                module_id="test",
                operation="mutate",
                mutator=mutate_endpoint,
            )
        )

        with patch("extensions.users.backend.handlers.get_runtime_resource_registry", return_value=registry):
            with patch("apps.core.resource_dispatcher.get_runtime_resource_registry", return_value=registry):
                response = self.client.get(f"/api/users/{user.id}")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["mutated_by_resource_endpoint"])

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

    def test_session_state_reports_guest_without_auth(self):
        response = self.client.get("/api/users/session")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json(), {"authenticated": False, "user": None})

    def test_session_state_reports_authenticated_user(self):
        user = User.objects.create_user(
            username="session-user",
            email="session-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        token = str(RefreshToken.for_user(user).access_token)

        response = self.client.get(
            "/api/users/session",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertTrue(payload["authenticated"])
        self.assertEqual(payload["user"]["username"], "session-user")
        self.assertEqual(payload["user"]["forum_permissions"], sorted(payload["user"]["forum_permissions"]))

    def test_forum_permissions_include_runtime_processed_groups(self):
        user = User.objects.create_user(
            username="runtime-group-permission",
            email="runtime-group-permission@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        group = Group.objects.create(name="RuntimeGroup", color="#27ae60", icon="fas fa-key")
        Permission.objects.create(group=group, permission="runtime.group.permission")

        with patch("apps.core.extensions.system_runtime.apply_runtime_user_group_processors", return_value=[group.id]):
            self.assertEqual(
                UserService.get_forum_permission_set(user),
                {"runtime.group.permission"},
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
        self.assertEqual(response.json()["message"], "没有权限查看用户列表")
        self.assertEqual(response.json()["code"], "forbidden")

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

    def test_list_users_avoids_n_plus_one_for_primary_group(self):
        viewer = User.objects.create_user(
            username="user-list-preload-viewer",
            email="user-list-preload-viewer@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        viewer_group = Group.objects.create(name="PreloadViewers", color="#2ecc71")
        Permission.objects.create(group=viewer_group, permission="viewUserList")
        viewer.user_groups.add(viewer_group)

        for index in range(3):
            listed_user = User.objects.create_user(
                username=f"listed-user-preload-{index}",
                email=f"listed-user-preload-{index}@example.com",
                password="password123",
                is_email_confirmed=True,
            )
            support_group = Group.objects.create(name=f"SupportPreload{index}", color="#3498db")
            listed_user.user_groups.add(support_group)

        token = str(RefreshToken.for_user(viewer).access_token)
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(
                "/api/users",
                HTTP_AUTHORIZATION=f"Bearer {token}",
            )

        self.assertEqual(response.status_code, 200, response.content)
        select_group_queries = [
            query["sql"]
            for query in context.captured_queries
            if "user_groups" in query["sql"].lower()
        ]
        self.assertLessEqual(len(select_group_queries), 2)

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

    def test_list_users_normalizes_page_and_limit(self):
        viewer = User.objects.create_user(
            username="user-limit-viewer",
            email="user-limit-viewer@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        viewer_group = Group.objects.create(name="LimitViewers", color="#16a085")
        Permission.objects.create(group=viewer_group, permission="viewUserList")
        viewer.user_groups.add(viewer_group)
        token = str(RefreshToken.for_user(viewer).access_token)

        response = self.client.get(
            "/api/users",
            {"page": 0, "limit": 999},
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertLessEqual(len(response.json()), 100)


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


class AuthRateLimitTests(TestCase):
    remote_addr = "203.0.113.80"

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="rate-limit-user",
            email="rate-limit@example.com",
            password="password123",
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_login_rate_limits_repeated_failures_by_identifier(self):
        for _ in range(5):
            response = self.client.post(
                "/api/users/login",
                data=json.dumps({
                    "identification": "rate-limit-user",
                    "password": "wrong-password",
                }),
                content_type="application/json",
                REMOTE_ADDR=self.remote_addr,
            )
            self.assertEqual(response.status_code, 401, response.content)
            self.assertEqual(response.json()["error"], "用户名或密码错误")

        response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "rate-limit-user",
                "password": "wrong-password",
            }),
            content_type="application/json",
            REMOTE_ADDR=self.remote_addr,
        )

        self.assertEqual(response.status_code, 429, response.content)

    def test_register_rate_limits_repeated_validation_failures(self):
        for _ in range(5):
            response = self.client.post(
                "/api/users/register",
                data=json.dumps({
                    "username": "rate-limit-user",
                    "email": "rate-limit@example.com",
                    "password": "password123",
                }),
                content_type="application/json",
                REMOTE_ADDR=self.remote_addr,
            )
            self.assertEqual(response.status_code, 400, response.content)

        response = self.client.post(
            "/api/users/register",
            data=json.dumps({
                "username": "rate-limit-user",
                "email": "rate-limit@example.com",
                "password": "password123",
            }),
            content_type="application/json",
            REMOTE_ADDR=self.remote_addr,
        )

        self.assertEqual(response.status_code, 429, response.content)

    def test_forgot_password_hides_unknown_email(self):
        response = self.client.post(
            "/api/users/forgot-password",
            data=json.dumps({"email": "missing@example.com"}),
            content_type="application/json",
            REMOTE_ADDR=self.remote_addr,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["message"], "重置密码邮件已发送")
        self.assertFalse(PasswordToken.objects.exists())

    def test_forgot_password_rate_limits_repeated_requests(self):
        for _ in range(5):
            response = self.client.post(
                "/api/users/forgot-password",
                data=json.dumps({"email": self.user.email}),
                content_type="application/json",
                REMOTE_ADDR=self.remote_addr,
            )
            self.assertEqual(response.status_code, 200, response.content)

        response = self.client.post(
            "/api/users/forgot-password",
            data=json.dumps({"email": self.user.email}),
            content_type="application/json",
            REMOTE_ADDR=self.remote_addr,
        )

        self.assertEqual(response.status_code, 429, response.content)


@override_settings(DEBUG=False, CSRF_COOKIE_SECURE=True)
class TokenCookieAuthTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="token-cookie-user",
            email="token-cookie@example.com",
            password="password123",
        )

    def _bootstrap_csrf(self, client: Client):
        response = client.get("/api/csrf", secure=True)
        self.assertEqual(response.status_code, 200, response.content)
        token = response.cookies["csrftoken"].value
        self.assertTrue(token)
        return token, response.cookies["csrftoken"]

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

        access_cookie = response.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        cookie = response.cookies.get("bias_refresh_token")
        self.assertIsNotNone(access_cookie)
        self.assertTrue(access_cookie["httponly"])
        self.assertTrue(access_cookie["secure"])
        self.assertEqual(access_cookie["samesite"], "Lax")
        self.assertEqual(access_cookie["path"], "/")
        self.assertIsNotNone(cookie)
        self.assertTrue(cookie["httponly"])
        self.assertTrue(cookie["secure"])
        self.assertEqual(cookie["samesite"], "Lax")
        self.assertEqual(cookie["path"], "/api/users")

    def test_login_uses_shorter_default_access_token_lifetime(self):
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
        access = RefreshToken(response.cookies["bias_refresh_token"].value).access_token
        lifetime_seconds = int((access["exp"] - access["iat"]))
        self.assertEqual(lifetime_seconds, 900)

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
        self.assertIsNotNone(response.cookies.get(ACCESS_TOKEN_COOKIE_NAME))

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
        access_cookie = response.cookies.get(ACCESS_TOKEN_COOKIE_NAME)
        cookie = response.cookies.get("bias_refresh_token")
        self.assertIsNotNone(access_cookie)
        self.assertEqual(access_cookie.value, "")
        self.assertEqual(access_cookie["path"], "/")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, "")
        self.assertEqual(cookie["path"], "/api/users")

    def test_current_user_accepts_access_cookie_without_authorization_header(self):
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

        response = self.client.get("/api/users/me", secure=True)

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["username"], "token-cookie-user")

    def test_csrf_bootstrap_sets_secure_cookie(self):
        csrf_client = Client(enforce_csrf_checks=True)

        token, response_cookie = self._bootstrap_csrf(csrf_client)

        self.assertEqual(token, csrf_client.cookies["csrftoken"].value)
        self.assertTrue(response_cookie["secure"])
        self.assertEqual(response_cookie["samesite"], "Lax")

    def test_login_requires_csrf_when_checks_enabled(self):
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "token-cookie-user",
                "password": "password123",
            }),
            content_type="application/json",
            secure=True,
            HTTP_REFERER="https://testserver/",
        )

        self.assertEqual(response.status_code, 403, response.content)

    def test_login_accepts_csrf_when_checks_enabled(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_token, _ = self._bootstrap_csrf(csrf_client)

        response = csrf_client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "token-cookie-user",
                "password": "password123",
            }),
            content_type="application/json",
            secure=True,
            HTTP_REFERER="https://testserver/",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["access"])

    def test_refresh_access_token_requires_csrf_when_checks_enabled(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_token, _ = self._bootstrap_csrf(csrf_client)

        login_response = csrf_client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "token-cookie-user",
                "password": "password123",
            }),
            content_type="application/json",
            secure=True,
            HTTP_REFERER="https://testserver/",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)

        response = csrf_client.post(
            "/api/users/token/refresh",
            secure=True,
            HTTP_REFERER="https://testserver/",
        )

        self.assertEqual(response.status_code, 403, response.content)

    def test_refresh_access_token_accepts_csrf_when_checks_enabled(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_token, _ = self._bootstrap_csrf(csrf_client)

        login_response = csrf_client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "token-cookie-user",
                "password": "password123",
            }),
            content_type="application/json",
            secure=True,
            HTTP_REFERER="https://testserver/",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(login_response.status_code, 200, login_response.content)

        response = csrf_client.post(
            "/api/users/token/refresh",
            secure=True,
            HTTP_REFERER="https://testserver/",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["access"])


class SecurityHeadersTests(TestCase):
    def test_api_responses_include_security_headers(self):
        response = self.client.get("/api/system/status")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertIn("Content-Security-Policy", response)
        self.assertEqual(response["Referrer-Policy"], "strict-origin-when-cross-origin")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")


class HumanVerificationAuthTests(TestCase):
    def setUp(self):
        from extensions.testing import bootstrap_enabled_extension_application

        bootstrap_enabled_extension_application("security")
        self.user = User.objects.create_user(
            username="human-check-user",
            email="human-check@example.com",
            password="password123",
        )

    def tearDown(self):
        clear_runtime_setting_caches()
        super().tearDown()

    def enable_turnstile(self, *, login_enabled=True, register_enabled=True):
        save_extension_settings("security", {
            "auth_human_verification_provider": "turnstile",
            "auth_turnstile_site_key": "site-key",
            "auth_turnstile_secret_key": "secret-key",
            "auth_human_verification_login_enabled": login_enabled,
            "auth_human_verification_register_enabled": register_enabled,
        })
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

    @patch("extensions.security.backend.human_verification.httpx.post")
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

    @patch("extensions.security.backend.human_verification.httpx.post")
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

    @patch("extensions.security.backend.human_verification.httpx.post")
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

    def test_public_forum_settings_expose_human_verification_public_fields(self):
        self.enable_turnstile(login_enabled=True, register_enabled=False)

        response = self.client.get("/api/forum")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["auth_human_verification_provider"], "turnstile")
        self.assertEqual(payload["auth_turnstile_site_key"], "site-key")
        self.assertTrue(payload["auth_human_verification_login_enabled"])
        self.assertFalse(payload["auth_human_verification_register_enabled"])
        self.assertNotIn("auth_turnstile_secret_key", payload)

    def test_security_extension_settings_persist_human_verification_config(self):
        admin = User.objects.create_superuser(
            username="human-admin",
            email="human-admin@example.com",
            password="password123",
        )
        response = self.client.post(
            "/api/users/login",
            data=json.dumps({
                "identification": "human-admin",
                "password": "password123",
            }),
            content_type="application/json",
        )
        access = response.json()["access"]

        response = self.client.post(
            "/api/admin/extensions/security/settings",
            data=json.dumps({
                "auth_human_verification_provider": "turnstile",
                "auth_turnstile_site_key": "site-key",
                "auth_turnstile_secret_key": "secret-key",
                "auth_human_verification_login_enabled": True,
                "auth_human_verification_register_enabled": False,
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["settings"]["auth_human_verification_provider"], "turnstile")
        self.assertEqual(
            json.loads(Setting.objects.get(key="extensions.security.auth_human_verification_provider").value),
            "turnstile",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="extensions.security.auth_turnstile_site_key").value),
            "site-key",
        )
        self.assertEqual(
            json.loads(Setting.objects.get(key="extensions.security.auth_human_verification_register_enabled").value),
            False,
        )

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

        with patch("extensions.users.backend.tasks.send_verification_email_task.delay") as delay:
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

        with self.captureOnCommitCallbacks(execute=True):
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

        audit_log = AuditLog.objects.get(action="admin.user.update", target_id=self.user.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "user")
        self.assertIn("is_staff", audit_log.data["changed_fields"])
        self.assertTrue(audit_log.data["groups_changed"])

    def test_admin_unsuspending_user_creates_recovery_notification(self):
        self.user.suspended_until = timezone.now() + timedelta(days=2)
        self.user.suspend_reason = "temporary"
        self.user.suspend_message = "请等待处理"
        self.user.save(update_fields=["suspended_until", "suspend_reason", "suspend_message"])

        with self.captureOnCommitCallbacks(execute=True):
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

    def test_admin_suspension_event_dispatches_after_commit(self):
        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
                response = self.client.put(
                    f"/api/admin/users/{self.user.id}",
                    data=json.dumps({
                        "suspended_until": "2030-01-02T03:04:05Z",
                        "suspend_reason": "spam",
                        "suspend_message": "请联系管理员处理",
                    }),
                    content_type="application/json",
                    **self.auth_header(),
                )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(callbacks), 1)
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertIsInstance(event, UserSuspendedEvent)
        self.assertEqual(event.user_id, self.user.id)
        self.assertEqual(event.actor_user_id, self.admin.id)

    def test_admin_unsuspension_event_dispatches_after_commit(self):
        self.user.suspended_until = timezone.now() + timedelta(days=2)
        self.user.suspend_reason = "temporary"
        self.user.suspend_message = "请等待处理"
        self.user.save(update_fields=["suspended_until", "suspend_reason", "suspend_message"])

        mocked_bus = Mock()
        with patch("apps.core.domain_events.get_forum_event_bus", return_value=mocked_bus):
            with self.captureOnCommitCallbacks(execute=True) as callbacks:
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
        self.assertEqual(len(callbacks), 1)
        event = mocked_bus.dispatch.call_args.args[0]
        self.assertIsInstance(event, UserUnsuspendedEvent)
        self.assertEqual(event.user_id, self.user.id)
        self.assertEqual(event.actor_user_id, self.admin.id)

    def test_admin_can_delete_user(self):
        response = self.client.delete(
            f"/api/admin/users/{self.user.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertFalse(User.objects.filter(id=self.user.id).exists())
        audit_log = AuditLog.objects.get(action="admin.user.delete", target_id=self.user.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.data["username"], "managed-user")

    def test_admin_cannot_delete_self(self):
        response = self.client.delete(
            f"/api/admin/users/{self.admin.id}",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不能删除当前登录的管理员账号")
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())

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
        audit_log = AuditLog.objects.get(action="admin.group.delete", target_id=group.id)
        self.assertEqual(audit_log.user_id, self.admin.id)
        self.assertEqual(audit_log.target_type, "group")
        self.assertEqual(audit_log.data["name"], "Helpers")

    def test_admin_cannot_delete_builtin_group(self):
        response = self.client.delete(
            "/api/admin/groups/1",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "系统默认用户组不允许删除")
        self.assertTrue(Group.objects.filter(id=1, name="Admin").exists())
