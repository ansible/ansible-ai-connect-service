#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ansible_wisdom.main.settings.development")
    # Workaround until the ConfigMap are updated with the new values.
    settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
    if settings_module and settings_module.startswith("main.settings"):
        os.environ["DJANGO_SETTINGS_MODULE"] = f"ansible_wisdom.{settings_module}"

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
