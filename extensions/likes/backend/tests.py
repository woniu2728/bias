import json
from io import StringIO
from pathlib import Path
import shutil
import uuid
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase
from ninja_jwt.tokens import RefreshToken

from apps.core.extension_settings_service import save_extension_settings
from apps.core.extensions.bootstrap import build_extension_application
from apps.core.extensions.registry import ExtensionRegistry
from extensions.testing import ExtensionRuntimeTestMixin, get_resource_registry
from apps.core.extensions.runtime import (
    can_runtime_like_post,
    create_runtime_discussion,
    like_runtime_post,
)
from apps.core.models import ExtensionInstallation
from apps.core.extensions.runtime import (
    create_runtime_post,
)
from apps.core.extensions.runtime import (
    get_runtime_user_model,
)


class RuntimeModelProxy:
    def __init__(self, resolver):
        self._resolver = resolver

    def __getattr__(self, name):
        return getattr(self._resolver(), name)


User = RuntimeModelProxy(get_runtime_user_model)


class LikesExtensionDiagnosticsTests(ExtensionRuntimeTestMixin, TestCase):
    def test_likes_extension_registers_runtime_service_provider(self):
        application = self.bootstrap_extensions("likes")
        service = application.get_service("likes.service")

        self.assertIn("likes.service", application.get_service_provider_keys(extension_id="likes"))
        self.assertEqual(service["model"].__name__, "PostLike")
        for key in ("like_post", "unlike_post", "can_like_post"):
            self.assertTrue(callable(service[key]), key)

    def test_likes_capabilities_are_filtered_when_extension_disabled(self):
        self.disable_extension_for_test("likes")

        resource_registry = get_resource_registry()

        self.assertFalse(any(item.module_id == "likes" for item in resource_registry.get_fields("post")))
        self.assertIsNone(resource_registry.get_dispatch_endpoint("post", "like", "POST", {}))

    def test_inspect_reports_likes_model_as_extension_native(self):
        stdout = StringIO()
        call_command(
            "inspect_extensions",
            "--extension-id",
            "likes",
            stdout=stdout,
        )
        payload = json.loads(stdout.getvalue())
        extension = payload["extensions"][0]
        audit = extension["model_ownership_audit"]
        owned_item = audit["items"][0]

        self.assertEqual(extension["id"], "likes")
        self.assertIn("0001_state_post_like.py", extension["migration_plan"]["pending_files"])
        self.assertEqual(audit["extension_native_count"], 1)
        self.assertEqual(audit["app_label_migration_required_count"], 0)
        self.assertEqual(audit["app_label_migration_plan_required_count"], 0)
        self.assertTrue(all(item["storage_origin"] == "extension" for item in audit["items"]))
        self.assertTrue(all(item["model_module"].startswith("extensions.likes") for item in audit["items"]))
        self.assertEqual(audit["app_label_migration_items"], [])
        self.assertEqual(owned_item["current_app_label"], "likes")
        self.assertEqual(owned_item["target_app_label"], "likes")
        self.assertEqual(owned_item["migration_risk"], "none")


class LikesExtensionTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(
            username="like_author",
            email="like_author@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.liker = User.objects.create_user(
            username="like_user",
            email="like_user@example.com",
            password="password123",
            is_email_confirmed=True,
        )
        self.admin = User.objects.create_superuser(
            username="like-admin",
            email="like-admin@example.com",
            password="password123",
        )
        self.discussion = create_runtime_discussion(
            title="Like discussion",
            content="Initial post",
            user=self.author,
        )
        self.post = create_runtime_post(
            discussion_id=self.discussion.id,
            content="Reply to like",
            user=self.author,
        )

    def admin_auth_header(self):
        token = RefreshToken.for_user(self.admin).access_token
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    def test_extension_detail_api_surfaces_registered_resources_for_likes_extension(self):
        response = self.client.get(
            "/api/admin/extensions/likes",
            **self.admin_auth_header(),
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = response.json()["extension"]
        self.assertEqual(payload["frontend_forum_entry"], "extensions/likes/frontend/forum/index.js")
        like_fields = {
            item["field"]
            for item in payload["resource_fields"]
            if item["module_id"] == "likes"
        }
        self.assertIn("like_count", like_fields)
        self.assertIn("is_liked", like_fields)
        self.assertIn("can_like", like_fields)
        self.assertTrue(
            any(item["module_id"] == "likes" and item["endpoint"] == "like" for item in payload["resource_endpoints"])
        )
        self.assertTrue(any(item["key"] == "like_own_post" for item in payload["settings_schema"]))
        self.assertTrue(any(item["code"] == "likedBy" for item in payload["search_filters"]))
        self.assertTrue(any(item["module_id"] == "likes" and item["relationship"] == "likes" for item in payload["resource_relationships"]))
        self.assertTrue(any(item["module_id"] == "likes" and item["filter"] == "likedBy" for item in payload["resource_filters"]))
        self.assertTrue(any(item["code"] == "postLiked" for item in payload["notification_types"]))

    def test_post_like_preload_uses_count_annotation_without_loading_all_likes(self):
        registry = get_resource_registry()

        default_plan = registry.build_preload_plan("post", {"user": self.liker})
        default_prefetch_targets = {
            getattr(item, "to_attr", "")
            for item in default_plan.prefetch_related
        }
        include_plan = registry.build_preload_plan("post", {"user": self.liker}, include=("likes",))
        include_prefetch_targets = {
            getattr(item, "to_attr", "")
            for item in include_plan.prefetch_related
        }
        default_annotation_names = {name for name, _expression in default_plan.annotations}

        self.assertIn("likes_count", default_annotation_names)
        self.assertIn("viewer_likes_cache", default_prefetch_targets)
        self.assertNotIn("likes_cache", default_prefetch_targets)
        self.assertIn("likes_cache", include_prefetch_targets)

    def test_post_global_index_reports_likes_from_annotation(self):
        with self.captureOnCommitCallbacks(execute=True):
            like_runtime_post(self.post.id, self.liker)
        token = RefreshToken.for_user(self.liker).access_token

        response = self.client.get(
            "/api/posts",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)
        payload = next(item for item in response.json()["data"] if item["id"] == self.post.id)
        self.assertEqual(payload["like_count"], 1)
        self.assertTrue(payload["is_liked"])

    def test_duplicate_like_raises_value_error_not_integrity_error(self):
        with self.captureOnCommitCallbacks(execute=True):
            like_runtime_post(self.post.id, self.liker)

        with self.assertRaisesMessage(ValueError, "已经点赞过了"):
            like_runtime_post(self.post.id, self.liker)

    def test_like_own_post_returns_bad_request_in_api(self):
        token = RefreshToken.for_user(self.author).access_token

        response = self.client.post(
            f"/api/posts/{self.post.id}/like",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(response.json()["error"], "不能给自己的帖子点赞")

    def test_like_own_post_setting_allows_author_to_like_own_post(self):
        save_extension_settings("likes", {"like_own_post": True})
        token = RefreshToken.for_user(self.author).access_token

        response = self.client.post(
            f"/api/posts/{self.post.id}/like",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, 200, response.content)

    def test_post_global_index_supports_liked_by_extension_filter(self):
        other_post = create_runtime_post(
            discussion_id=self.discussion.id,
            content="Reply not liked",
            user=self.author,
        )
        with self.captureOnCommitCallbacks(execute=True):
            like_runtime_post(self.post.id, self.liker)

        response = self.client.get(
            "/api/posts",
            {"filter[likedBy]": self.liker.username},
        )

        self.assertEqual(response.status_code, 200, response.content)
        ids = [item["id"] for item in response.json()["data"]]
        self.assertIn(self.post.id, ids)
        self.assertNotIn(other_post.id, ids)

    def test_post_search_supports_liked_by_extension_filter(self):
        other_post = create_runtime_post(
            discussion_id=self.discussion.id,
            content="Reply to like",
            user=self.author,
        )
        with self.captureOnCommitCallbacks(execute=True):
            like_runtime_post(self.post.id, self.liker)

        response = self.client.get(
            "/api/search",
            {"q": f"Reply likedBy:{self.liker.username}", "type": "posts"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        ids = [item["id"] for item in response.json()["posts"]]
        self.assertIn(self.post.id, ids)
        self.assertNotIn(other_post.id, ids)

    def test_like_post_dispatches_domain_event_instead_of_direct_notification_call(self):
        with patch("apps.core.extensions.runtime.notify_runtime_notification") as notify_mock:
            with self.captureOnCommitCallbacks(execute=True):
                like_runtime_post(self.post.id, self.liker)

        notify_mock.assert_called_once_with("notify_post_liked", post_id=self.post.id, from_user=self.liker)

    def test_like_post_dispatches_domain_event_after_commit(self):
        with patch("apps.core.domain_events.get_forum_event_bus") as get_bus_mock:
            bus_mock = Mock()
            get_bus_mock.return_value = bus_mock

            with self.captureOnCommitCallbacks() as callbacks:
                like_runtime_post(self.post.id, self.liker)

            self.assertEqual(len(callbacks), 1)
            bus_mock.dispatch.assert_not_called()

            callbacks[0]()

        bus_mock.dispatch.assert_called_once()

    def test_policy_extender_can_deny_like_post(self):
        temp_dir, registry = _build_like_policy_extension_registry()
        try:
            blocker = User.objects.create_user(
                username="blocked-liker",
                email="blocked-liker@example.com",
                password="password123",
                is_email_confirmed=True,
            )

            self.assertTrue(can_runtime_like_post(self.post, blocker))

            with patch(
                "apps.core.extensions.policy_runtime_service.get_extension_application",
                return_value=build_extension_application(manager=registry, force=True),
            ):
                self.assertFalse(can_runtime_like_post(self.post, blocker))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def _make_workspace_temp_dir() -> Path:
    path = Path.cwd() / f"tmp-test-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _build_like_policy_extension_registry() -> tuple[Path, ExtensionRegistry]:
    temp_dir = _make_workspace_temp_dir()
    extensions_dir = temp_dir / "extensions"
    manifest_dir = extensions_dir / "likes-policy"
    backend_dir = manifest_dir / "backend"
    backend_dir.mkdir(parents=True, exist_ok=False)
    (manifest_dir / "extension.json").write_text(json.dumps({
        "id": "likes-policy",
        "name": "Likes Policy",
        "version": "1.0.0",
        "backend_entry": "extensions.likes_policy.backend.ext",
    }, ensure_ascii=False), encoding="utf-8")
    (backend_dir / "ext.py").write_text(
        "from apps.core.extensions import PolicyExtender\n"
        "\n"
        "def deny_post_like(user=None, post=None, **kwargs):\n"
        "    if user and post and user.username == 'blocked-liker':\n"
        "        return False\n"
        "    return None\n"
        "\n"
        "def extend():\n"
        "    return [PolicyExtender(mounts=(('post.like', deny_post_like),))]\n",
        encoding="utf-8",
    )
    ExtensionInstallation.objects.create(
        extension_id="likes-policy",
        version="1.0.0",
        source="filesystem",
        enabled=True,
        installed=True,
        booted=True,
    )
    return temp_dir, ExtensionRegistry(extensions_path=extensions_dir)


