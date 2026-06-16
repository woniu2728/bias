from apps.core.tests.common import *

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

    def test_init_groups_syncs_registry_managed_admin_permissions(self):
        call_command("init_groups")

        admin_group = Group.objects.get(id=1)
        permissions = set(
            Permission.objects.filter(group=admin_group).values_list("permission", flat=True)
        )

        self.assertTrue(set(get_registry_staff_managed_admin_permission_codes()).issubset(permissions))
        self.assertIn("admin.approval.view", permissions)
        self.assertIn("admin.flag.view", permissions)
        self.assertIn("post.edit", permissions)
        self.assertIn("post.delete", permissions)

        member_permissions = set(
            Permission.objects.filter(group_id=3).values_list("permission", flat=True)
        )
        self.assertIn("post.editOwn", member_permissions)
        self.assertIn("post.deleteOwn", member_permissions)
