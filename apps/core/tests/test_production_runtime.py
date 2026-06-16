from apps.core.tests.common import *

class ProductionRuntimeCheckTests(TestCase):
    @override_settings(
        DEBUG=False,
        DATABASES={"default": {"ENGINE": "django.db.backends.postgresql", "NAME": "bias", "HOST": "db"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "prod-runtime-check-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        CELERY_BROKER_URL="memory://",
        SECRET_KEY="django-insecure-change-this-in-production",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "short-jwt-secret"},
        FRONTEND_URL="",
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
    )
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    def test_production_runtime_checks_report_critical_risks(self, _is_test_process):
        messages = run_checks(tags=["bias_runtime"])
        message_ids = {message.id for message in messages}

        self.assertIn("bias.django-secret-placeholder", message_ids)
        self.assertIn("bias.jwt-secret-too-short", message_ids)
        self.assertIn("bias.redis-disabled-production", message_ids)
        self.assertIn("bias.frontend-url-missing-production", message_ids)
        self.assertIn("bias.email-backend-development-production", message_ids)

    @override_settings(
        DEBUG=False,
        WEB_CONCURRENCY=2,
        DATABASES={"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}},
        CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "runtime-check-test"}},
        CHANNEL_LAYERS={"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}},
        SECRET_KEY="runtime-secret-key-12345678901234567890",
        NINJA_JWT={"ALGORITHM": "HS256", "SIGNING_KEY": "runtime-jwt-secret-key-123456789012345"},
    )
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    def test_production_runtime_checks_warn_about_multiprocess_inmemory_backends(self, _is_test_process):
        messages = run_checks(tags=["bias_runtime"])
        message_ids = {message.id for message in messages}

        self.assertIn("bias.locmem-cache-multiprocess", message_ids)
        self.assertIn("bias.realtime-inmemory-multiprocess", message_ids)

    @override_settings(DEBUG=False)
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    @patch("apps.core.startup_guard.run_checks")
    def test_startup_guard_blocks_production_startup_when_critical_checks_exist(
        self,
        run_checks_mock,
        _is_test_process,
    ):
        from django.core.checks import Critical, Warning
        from apps.core.startup_guard import enforce_production_runtime_checks

        run_checks_mock.return_value = [
            Warning("warning", id="bias.warning-example"),
            Critical("critical failure", hint="fix it", id="bias.critical-example"),
        ]

        with self.assertRaises(ImproperlyConfigured) as captured:
            enforce_production_runtime_checks()

        message = str(captured.exception)
        self.assertIn("bias.critical-example", message)
        self.assertIn("critical failure", message)
        self.assertIn("fix it", message)

    @override_settings(DEBUG=True)
    @patch("apps.core.startup_guard.run_checks")
    def test_startup_guard_skips_non_production_runtime(self, run_checks_mock):
        from apps.core.startup_guard import enforce_production_runtime_checks

        enforce_production_runtime_checks()

        run_checks_mock.assert_not_called()

    @override_settings(DEBUG=False)
    @patch.object(settings.BOOTSTRAP, "installed", True)
    @patch("apps.core.runtime_checks._is_test_process", return_value=False)
    @patch("apps.core.startup_guard.run_checks")
    def test_startup_guard_allows_installation_with_development_email_backend(
        self,
        run_checks_mock,
        _is_test_process,
    ):
        from django.core.checks import Critical
        from apps.core.startup_guard import enforce_production_runtime_checks

        run_checks_mock.return_value = [
            Critical(
                "development email backend",
                id="bias.email-backend-development-production",
            ),
        ]

        with patch.dict(os.environ, {"BIAS_INSTALLING": "1"}):
            enforce_production_runtime_checks()

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_enforces_production_runtime_checks(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        manage.main()

        enforce_runtime_checks_mock.assert_called_once_with()
        execute_from_command_line_mock.assert_called_once_with(sys.argv)

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_skips_startup_guard_for_validate_extensions(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        argv = ["manage.py", "validate_extensions"]
        with patch.object(sys, "argv", argv):
            manage.main()

        enforce_runtime_checks_mock.assert_not_called()
        execute_from_command_line_mock.assert_called_once_with(argv)

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_skips_startup_guard_for_create_extension(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        argv = ["manage.py", "create_extension", "demo-tools"]
        with patch.object(sys, "argv", argv):
            manage.main()

        enforce_runtime_checks_mock.assert_not_called()
        execute_from_command_line_mock.assert_called_once_with(argv)

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    @patch("django.core.management.execute_from_command_line")
    def test_manage_py_main_skips_startup_guard_for_inspect_extensions(
        self,
        execute_from_command_line_mock,
        enforce_runtime_checks_mock,
    ):
        import manage

        argv = ["manage.py", "inspect_extensions"]
        with patch.object(sys, "argv", argv):
            manage.main()

        enforce_runtime_checks_mock.assert_not_called()
        execute_from_command_line_mock.assert_called_once_with(argv)

    @patch("apps.core.startup_guard.enforce_production_runtime_checks")
    def test_celery_module_enforces_production_runtime_checks(self, enforce_runtime_checks_mock):
        import config.celery as celery_module

        importlib.reload(celery_module)
        celery_module._enforce_celery_runtime_checks()

        enforce_runtime_checks_mock.assert_called_once_with()
