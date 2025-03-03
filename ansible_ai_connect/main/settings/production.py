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
from typing import List

from .base import *  # NOQA
from .base import os


def get_allowed_hosts(ansible_wisdom_domain: str) -> List[str]:
    allowed_hosts = list(filter(len, ansible_wisdom_domain.split(",")))
    if "*" in allowed_hosts:
        return ["*"]
    if "daphne" not in allowed_hosts:
        allowed_hosts.append("daphne")
    return allowed_hosts


DEBUG = False

ALLOWED_HOSTS = get_allowed_hosts(os.getenv("ANSIBLE_WISDOM_DOMAIN", ""))

SOCIAL_AUTH_REDIRECT_IS_HTTPS = os.getenv("SOCIAL_AUTH_REDIRECT_IS_HTTPS", "True").lower() == "true"

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# "Schema 2" Telemetry Admin Dashboard URL
TELEMETRY_ADMIN_DASHBOARD_URL = "https://console.redhat.com/ansible/lightspeed-admin-dashboard"
