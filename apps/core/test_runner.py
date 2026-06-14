from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test.runner import DiscoverRunner


class BiasDiscoverRunner(DiscoverRunner):
    """Ensure `manage.py test` loads app test modules even without explicit labels."""

    def build_suite(self, test_labels=None, *args, **kwargs):
        test_labels = self._normalize_test_labels(test_labels)
        return super().build_suite(test_labels, *args, **kwargs)

    def _normalize_test_labels(self, test_labels=None) -> list[str]:
        if not test_labels:
            return self._default_test_labels()

        normalized = []
        for label in test_labels:
            if label in {"apps.core", "core"}:
                normalized.extend(_app_test_module_labels("apps.core"))
                continue
            normalized.append(label)
        return normalized

    def _default_test_labels(self) -> list[str]:
        app_names = {app for app in settings.INSTALLED_APPS if app.startswith("apps.")}
        app_names.update(
            app_config.name
            for app_config in apps.get_app_configs()
            if app_config.name.startswith("apps.")
        )
        labels = []
        for app_name in sorted(app_names):
            labels.extend(_app_test_module_labels(app_name))
        return labels


def _app_test_module_labels(app_name: str) -> list[str]:
    app_path = Path(settings.BASE_DIR) / app_name.replace(".", "/")
    labels = []
    tests_py = app_path / "tests.py"
    if tests_py.exists():
        labels.append(f"{app_name}.tests")
    labels.extend(
        f"{app_name}.{path.stem}"
        for path in sorted(app_path.glob("test_*.py"), key=lambda item: item.name)
        if path.name != "test_runner.py"
    )
    return labels
