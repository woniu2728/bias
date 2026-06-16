from apps.core.tests.common import *

class ExtensionMiddlewareIntegrationTests(TestCase):
    def _build_middleware_extension_registry(self) -> tuple[Path, ExtensionRegistry]:
        temp_dir = make_workspace_temp_dir()
        extensions_dir = temp_dir / "extensions"
        manifest_dir = extensions_dir / "alpha-middleware"
        backend_dir = manifest_dir / "backend"
        manifest_dir.mkdir(parents=True, exist_ok=False)
        backend_dir.mkdir(parents=True, exist_ok=False)
        (manifest_dir / "extension.json").write_text(json.dumps({
            "id": "alpha-middleware",
            "name": "Alpha Middleware",
            "version": "1.0.0",
            "backend_entry": "extensions.alpha_middleware.backend.ext",
        }, ensure_ascii=False), encoding="utf-8")
        (backend_dir / "ext.py").write_text(
            "from django.http import JsonResponse\n"
            "from apps.core.extensions import MiddlewareExtender\n"
            "\n"
            "def annotate_request(request, next_handler):\n"
            "    request.alpha_trace = ['global']\n"
            "    response = next_handler(request)\n"
            "    response['X-Alpha-Global'] = '1'\n"
            "    return response\n"
            "\n"
            "def annotate_api_request(request, next_handler):\n"
            "    request.alpha_trace.append('api')\n"
            "    response = next_handler(request)\n"
            "    response['X-Alpha-Api'] = ','.join(request.alpha_trace)\n"
            "    return response\n"
            "\n"
            "def block_admin(request):\n"
            "    return JsonResponse({'blocked': True, 'target': 'admin'}, status=418)\n"
            "\n"
            "def extend():\n"
            "    return [\n"
            "        MiddlewareExtender(mounts=(\n"
            "            ('global', annotate_request, 10),\n"
            "            ('api', annotate_api_request, 20),\n"
            "            ('admin', block_admin, 5),\n"
            "        )),\n"
            "    ]\n",
            encoding="utf-8",
        )
        ExtensionInstallation.objects.create(
            extension_id="alpha-middleware",
            version="1.0.0",
            source="filesystem",
            enabled=True,
            installed=True,
            booted=True,
        )
        return temp_dir, ExtensionRegistry(extensions_path=extensions_dir)

    def test_extension_request_middleware_runs_global_and_api_targets(self):
        temp_dir, registry = self._build_middleware_extension_registry()
        try:
            request = RequestFactory().get("/api/demo")

            def get_response(inner_request):
                trace = list(getattr(inner_request, "alpha_trace", []))
                return JsonResponse({"trace": trace})

            middleware = ExtensionRequestMiddleware(get_response)

            with patch("apps.core.middleware.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                response = middleware(request)

            self.assertEqual(response.status_code, 200)
            self.assertEqual(json.loads(response.content), {"trace": ["global", "api"]})
            self.assertEqual(response["X-Alpha-Global"], "1")
            self.assertEqual(response["X-Alpha-Api"], "global,api")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_request_middleware_can_short_circuit_admin_target(self):
        temp_dir, registry = self._build_middleware_extension_registry()
        try:
            request = RequestFactory().get("/api/admin/extensions")

            def get_response(_request):
                return HttpResponse("should not execute", status=200)

            middleware = ExtensionRequestMiddleware(get_response)

            with patch("apps.core.middleware.get_extension_application", return_value=build_extension_application(manager=registry, force=True)):
                response = middleware(request)

            self.assertEqual(response.status_code, 418)
            self.assertEqual(json.loads(response.content), {"blocked": True, "target": "admin"})
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_extension_error_handling_middleware_reports_and_reraises(self):
        from apps.core.middleware import ExtensionErrorHandlingMiddleware

        request = RequestFactory().get("/api/fail")
        reported = []

        def get_response(_request):
            raise ValueError("broken")

        middleware = ExtensionErrorHandlingMiddleware(get_response)

        with patch(
            "apps.core.extensions.system_runtime.report_runtime_error",
            side_effect=lambda exc, **kwargs: reported.append((exc, kwargs)),
        ):
            with self.assertRaises(ValueError):
                middleware(request)

        self.assertEqual(reported[0][0].args, ("broken",))
        self.assertEqual(reported[0][1]["request"], request)
        self.assertEqual(reported[0][1]["operation"], "request")

    def test_extension_error_handling_middleware_uses_typed_handler_response(self):
        from apps.core.extensions import ErrorHandlingExtender
        from apps.core.middleware import ExtensionErrorHandlingMiddleware

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")

        def handle_value_error(payload, context):
            return JsonResponse({"handled": payload["message"], "status": payload["http_status"]}, status=409)

        ErrorHandlingExtender() \
            .type(ValueError, "alpha_value_error") \
            .status("alpha_value_error", 409) \
            .handler(ValueError, handle_value_error) \
            .extend(app, extension)
        app.make("error.handling")

        request = RequestFactory().get("/api/fail")

        def get_response(_request):
            raise ValueError("broken")

        middleware = ExtensionErrorHandlingMiddleware(get_response)

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            response = middleware(request)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(json.loads(response.content), {"handled": "broken", "status": 409})

    def test_extension_csrf_middleware_marks_exempt_runtime_route(self):
        from apps.core.extensions import CsrfExtender
        from apps.core.middleware import ExtensionCsrfMiddleware

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        CsrfExtender().exempt_route("alpha-webhook").extend(app, extension)
        app.make("csrf")

        request = RequestFactory().post("/api/webhook")
        request.resolver_match = SimpleNamespace(url_name="alpha-webhook")
        middleware = ExtensionCsrfMiddleware(lambda current_request: HttpResponse("ok"))

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            result = middleware.process_view(request, None, (), {})

        self.assertIsNone(result)
        self.assertTrue(request._dont_enforce_csrf_checks)

    def test_extension_throttle_api_middleware_short_circuits_api_request(self):
        from apps.core.extensions import ThrottleApiExtender
        from apps.core.middleware import ExtensionThrottleApiMiddleware

        app = ExtensionApplication()
        extension = SimpleNamespace(extension_id="alpha-tools")
        ThrottleApiExtender().set("alpha", lambda request: request.path == "/api/demo").extend(app, extension)
        app.make("throttle.api")

        request = RequestFactory().get("/api/demo")
        middleware = ExtensionThrottleApiMiddleware(lambda current_request: HttpResponse("ok"))

        with patch("apps.core.extensions.bootstrap.get_extension_host", return_value=app):
            response = middleware.process_view(request, None, (), {})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.content), {"error": "请求过于频繁", "code": "rate_limit_exceeded"})


    def test_validate_extension_manifests_reports_missing_dependency_and_missing_admin_entry(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            manifest_path = manifest_dir / "extension.json"
            manifest_path.write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core", "missing-one"],
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_dependency" for item in result.issues))
            self.assertTrue(any(item.code == "missing_frontend_admin_entry" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_admin_content_validation_logs_extension_registry_failures(self):
        from apps.core.extension_validation_context import resolve_available_extension_ids_for_validation

        registry = Mock()
        registry.get_extensions.side_effect = RuntimeError("registry unavailable")

        with patch("apps.core.extension_validation_context.get_core_module_ids", return_value=("core",)):
            with patch("apps.core.extension_validation_context.get_extension_registry", return_value=registry):
                with self.assertLogs("apps.core.extension_validation_context", level="WARNING") as logs:
                    extension_ids = resolve_available_extension_ids_for_validation()

        self.assertEqual(extension_ids, {"core"})
        self.assertTrue(any("Failed to resolve installed extension ids" in message for message in logs.output))

    def test_validate_extension_manifests_rejects_optional_dependency_top_level_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.ext import beta_extenders\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    optional_dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "optional_dependency_top_level_import"
                and item.extension_id == "alpha-tools"
                and item.field.endswith("extensions/alpha-tools/backend/ext.py")
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_undeclared_cross_extension_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.ext import beta_extenders\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "undeclared_cross_extension_import"
                and item.level == "error"
                and item.extension_id == "alpha-tools"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_declared_dependency_internal_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.services import BetaService\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_cross_extension_internal_import"
                and item.level == "error"
                and item.extension_id == "alpha-tools"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_cross_extension_events_and_visibility_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from extensions.beta_tools.backend.events import BetaHappened\n"
                "from extensions.beta_tools.backend.visibility import scope_beta\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            issues = [
                item for item in result.issues
                if item.code == "forbidden_cross_extension_internal_import"
                and item.extension_id == "alpha-tools"
            ]
            self.assertFalse(result.ok)
            self.assertEqual(len(issues), 2)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_delayed_internal_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ConditionalExtender\n"
                "\n"
                "def beta_extenders():\n"
                "    from extensions.beta_tools.backend.models import BetaThing\n"
                "    return []\n"
                "\n"
                "def extend():\n"
                "    return [ConditionalExtender().when_extension_enabled('beta-tools', beta_extenders)]\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    optional_dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_cross_extension_internal_import"
                and item.level == "error"
                and item.extension_id == "alpha-tools"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_allows_conditional_optional_dependency_delayed_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            extensions_dir = Path(temp_dir) / "extensions"
            alpha_dir = extensions_dir / "alpha-tools"
            beta_dir = extensions_dir / "beta-tools"
            alpha_backend_dir = alpha_dir / "backend"
            alpha_backend_dir.mkdir(parents=True, exist_ok=False)
            beta_dir.mkdir(parents=True, exist_ok=False)
            (alpha_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "optional_dependencies": ["beta-tools"],
            }, ensure_ascii=False), encoding="utf-8")
            (alpha_backend_dir / "ext.py").write_text(
                "from apps.core.extensions import ConditionalExtender\n"
                "\n"
                "def beta_extenders():\n"
                "    from extensions.beta_tools.backend.ext import beta_extenders\n"
                "    return []\n"
                "\n"
                "def extend():\n"
                "    return [ConditionalExtender().when_extension_enabled('beta-tools', beta_extenders)]\n",
                encoding="utf-8",
            )
            (beta_dir / "extension.json").write_text(json.dumps({
                "id": "beta-tools",
                "name": "Beta Tools",
                "version": "1.0.0",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = [
                ExtensionManifest(
                    id="alpha-tools",
                    name="Alpha Tools",
                    version="1.0.0",
                    backend_entry="extensions.alpha_tools.backend.ext",
                    optional_dependencies=("beta-tools",),
                    path=str(alpha_dir),
                ),
                ExtensionManifest(
                    id="beta-tools",
                    name="Beta Tools",
                    version="1.0.0",
                    path=str(beta_dir),
                ),
            ]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=extensions_dir,
            )

            self.assertTrue(result.ok)
            self.assertFalse(any(item.code == "optional_dependency_top_level_import" for item in result.issues))
            self.assertFalse(any(item.code == "undeclared_cross_extension_import" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_frontend_admin_exports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveSettingsPage() { return null }\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "missing_frontend_admin_export"
                and "resolveOperationsPage" in item.message
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_mismatched_frontend_entry_paths(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/other-tools/frontend/admin/index.js",
                "frontend_forum_entry": "extensions/other-tools/frontend/forum/index.js",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_frontend_admin_entry_path" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_frontend_forum_entry_path" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_core_owned_frontend_contributions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            forum_dir = manifest_dir / "frontend" / "forum"
            forum_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
            }, ensure_ascii=False), encoding="utf-8")
            (forum_dir / "index.js").write_text(
                "import { registerForumNavItem } from '@/forum/registry'\n"
                "export const extend = [{\n"
                "  extend() {\n"
                "    registerForumNavItem({ key: 'alpha', moduleId: 'core' })\n"
                "  },\n"
                "}]\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_core_module_frontend_contribution"
                and item.field == "extensions/alpha-tools/frontend/forum/index.js"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_allows_generated_settings_surface(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/alpha-tools/settings"],
                "settings_schema": [
                    {
                        "key": "welcome_message",
                        "label": "欢迎语",
                        "type": "text",
                        "default": "hello",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveDetailPage() { return null }\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertTrue(result.ok)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_allows_generated_permissions_and_operations_surfaces(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            admin_dir = manifest_dir / "frontend" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "permissions_pages": ["/admin/extensions/alpha-tools/permissions"],
                "operations_pages": ["/admin/extensions/alpha-tools/operations"],
                "admin_actions": [
                    {
                        "key": "details",
                        "label": "查看详情",
                        "kind": "route",
                        "target": "/admin/extensions/alpha-tools",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (admin_dir / "index.js").write_text(
                "export function resolveDetailPage() { return null }\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertTrue(result.ok)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_frontend_forum_entry(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_frontend_forum_entry" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_missing_frontend_forum_export(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            forum_dir = manifest_dir / "frontend" / "forum"
            forum_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_forum_entry": "extensions/alpha-tools/frontend/forum/index.js",
            }, ensure_ascii=False), encoding="utf-8")
            (forum_dir / "index.js").write_text(
                "export const setup = null\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "missing_frontend_forum_export" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_mismatched_extension_admin_page(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "frontend_admin_entry": "extensions/alpha-tools/frontend/admin/index.js",
                "settings_pages": ["/admin/extensions/other-tools/settings"],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_extension_admin_page" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_admin_actions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "dependencies": ["core"],
                "admin_actions": [
                    {
                        "key": "broken",
                        "label": "坏动作",
                        "kind": "command",
                        "target": "/admin/extensions/alpha-tools",
                        "tone": "loud",
                    },
                    {
                        "key": "broken-route",
                        "label": "坏路由",
                        "kind": "route",
                        "target": "admin/extensions/alpha-tools",
                        "tone": "default",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_admin_action_kind" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_admin_action_tone" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_admin_action_target" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_runtime_actions(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "runtime_actions": [
                    {
                        "key": "rebuild-cache",
                        "label": "刷新缓存",
                        "hook": "",
                    },
                    {
                        "key": "rebuild-cache",
                        "label": "",
                        "hook": "run_rebuild_cache",
                        "tone": "loud",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertEqual(result.error_count, 5)
            self.assertTrue(any(item.code == "invalid_runtime_action" for item in result.issues))
            self.assertTrue(any(item.code == "duplicate_runtime_action_key" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_runtime_action_tone" for item in result.issues))
            self.assertTrue(any(item.code == "missing_backend_entry_declaration" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_strict_reports_missing_runtime_backend_hook(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "runtime_actions": [
                    {
                        "key": "rebuild-cache",
                        "label": "刷新缓存",
                        "hook": "run_rebuild_cache",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                strict_runtime_hooks=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "missing_backend_hook" and "run_rebuild_cache" in item.message
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_migration_namespace_field(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
                "migration_namespace": "extensions.alpha_tools.backend.migrations",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(
                item.code == "forbidden_migration_namespace_manifest_field"
                for item in result.issues
            ))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_backend_and_forbidden_migration_namespace(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            migrations_dir = backend_dir / "migrations"
            migrations_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.other_tools.backend.ext",
                "migration_namespace": "extensions.other_tools.backend.migrations",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "def run_install(context):\n"
                "    return {'status': 'ok'}\n",
                encoding="utf-8",
            )
            (migrations_dir / "0001_initial.py").write_text(
                "def apply():\n"
                "    return 'ok'\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_backend_entry_namespace" for item in result.issues))
            self.assertTrue(any(item.code == "forbidden_migration_namespace_manifest_field" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_django_app_config_namespace(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "apps.core.apps.CoreConfig",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_django_app_config_namespace" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_django_migration_module_field(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                "django_migration_module": "extensions.posts.backend.wrong_migrations",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "forbidden_django_migration_module_manifest_field" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_django_app_label_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_label": "alpha",
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "django_app_label_without_app_config" for item in result.issues))

            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "django_app_config": "extensions.alpha_tools.backend.apps.AlphaToolsConfig",
                "django_app_label": "123-invalid",
            }, ensure_ascii=False), encoding="utf-8")

            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_django_app_label" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_django_app_entry_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core import signals\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "forbidden_django_app_entry_import" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_apps_core_root_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core import signals\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "forbidden_core_internal_import" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_rejects_apps_core_internal_module_imports(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            backend_dir = manifest_dir / "backend"
            backend_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (backend_dir / "ext.py").write_text(
                "from apps.core.extensions.backend import _build_runtime_action_definition\n"
                "\n"
                "def extend():\n"
                "    return []\n",
                encoding="utf-8",
            )

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = loader.discover_manifests()
            result = validate_extension_manifests_with_available_ids(
                manifests,
                available_extension_ids={"core"},
                extensions_base_path=Path(temp_dir) / "extensions",
                public_sdk_only=True,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "forbidden_core_internal_import" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_legacy_migration_dir_without_files(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            migrations_dir = manifest_dir / "backend" / "migrations"
            migrations_dir.mkdir(parents=True, exist_ok=False)
            (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (manifest_dir / "backend" / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "legacy_extension_migration_dir" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_legacy_migration_dir_with_invalid_file_contract(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            migrations_dir = manifest_dir / "backend" / "migrations"
            migrations_dir.mkdir(parents=True, exist_ok=False)
            (migrations_dir / "__init__.py").write_text("", encoding="utf-8")
            (migrations_dir / "initial.py").write_text(
                "VALUE = 'missing-entrypoint'\n",
                encoding="utf-8",
            )
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "backend_entry": "extensions.alpha_tools.backend.ext",
            }, ensure_ascii=False), encoding="utf-8")
            (manifest_dir / "backend" / "ext.py").write_text("def extend():\n    return []\n", encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "legacy_extension_migration_dir" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_settings_schema(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "settings_schema": [
                    {
                        "key": "mode",
                        "label": "",
                        "type": "select",
                        "options": [],
                    },
                    {
                        "key": "mode",
                        "label": "模式",
                        "type": "json",
                    }
                ],
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "duplicate_extension_setting_key" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_extension_setting_type" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_extension_setting_options" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_reports_invalid_ecosystem_metadata(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            (manifest_dir / "extension.json").write_text(json.dumps({
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "compatibility": {
                    "bias_version": "latest",
                    "api_version": "v1",
                    "api_stability": "ga",
                },
                "distribution": {
                    "channel": "store",
                    "signature_url": "https://example.com/signature.txt",
                    "replacement": "not a package!",
                },
                "security": {
                    "support_email": "security-at-example.com",
                },
            }, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(result.ok)
            self.assertTrue(any(item.code == "invalid_bias_version_range" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_api_version" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_api_stability" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_distribution_channel" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_distribution_replacement" for item in result.issues))
            self.assertTrue(any(item.code == "invalid_security_support_email" for item in result.issues))
            self.assertTrue(any(item.code == "signature_url_without_key" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_validate_extension_manifests_checks_local_distribution_signature(self):
        temp_dir = make_workspace_temp_dir()
        try:
            manifest_dir = Path(temp_dir) / "extensions" / "alpha-tools"
            manifest_dir.mkdir(parents=True, exist_ok=False)
            manifest = {
                "id": "alpha-tools",
                "name": "Alpha Tools",
                "version": "1.0.0",
                "distribution": {
                    "channel": "private",
                    "signing_key_id": "local-dev",
                    "signature_url": "signature.txt",
                },
                "security": {
                    "capabilities_notice": "测试签名文件校验。",
                },
            }
            (manifest_dir / "extension.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

            loader = ExtensionManifestLoader(Path(temp_dir) / "extensions")
            manifests = [item.manifest for item in loader.discover()]
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertTrue(any(item.code == "missing_distribution_signature_file" for item in result.issues))

            (manifest_dir / "signature.txt").write_text("signature", encoding="utf-8")
            result = validate_extension_manifests(manifests, extensions_base_path=Path(temp_dir) / "extensions")

            self.assertFalse(any(item.code == "missing_distribution_signature_file" for item in result.issues))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
