from apps.core.tests.common import *

class ExtensionPolicyIntegrationTests(TestCase):
    def test_authorization_decision_priority_matches_gate_semantics(self):
        from apps.core.authorization import (
            allow,
            assert_can,
            AuthorizationPolicy,
            can,
            deny,
            force_allow,
            force_deny,
            resolve_authorization_decision,
        )

        self.assertFalse(resolve_authorization_decision([allow(), force_deny(), force_allow()], default=True))
        self.assertTrue(resolve_authorization_decision([deny(), force_allow()], default=False))
        self.assertFalse(resolve_authorization_decision([allow(), deny()], default=True))
        self.assertTrue(resolve_authorization_decision([allow()], default=False))
        self.assertIsNone(resolve_authorization_decision([None], default=None))
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=True) as evaluate:
            self.assertTrue(can("actor", "discussion.edit", "discussion"))
            assert_can("actor", "discussion.edit", "discussion")
        evaluate.assert_called_with("discussion.edit", user="actor", model="discussion", default=None)
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=False):
            with self.assertRaises(PermissionError):
                assert_can("actor", "discussion.edit", "discussion")
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=None):
            with patch("apps.core.forum_permissions.has_forum_permission", return_value=True) as has_permission:
                self.assertTrue(can("actor", "discussion.edit", "discussion"))
        has_permission.assert_called_with("actor", "discussion.edit")
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=None):
            with patch("apps.core.forum_permissions.has_forum_permission", return_value=False):
                self.assertFalse(can("actor", "discussion.edit", "discussion"))
        with patch("apps.core.extensions.policy_runtime_service.evaluate_model_policy", return_value=None):
            with patch("apps.core.forum_permissions.has_forum_permission", side_effect=RuntimeError("permission backend down")):
                with self.assertLogs("apps.core.authorization", level="WARNING") as logs:
                    self.assertFalse(can("actor", "discussion.edit", "discussion"))
        self.assertTrue(any("Forum permission fallback failed" in message for message in logs.output))

        class DiscussionPolicy(AuthorizationPolicy):
            def discussion_edit(self, user, model, **context):
                return self.forceDeny()

            def can(self, user, ability, model, **context):
                if ability == "discussion.view":
                    return True
                return None

        policy = DiscussionPolicy()
        self.assertFalse(resolve_authorization_decision([
            policy(user="actor", ability="discussion.edit", model="discussion"),
            force_allow(),
        ]))
        self.assertTrue(resolve_authorization_decision([
            policy(user="actor", ability="discussion.view", model="discussion"),
        ]))

    def _build_policy_extension_registry(self) -> tuple[Path, ExtensionRegistry]:
        temp_dir = make_workspace_temp_dir()
        extensions_dir = temp_dir / "extensions"
        manifest_dir = extensions_dir / "alpha-policy"
        backend_dir = manifest_dir / "backend"
        manifest_dir.mkdir(parents=True, exist_ok=False)
        backend_dir.mkdir(parents=True, exist_ok=False)
        (manifest_dir / "extension.json").write_text(json.dumps({
            "id": "alpha-policy",
            "name": "Alpha Policy",
            "version": "1.0.0",
            "backend_entry": "extensions.alpha_policy.backend.ext",
        }, ensure_ascii=False), encoding="utf-8")
        (backend_dir / "ext.py").write_text(
            "from apps.core.extensions import PolicyExtender\n"
            "\n"
            "def grant_search_users(user=None, permission_name=None, **kwargs):\n"
            "    if permission_name == 'searchUsers' and user and user.username == 'policy-user':\n"
            "        return True\n"
            "    return None\n"
            "\n"
            "def deny_delete_own_discussion(user=None, discussion=None, **kwargs):\n"
            "    if user and discussion and discussion.user_id == user.id:\n"
            "        return False\n"
            "    return None\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        PolicyExtender(mounts=(\n"
            "            ('forum.permission.searchUsers', grant_search_users),\n"
            "            ('discussion.delete', deny_delete_own_discussion),\n"
            "        )),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.create(
            extension_id="alpha-policy",
            version="1.0.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
        )
        return temp_dir, ExtensionRegistry(extensions_path=extensions_dir)

    def test_extension_policy_can_grant_forum_permission(self):
        temp_dir, registry = self._build_policy_extension_registry()
        try:
            user = User.objects.create_user(
                username="policy-user",
                email="policy-user@example.com",
                password="password123",
                is_email_confirmed=True,
            )
            group = Group.objects.create(name="PolicySearchViewer", color="#27ae60")
            Permission.objects.create(group=group, permission="viewUserList")
            user.user_groups.add(group)

            self.assertFalse(has_forum_permission(user, "searchUsers"))

            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                self.assertTrue(has_forum_permission(user, "searchUsers"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_policy_can_deny_delete_own_discussion(self):
        temp_dir, registry = self._build_policy_extension_registry()
        try:
            author = User.objects.create_user(
                username="policy-discussion-author",
                email="policy-discussion-author@example.com",
                password="password123",
                is_email_confirmed=True,
            )
            discussion = Discussion.objects.create(
                title="Policy delete discussion",
                user=author,
                last_posted_user=author,
            )

            self.assertTrue(evaluate_runtime_extension_policy(
                "discussion.delete",
                default=True,
                user=author,
                discussion=discussion,
            ))

            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                self.assertFalse(evaluate_runtime_extension_policy(
                    "discussion.delete",
                    default=True,
                    user=author,
                    discussion=discussion,
                ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_policy_extender_accepts_policy_classes(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = temp_dir / "extensions"
            manifest_dir = extensions_dir / "alpha-policy-class"
            backend_dir = manifest_dir / "backend"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-policy-class",
                "name": "Alpha Policy",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_policy_class.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions import AuthorizationPolicy, PolicyExtender\n"
                "\n"
                "class AlphaModel:\n"
                "    pass\n"
                "\n"
                "class AlphaPolicy(AuthorizationPolicy):\n"
                "    instances = 0\n"
                "\n"
                "    def __init__(self):\n"
                "        type(self).instances += 1\n"
                "\n"
                "    def alpha_edit(self, user, model, **context):\n"
                "        return self.forceDeny()\n"
                "\n"
                "    def can(self, user, ability, model, **context):\n"
                "        if ability == 'alpha.view':\n"
                "            return self.allow()\n"
                "        return None\n"
                "\n"
                "class GlobalPolicy(AuthorizationPolicy):\n"
                "    def can(self, user, ability, model, **context):\n"
                "        if ability == 'alpha.global':\n"
                "            return self.forceAllow()\n"
                "        return None\n"
                "\n"
                "def extend():\n"
                "    return [\n"
                "        (PolicyExtender()\n"
                "            .policy(AlphaModel, AlphaPolicy)\n"
                "            .global_policy(GlobalPolicy)),\n"
                "    ]\n",
                encoding="utf-8",
            )
            ExtensionInstallation.objects.create(
                extension_id="alpha-policy-class",
                version="1.0.0",
                source="filesystem",
                enabled=True,
                installed=True,
                booted=True,
            )

            application = build_extension_application(manager=ExtensionRegistry(extensions_path=extensions_dir), force=True)
            runtime_view = application.get_runtime_view("alpha-policy-class")
            model_mount = next(item for item in runtime_view.policy_mounts if item.model is not None)
            model_class = model_mount.model

            from apps.core.extensions.policy_runtime_service import evaluate_model_policy
            with patch("apps.core.extensions.policy_runtime_service.get_extension_application", return_value=application):
                self.assertFalse(evaluate_model_policy("alpha.edit", user="actor", model=model_class(), default=True))
                self.assertTrue(evaluate_model_policy("alpha.view", user="actor", model=model_class(), default=False))
                self.assertTrue(evaluate_model_policy("alpha.global", user="actor", model=None, default=False))
                self.assertFalse(evaluate_model_policy("alpha.missing", user="actor", model=model_class(), default=False))

            policy_instance = model_mount.handler._bias_policy_cache["value"]
            self.assertEqual(policy_instance.__class__.instances, 1)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
