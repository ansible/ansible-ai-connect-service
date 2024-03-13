"""
WSGI config for main project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/wsgi/
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

application = get_wsgi_application()
