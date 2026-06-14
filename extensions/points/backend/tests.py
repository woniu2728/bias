import json
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.core.extension_settings_service import save_extension_settings
from apps.core.extensions.runtime import (
    create_runtime_discussion,
    create_runtime_post,
    get_runtime_user_model,
)
from extensions.points.backend.models import PointLedgerEntry
from extensions.points.backend.services import (
    InsufficientPointsError,
    award_points,
    get_balance,
    spend_points,
)
from extensions.testing import ExtensionRuntimeTestMixin


class RuntimeModelProxy:
    def __init__(self, resolver):
        self._resolver = resolver

    def __getattr__(self, name):
        return getattr(self._resolver(), name)


User = RuntimeModelProxy(get_runtime_user_model)


class PointsExtensionDiagnosticsTests(ExtensionRuntimeTestMixin, TestCase):
    def test_points_extension_registers_runtime_service_provider(self):
        application = self.bootstrap_extensions("points")
        service = application.get_service("points.service")
        runtime_view = application.get_runtime_view("points")

        self.assertIn("points.service", application.get_service_provider_keys(extension_id="points"))
        self.assertTrue(callable(service["award"]))
        self.assertTrue(callable(service["spend"]))
        self.assertIn("discussion_create_reward", {item.key for item in runtime_view.settings_schema})

    def test_inspect_reports_points_extension_without_validation_errors(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "points",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        issues = extension["debug_info"]["validation_issues"]

        self.assertEqual(extension["id"], "points")
        self.assertFalse(any(item["level"] == "error" for item in issues))


class PointsServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="points-user",
            email="points-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_award_and_spend_points_update_balance(self):
        award_points(
            self.user,
            10,
            reason="manual_award",
            idempotency_key="manual:award:1",
        )
        spend_points(
            self.user,
            4,
            reason="manual_spend",
            idempotency_key="manual:spend:1",
        )

        self.assertEqual(get_balance(self.user), 6)
        self.assertEqual(PointLedgerEntry.objects.count(), 2)

    def test_idempotency_key_prevents_duplicate_award(self):
        first = award_points(
            self.user,
            10,
            reason="manual_award",
            idempotency_key="manual:award:duplicate",
        )
        second = award_points(
            self.user,
            10,
            reason="manual_award",
            idempotency_key="manual:award:duplicate",
        )

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(get_balance(self.user), 10)
        self.assertEqual(PointLedgerEntry.objects.count(), 1)

    def test_spend_points_rejects_insufficient_balance(self):
        with self.assertRaises(InsufficientPointsError):
            spend_points(
                self.user,
                5,
                reason="manual_spend",
                idempotency_key="manual:spend:insufficient",
            )


class PointsRewardIntegrationTests(ExtensionRuntimeTestMixin, TestCase):
    def setUp(self):
        self.bootstrap_extensions("points")
        save_extension_settings("points", {
            "enabled": True,
            "discussion_create_reward": 10,
            "reply_create_reward": 3,
            "like_received_reward": 1,
        })
        self.author = User.objects.create_user(
            username="points-author",
            email="points-author@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_discussion_and_reply_creation_award_points_once(self):
        with self.captureOnCommitCallbacks(execute=True):
            discussion = create_runtime_discussion(
                title="Points discussion",
                content="Initial post",
                user=self.author,
            )
        with self.captureOnCommitCallbacks(execute=True):
            create_runtime_post(
                discussion_id=discussion.id,
                content="Rewarded reply",
                user=self.author,
            )

        self.assertEqual(get_balance(self.author), 13)
        reasons = list(PointLedgerEntry.objects.order_by("id").values_list("reason", flat=True))
        self.assertEqual(reasons, ["discussion_created", "reply_created"])
