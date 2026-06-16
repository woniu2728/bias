from apps.core.tests.common import *

class ExtensionDiagnosticsTests(TestCase):
    def test_classify_extension_diagnostics_marks_pending_migration_plan_as_warning(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "migration_plan": {
                "pending_files": ["0001_bootstrap.py"],
            },
            "delivery_checks": [],
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertTrue(diagnostics["warning"])
        self.assertIn("迁移状态待完善", diagnostics["warning_reasons"])

    def test_classify_extension_diagnostics_ignores_absent_migration_plan(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "migration_state": "pending",
            "migration_plan": {
                "declared_files": [],
                "applied_files": [],
                "pending_files": [],
            },
            "delivery_checks": [],
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertFalse(diagnostics["warning"])
        self.assertNotIn("迁移状态待完善", diagnostics["warning_reasons"])

    def test_classify_extension_diagnostics_marks_model_ownership_audit_as_warning(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "model_ownership_audit": {
                "package_migration_required_count": 2,
                "app_label_migration_required_count": 1,
            },
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertTrue(diagnostics["warning"])
        self.assertIn("扩展模型仍依赖 Django app 模块壳", diagnostics["warning_reasons"])
        self.assertIn("扩展模型 app label 尚未完全归属扩展", diagnostics["warning_reasons"])

    def test_classify_extension_diagnostics_marks_frontend_asset_state_as_warning(self):
        diagnostics = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "frontend_asset_state": {
                "has_frontend": True,
                "manifest_exists": True,
                "compiled": True,
                "requires_rebuild": True,
            },
        })

        self.assertFalse(diagnostics["blocking"])
        self.assertTrue(diagnostics["warning"])
        self.assertIn("扩展前端资源待重建", diagnostics["warning_reasons"])

        missing = classify_extension_diagnostics({
            "healthy": True,
            "runtime_issues": [],
            "dependency_state": "healthy",
            "frontend_asset_state": {
                "has_frontend": True,
                "manifest_exists": False,
                "compiled": False,
                "requires_rebuild": False,
            },
        })

        self.assertIn("扩展前端资源尚未生成", missing["warning_reasons"])

    def test_summarize_extension_delivery_counts_frontend_migration_and_signed_assets(self):
        summary = summarize_extension_delivery([
            {
                "delivery_assets": {
                    "asset_count": 4,
                    "assets": [
                        {"key": "frontend_admin_entry", "exists": True},
                        {"key": "migrations", "exists": True},
                        {"key": "locale", "exists": False},
                    ],
                },
            },
            {
                "delivery_assets": {
                    "asset_count": 3,
                    "assets": [
                        {"key": "frontend_forum_entry", "exists": True},
                        {"key": "locale", "exists": True},
                        {"key": "signature", "exists": True},
                    ],
                },
            },
        ])

        self.assertEqual(summary["asset_count"], 7)
        self.assertEqual(summary["frontend_bundle_count"], 2)
        self.assertEqual(summary["migration_bundle_count"], 1)
        self.assertEqual(summary["locale_bundle_count"], 1)
        self.assertEqual(summary["signed_extension_count"], 1)
