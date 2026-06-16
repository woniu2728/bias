from apps.core.tests.common import *

class SecretValidationTests(TestCase):
    def test_runtime_diagnostics_keeps_admin_helper_compatibility_imports(self):
        from apps.core import admin_runtime_helpers, runtime_diagnostics

        self.assertIs(
            admin_runtime_helpers.build_runtime_risks,
            runtime_diagnostics.build_runtime_risks,
        )
        self.assertIs(
            admin_runtime_helpers.probe_cache_connection,
            runtime_diagnostics.probe_cache_connection,
        )

    @override_settings(WEB_CONCURRENCY=1)
    def test_runtime_diagnostics_accepts_explicit_web_concurrency(self):
        from apps.core import runtime_diagnostics

        risks = runtime_diagnostics.build_runtime_risks(
            debug_mode=False,
            database_label="SQLite (db.sqlite3)",
            cache_driver="内存",
            realtime_driver="In-memory",
            queue_enabled=False,
            queue_driver="sync",
            queue_worker_status={"available": False, "message": ""},
            redis_enabled=False,
            cache_connection={"enabled": False, "available": None},
            realtime_connection={"enabled": False, "available": None},
            queue_broker_connection={"enabled": False, "available": None},
            auth_secret_risks=[],
            web_concurrency=2,
        )

        risk_codes = {item["code"] for item in risks}
        self.assertIn("locmem-cache-multiprocess", risk_codes)
        self.assertIn("realtime-inmemory-multiprocess", risk_codes)

    def test_frontend_route_serialization_supports_runtime_and_manifest_contracts(self):
        from apps.core.extensions.frontend_serialization import serialize_frontend_routes

        route = SimpleNamespace(
            path="",
            name="alpha",
            component="AlphaPage",
            frontend="forum",
            module_id="alpha-tools",
            title="Alpha",
            description="Alpha route",
            preloads=("loadAlpha",),
            document_attributes=({"data-alpha": "1"},),
            head_tags=({"name": "alpha"},),
            requires_auth=True,
            order=20,
            removed=False,
        )

        runtime_routes = serialize_frontend_routes((route,))
        manifest_routes = serialize_frontend_routes(
            (route,),
            require_path=False,
            include_document_payload=False,
        )

        self.assertEqual(runtime_routes, [])
        self.assertEqual(manifest_routes[0]["name"], "alpha")
        self.assertNotIn("preloads", manifest_routes[0])

    def test_placeholder_runtime_secrets_are_detected_consistently(self):
        from apps.core.secret_validation import build_auth_secret_risks, looks_like_placeholder_secret

        self.assertTrue(looks_like_placeholder_secret(""))
        self.assertTrue(looks_like_placeholder_secret("replace-with-django-secret-key"))
        self.assertTrue(looks_like_placeholder_secret("bias-dev-secret-key-change-this-32bytes-min"))

        risks = build_auth_secret_risks(
            secret_key="replace-with-django-secret-key",
            jwt_algorithm="HS256",
            jwt_signing_key="short-jwt-secret",
        )
        risk_codes = {item["code"] for item in risks}

        self.assertIn("django-secret-placeholder", risk_codes)
        self.assertIn("jwt-secret-too-short", risk_codes)

    def test_non_hmac_jwt_algorithm_does_not_apply_hs_length_rule(self):
        from apps.core.secret_validation import build_auth_secret_risks, jwt_key_length_requirement

        self.assertEqual(jwt_key_length_requirement("RS256"), 0)

        risks = build_auth_secret_risks(
            secret_key="production-django-secret-key-1234567890",
            jwt_algorithm="RS256",
            jwt_signing_key="short",
        )

        self.assertEqual(risks, [])
