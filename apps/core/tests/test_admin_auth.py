from apps.core.tests.common import *

class AdminAuthTests(TestCase):
    def test_require_staff_rejects_non_staff_auth(self):
        from apps.core.admin_auth import require_staff

        request = SimpleNamespace(auth=SimpleNamespace(is_staff=False))

        response = require_staff(request)

        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content)["message"], "需要管理员权限")

    def test_require_staff_allows_staff_auth(self):
        from apps.core.admin_auth import require_staff

        request = SimpleNamespace(auth=SimpleNamespace(is_staff=True))

        self.assertIsNone(require_staff(request))
