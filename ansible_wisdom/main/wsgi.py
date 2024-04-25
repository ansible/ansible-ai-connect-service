#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

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
