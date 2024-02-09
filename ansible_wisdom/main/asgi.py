"""
ASGI config for main project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ansible_wisdom.main.settings.development")
# Workaround until the ConfigMap are updated with the new values.
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if settings_module and settings_module.startswith("main.settings"):
    os.environ["DJANGO_SETTINGS_MODULE"] = f"ansible_wisdom.{settings_module}"

application = get_asgi_application()
