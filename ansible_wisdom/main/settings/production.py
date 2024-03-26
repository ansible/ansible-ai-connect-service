from .base import *  # NOQA
from .base import os

DEBUG = False

ALLOWED_HOSTS = list(filter(len, os.getenv("ANSIBLE_WISDOM_DOMAIN", "").split(",")))

SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# "Schema 2" Telemetry Admin Dashboard URL
TELEMETRY_ADMIN_DASHBOARD_URL = "https://console.redhat.com/ansible/lightspeed-admin-dashboard"
