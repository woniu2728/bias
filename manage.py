#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    from bias_core.startup_guard import run_django_management_with_startup_guard

    run_django_management_with_startup_guard(sys.argv)


if __name__ == "__main__":
    main()
