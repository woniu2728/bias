#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


STARTUP_GUARD_EXEMPT_COMMANDS = {
    "create_extension",
    "inspect_extensions",
    "validate_extensions",
}


def should_enforce_startup_guard(argv: list[str]) -> bool:
    if len(argv) < 2:
        return True

    return argv[1] not in STARTUP_GUARD_EXEMPT_COMMANDS


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    from apps.core.startup_guard import enforce_production_runtime_checks

    django.setup()
    if should_enforce_startup_guard(sys.argv):
        enforce_production_runtime_checks()
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
