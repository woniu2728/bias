import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def _enforce_celery_runtime_checks():
    from bias_core.startup_guard import enforce_celery_runtime_checks

    enforce_celery_runtime_checks()


_enforce_celery_runtime_checks()

app = Celery("bias")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
