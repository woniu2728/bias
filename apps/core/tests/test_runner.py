from apps.core.tests.common import *

class TestRunnerTests(TestCase):
    def test_default_runner_uses_app_test_modules_without_explicit_labels(self):
        runner = BiasDiscoverRunner()
        app_names = {app for app in settings.INSTALLED_APPS if app.startswith("apps.")}
        app_names.update(
            app_config.name
            for app_config in apps.get_app_configs()
            if app_config.name.startswith("apps.")
        )
        labels = []
        for app in sorted(app_names):
            app_path = Path(settings.BASE_DIR) / app.replace(".", "/")
            tests_path = app_path / "tests.py"
            if tests_path.exists():
                labels.append(f"{app}.tests")
            # 同样检查 tests/ 包
            tests_dir = app_path / "tests"
            if tests_dir.is_dir():
                labels.extend(
                    f"{app}.tests.{path.stem}"
                    for path in sorted(tests_dir.glob("test_*.py"), key=lambda item: item.name)
                    if path.name != "test_runner.py"
                )
            labels.extend(
                f"{app}.{path.stem}"
                for path in sorted(app_path.glob("test_*.py"), key=lambda item: item.name)
                if path.name != "test_runner.py"
            )

        suite = runner.build_suite([])

        discovered = set()
        stack = [suite]
        while stack:
            item = stack.pop()
            if hasattr(item, "__iter__") and not hasattr(item, "_testMethodName"):
                stack.extend(list(item))
                continue
            module = item.__class__.__module__
            discovered.add(module)

        for label in labels:
            self.assertIn(label, discovered)

    def test_core_app_label_expands_to_core_test_modules(self):
        runner = BiasDiscoverRunner()

        suite = runner.build_suite(["apps.core"])

        modules = set()
        stack = [suite]
        while stack:
            item = stack.pop()
            if hasattr(item, "__iter__") and not hasattr(item, "_testMethodName"):
                stack.extend(list(item))
                continue
            modules.add(item.__class__.__module__)

        self.assertTrue(
            any(m.startswith("apps.core.tests.") for m in modules),
            f"Expected test modules under apps.core.tests.*, got: {modules}",
        )
        self.assertIn("apps.core.test_management_commands", modules)

    def test_core_product_code_does_not_import_extension_backends(self):
        violations: list[str] = []
        core_root = Path(settings.BASE_DIR) / "apps" / "core"
        for path in sorted(core_root.rglob("*.py")):
            if path.name == "tests.py" or "tests" in path.parts or "__pycache__" in path.parts:
                continue
            relative_path = path.relative_to(settings.BASE_DIR).as_posix()
            source = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(source.splitlines(), start=1):
                stripped = line.lstrip()
                if stripped.startswith(("from extensions.", "import extensions.")):
                    violations.append(f"{relative_path}:{line_number}: {line.strip()}")

        self.assertEqual(violations, [], "core product code must depend on extension runtime contracts, not extension backends")
