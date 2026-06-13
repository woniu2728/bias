import json
import re
from io import StringIO
from unittest.mock import Mock, patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.core.extension_settings_service import save_extension_settings
from apps.core.extensions.runtime_access import create_runtime_discussion, get_runtime_user_model
from extensions.points.backend.models import PointLedgerEntry
from extensions.points.backend.services import award_points, get_account, get_balance
from extensions.ai.backend.services import AiService
from extensions.testing import ExtensionRuntimeTestMixin


class RuntimeModelProxy:
    def __init__(self, resolver):
        self._resolver = resolver

    def __getattr__(self, name):
        return getattr(self._resolver(), name)


User = RuntimeModelProxy(get_runtime_user_model)


class AiExtensionDiagnosticsTests(ExtensionRuntimeTestMixin, TestCase):
    def test_ai_extension_backend_uses_runtime_targets_not_cross_extension_internal_imports(self):
        ai_backend_dir = settings.BASE_DIR / "extensions" / "ai" / "backend"
        violations = []
        pattern = re.compile(r"^(?:from|import)\s+extensions\.(?!ai\b)", re.MULTILINE)
        for path in sorted(ai_backend_dir.rglob("*.py")):
            if path.name == "tests.py" or "__pycache__" in path.parts:
                continue
            source = path.read_text(encoding="utf-8")
            if pattern.search(source):
                violations.append(path.relative_to(settings.BASE_DIR).as_posix())

        self.assertEqual(violations, [])

    def test_inspect_reports_ai_extension_without_validation_errors(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "ai",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        issues = extension["debug_info"]["validation_issues"]

        self.assertEqual(extension["id"], "ai")
        self.assertEqual(extension["frontend_forum_entry"], "extensions/ai/frontend/forum/index.js")
        self.assertTrue(extension["debug_info"]["frontend_forum_entry"]["exists"])
        self.assertFalse(any(item["level"] == "error" for item in issues))

    def test_ai_extension_registers_settings_and_service_provider(self):
        application = self.bootstrap_extensions("ai")
        service = application.get_service("ai.service")
        runtime_view = application.get_runtime_view("ai")

        self.assertIn("ai.service", application.get_service_provider_keys(extension_id="ai"))
        self.assertTrue(callable(service["coach_question"]))
        self.assertIn("base_url", {item.key for item in runtime_view.settings_schema})
        self.assertIn("api_key", {item.key for item in runtime_view.settings_schema})
        self.assertEqual(runtime_view.forum_settings_keys, ("enabled", "fallback_enabled", "model"))


class AiServiceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="ai_author",
            email="ai_author@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_question_coach_returns_fallback_without_remote_settings(self):
        save_extension_settings("ai", {
            "enabled": True,
            "base_url": "",
            "api_key": "",
            "fallback_enabled": True,
        })

        payload = AiService.coach_question(title="bug", content="报错了")

        self.assertEqual(payload["mode"], "fallback")
        self.assertEqual(payload["action"], "question_coach")
        self.assertTrue(payload["cards"])

    @patch("extensions.ai.backend.services.httpx.post")
    def test_question_coach_calls_openai_compatible_endpoint_when_configured(self, post):
        save_extension_settings("ai", {
            "enabled": True,
            "base_url": "https://ai.example.test/v1/",
            "api_key": "test-key",
            "model": "test-model",
            "timeout_seconds": 12,
            "temperature_tenths": 2,
            "fallback_enabled": True,
        })
        response = Mock()
        response.json.return_value = {
            "choices": [
                {"message": {"content": "远程建议"}},
            ],
        }
        post.return_value = response

        payload = AiService.coach_question(title="如何排查性能问题", content="后台点击很慢，已经看过日志。")

        self.assertEqual(payload["mode"], "remote")
        self.assertEqual(payload["text"], "远程建议")
        post.assert_called_once()
        call = post.call_args.kwargs
        self.assertEqual(call["url"] if "url" in call else post.call_args.args[0], "https://ai.example.test/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], "Bearer test-key")
        self.assertEqual(call["json"]["model"], "test-model")
        self.assertEqual(call["timeout"], 12)


class AiPointsIntegrationTests(ExtensionRuntimeTestMixin, TestCase):
    def setUp(self):
        self.bootstrap_extensions("points", "ai")
        self.user = User.objects.create_user(
            username="ai-points-user",
            email="ai-points-user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        save_extension_settings("points", {
            "enabled": True,
            "ai_question_coach_cost": 2,
            "ai_role_summon_cost": 3,
            "ai_bounty_judge_cost": 5,
            "ai_discussion_summary_cost": 8,
        })
        save_extension_settings("ai", {
            "enabled": True,
            "base_url": "",
            "api_key": "",
            "fallback_enabled": True,
        })
        award_points(
            self.user,
            10,
            reason="test_seed",
            idempotency_key="ai-points:seed",
        )

    def test_ai_fallback_charges_configured_points(self):
        payload = AiService.coach_question(
            title="如何排查后台很慢",
            content="后台点击很慢，已经看过日志。",
            user=self.user,
        )

        self.assertEqual(payload["mode"], "fallback")
        self.assertEqual(payload["points"]["cost"], 2)
        self.assertEqual(get_balance(self.user), 8)
        self.assertTrue(PointLedgerEntry.objects.filter(reason="ai_question_coach", delta=-2).exists())

    @patch("extensions.ai.backend.services.httpx.post")
    def test_ai_remote_failure_refunds_charged_points(self, post):
        save_extension_settings("ai", {
            "enabled": True,
            "base_url": "https://ai.example.test/v1",
            "api_key": "test-key",
            "fallback_enabled": False,
        })
        post.side_effect = RuntimeError("remote down")

        with self.assertRaises(RuntimeError):
            AiService.coach_question(
                title="如何排查后台很慢",
                content="后台点击很慢，已经看过日志。",
                user=self.user,
            )

        self.assertEqual(get_balance(self.user), 10)
        account = get_account(self.user)
        self.assertEqual(account.earned_total, 10)
        self.assertEqual(account.spent_total, 2)
        self.assertTrue(PointLedgerEntry.objects.filter(reason="ai_question_coach", delta=-2).exists())
        self.assertTrue(PointLedgerEntry.objects.filter(reason="ai_question_coach_refund", delta=2).exists())


class AiDiscussionSummaryTests(ExtensionRuntimeTestMixin, TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="ai_summary_author",
            email="ai_summary_author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.reader = User.objects.create_user(
            username="ai_summary_reader",
            email="ai_summary_reader@example.com",
            password="password123",
            is_email_confirmed=True,
        )

    def test_hidden_discussion_summary_does_not_expose_title_to_regular_user(self):
        discussion = create_runtime_discussion(
            title="Private AI summary title",
            content="Hidden content",
            user=self.author,
        )
        discussion.hidden_at = timezone.now()
        discussion.save(update_fields=["hidden_at"])

        with self.assertRaisesMessage(ValueError, "讨论不存在"):
            AiService.summarize_discussion(discussion_id=discussion.id, user=self.reader)
