from apps.core.tests.common import *

class SystemStatusApiTests(TestCase):
    def test_system_status_endpoint_returns_ready_state(self):
        response = self.client.get("/api/system/status")

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()
        self.assertEqual(payload["state"], "ready")
        self.assertIn("current_version", payload)
