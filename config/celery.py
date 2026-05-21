import os

from celery import Celery, signals


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


def _enforce_celery_runtime_checks(*args, **kwargs):
    from apps.core.startup_guard import enforce_production_runtime_checks

    enforce_production_runtime_checks()


signals.worker_init.connect(_enforce_celery_runtime_checks)
signals.beat_init.connect(_enforce_celery_runtime_checks)
