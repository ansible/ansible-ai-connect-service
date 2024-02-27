#!/usr/bin/env python3

"""
Workaround to remove once we've got an image based on the ansible_wisdom
package in production.
"""

import os

from django.core.wsgi import get_wsgi_application

# Create files to store Prometheus metrics with worker ids instead of pids
# since wsgi may create a lots of pids.
try:
    import prometheus_client
    import uwsgi

    prometheus_client.values.ValueClass = prometheus_client.values.MultiProcessValue(
        process_identifier=uwsgi.worker_id
    )
except ImportError:
    pass  # not running in uwsgi

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ansible_wisdom.main.settings.development")
# Workaround until the ConfigMap are updated with the new values.
settings_module = os.environ.get("DJANGO_SETTINGS_MODULE")
if settings_module and settings_module.startswith("main.settings"):
    os.environ["DJANGO_SETTINGS_MODULE"] = f"ansible_wisdom.{settings_module}"

application = get_wsgi_application()
