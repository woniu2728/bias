from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.test.runner import DiscoverRunner


class BiasDiscoverRunner(DiscoverRunner):
    """Ensure `manage.py test` loads app test modules even without explicit labels."""

    def build_suite(self, test_labels=None, *args, **kwargs):
        if not test_labels:
            app_names = {app for app in settings.INSTALLED_APPS if app.startswith("apps.")}
            app_names.update(
                app_config.name
                for app_config in apps.get_app_configs()
                if app_config.name.startswith("apps.")
            )
            test_labels = [f"{app}.tests" for app in sorted(app_names)]
            extensions_dir = Path(settings.BASE_DIR) / "extensions"
            if extensions_dir.exists():
                test_labels.extend(
                    f"extensions.{extension_dir.name}.backend.tests"
                    for extension_dir in sorted(extensions_dir.iterdir(), key=lambda item: item.name)
                    if extension_dir.is_dir()
                    and extension_dir.name.isidentifier()
                    and (extension_dir / "backend" / "tests.py").exists()
                )
        return super().build_suite(test_labels, *args, **kwargs)
