"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application
from apps.core.startup_guard import enforce_production_runtime_checks

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

enforce_production_runtime_checks()

application = get_wsgi_application()
