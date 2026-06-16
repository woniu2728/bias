from apps.core.tests.common import *

class AdminAuditLogApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="audit-admin",
            email="audit-admin@example.com",
            password="password123",
        )
        self.member = User.objects.create_user(
            username="audit-member",
            email="audit-member@example.com",
            password="password123",
        )

    def auth_header(self, user=None):
        token = RefreshToken.for_user(user or self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_admin_can_list_audit_logs(self):
        AuditLog.objects.create(
            user=self.admin,
            action="admin.cache.clear",
            target_type="cache",
            ip_address="127.0.0.1",
            data={"source": "test"},
        )
        AuditLog.objects.create(
            user=self.admin,
            action="admin.user.delete",
            target_type="user",
            target_id=self.member.id,
            data={"username": self.member.username},
        )
        AuditLog.objects.create(
            user=self.member,
            action="password_reset",
            target_type="user",
            target_id=self.member.id,
            data={"source": "public"},
        )

        response = self.client.get(
            "/api/admin/audit-logs",
            {"target_type": "user"},
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["data"][0]["action"], "admin.user.delete")
        self.assertEqual(payload["data"][0]["target_id"], self.member.id)
        self.assertEqual(payload["data"][0]["user"]["username"], self.admin.username)
        self.assertNotIn("password_reset", {item["action"] for item in payload["data"]})

    def test_non_staff_cannot_list_audit_logs(self):
        response = self.client.get(
            "/api/admin/audit-logs",
            **self.auth_header(self.member),
        )

        self.assertEqual(response.status_code, 403, response.content)
