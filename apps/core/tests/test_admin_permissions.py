from apps.core.tests.common import *

class AdminPermissionsApiTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username="admin-permission-mgr",
            email="admin-permission-mgr@example.com",
            password="password123",
        )
        Group.objects.get_or_create(
            id=1,
            defaults={
                "name": "Admin",
                "name_singular": "Admin",
                "name_plural": "Admins",
                "color": "#B72A2A",
            },
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

    def test_permissions_api_ignores_unknown_stored_codes_on_read(self):
        Permission.objects.create(group=self.group, permission="reply")
        Permission.objects.create(group=self.group, permission="editPosts")

        response = self.client.get(
            "/api/admin/permissions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        group_permissions = payload.get(str(self.group.id), payload.get(self.group.id, []))
        self.assertEqual(group_permissions, [])

    def test_permissions_api_includes_staff_runtime_baseline_for_admin_group(self):
        admin_group = Group.objects.get(id=1)
        Permission.objects.create(group=admin_group, permission="discussion.edit")

        response = self.client.get(
            "/api/admin/permissions",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        admin_permissions = set(payload.get("1", payload.get(1, [])))
        self.assertIn("discussion.edit", admin_permissions)
        self.assertIn("discussion.editOwn", admin_permissions)
        self.assertIn("discussion.deleteOwn", admin_permissions)
        self.assertIn("post.edit", admin_permissions)
        self.assertIn("post.delete", admin_permissions)

    def test_permissions_api_preserves_staff_runtime_baseline_when_saving_admin_group(self):
        admin_group = Group.objects.get(id=1)

        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(admin_group.id): ["discussion.edit"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        saved_permissions = set(
            Permission.objects.filter(group=admin_group).values_list("permission", flat=True)
        )
        self.assertIn("discussion.edit", saved_permissions)
        self.assertIn("discussion.editOwn", saved_permissions)
        self.assertIn("discussion.deleteOwn", saved_permissions)
        self.assertIn("post.edit", saved_permissions)
        self.assertIn("post.delete", saved_permissions)

    def test_permissions_api_rejects_unknown_codes_on_save(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["reply", "editPosts", "reply"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Permission.objects.filter(group=self.group).count(), 0)

    def test_permissions_api_expands_required_permissions_on_save(self):
        response = self.client.post(
            "/api/admin/permissions",
            data=json.dumps({
                str(self.group.id): ["replyWithoutApproval"],
            }),
            content_type="application/json",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            set(Permission.objects.filter(group=self.group).values_list("permission", flat=True)),
            {"replyWithoutApproval", "discussion.reply", "viewForum"},
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

    def test_permissions_meta_api_returns_registry_sections(self):
        response = self.client.get(
            "/api/admin/permissions/meta",
            **self.auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertIn("sections", payload)
        self.assertIn("modules", payload)
        self.assertNotIn("aliases", payload)
        section_names = {section["name"] for section in payload["sections"]}
        self.assertIn("view", section_names)
        self.assertIn("moderate", section_names)
        all_permission_codes = {
            permission["name"]
            for section in payload["sections"]
            for permission in section["permissions"]
        }
        self.assertIn("discussion.reply", all_permission_codes)
        for section in payload["sections"]:
            for permission in section["permissions"]:
                self.assertNotIn("aliases", permission)
        self.assertTrue(any(module["id"] == "core" for module in payload["modules"]))
