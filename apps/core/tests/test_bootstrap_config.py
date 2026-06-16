from apps.core.tests.common import *

class BootstrapConfigFallbackTests(TestCase):
    def test_cors_origins_include_local_development_hosts_only_in_debug(self):
        production_config = SiteBootstrapConfig(
            debug=False,
            frontend_url="https://forum.example.com",
            site_domains=["forum.example.com"],
            site_scheme="https",
        )
        debug_config = SiteBootstrapConfig(
            debug=True,
            frontend_url="http://localhost:8080",
            site_domains=["localhost:8080"],
            site_scheme="http",
        )

        production_origins = production_config.resolved_cors_origins()
        debug_origins = debug_config.resolved_cors_origins()

        self.assertEqual(production_origins, ["https://forum.example.com"])
        self.assertIn("http://localhost:3000", debug_origins)
        self.assertIn("http://localhost:5173", debug_origins)

    def test_env_bootstrap_with_database_only_is_not_installed(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with patch("apps.core.bootstrap_config._is_test_process", return_value=False):
                with patch.dict(
                    os.environ,
                    {
                        "BIAS_SITE_CONFIG": "",
                        "DB_NAME": "bias",
                        "DB_USER": "postgres",
                        "DB_PASSWORD": "postgres",
                        "DB_HOST": "db",
                        "DB_PORT": "5432",
                        "REDIS_HOST": "redis",
                        "REDIS_PORT": "6379",
                        "REDIS_DB": "0",
                        "SECRET_KEY": "",
                        "JWT_SECRET_KEY": "",
                        "FRONTEND_URL": "",
                    },
                    clear=False,
                ):
                    config = load_site_bootstrap(temp_dir)

            self.assertFalse(config.installed)
            self.assertEqual(config.source, "env")
            self.assertEqual(config.database_mode, "postgres")
            self.assertEqual(config.db_name, "bias")
            self.assertEqual(config.db_user, "postgres")
            self.assertEqual(config.db_host, "db")
            self.assertTrue(config.use_redis)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_env_bootstrap_is_installed_with_runtime_secrets_and_origin(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with patch("apps.core.bootstrap_config._is_test_process", return_value=False):
                with patch.dict(
                    os.environ,
                    {
                        "BIAS_SITE_CONFIG": "",
                        "DB_NAME": "bias",
                        "DB_USER": "postgres",
                        "DB_PASSWORD": "postgres",
                        "SECRET_KEY": "a" * 50,
                        "JWT_SECRET_KEY": "b" * 50,
                        "FRONTEND_URL": "http://localhost:8080",
                    },
                    clear=False,
                ):
                    config = load_site_bootstrap(temp_dir)

            self.assertTrue(config.installed)
            self.assertEqual(config.source, "env")
            self.assertEqual(config.frontend_url, "http://localhost:8080")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_env_bootstrap_rejects_placeholder_runtime_secrets(self):
        temp_dir = make_workspace_temp_dir()
        try:
            with patch("apps.core.bootstrap_config._is_test_process", return_value=False):
                with patch.dict(
                    os.environ,
                    {
                        "BIAS_SITE_CONFIG": "",
                        "DB_NAME": "bias",
                        "DB_USER": "postgres",
                        "DB_PASSWORD": "postgres",
                        "SECRET_KEY": "replace-with-django-secret-key",
                        "JWT_SECRET_KEY": "replace-with-jwt-secret-key",
                        "FRONTEND_URL": "http://localhost:8080",
                    },
                    clear=False,
                ):
                    config = load_site_bootstrap(temp_dir)

            self.assertFalse(config.installed)
            self.assertEqual(config.source, "env")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
