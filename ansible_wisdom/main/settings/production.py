import os
from typing import Literal

from .base import *  # NOQA


ANSIBLE_AI_MODEL_NAME = "wisdom"
ANSIBLE_AI_MODEL_MESH_HOST = os.environ["ANSIBLE_AI_MODEL_MESH_HOST"]
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT = os.environ["ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT"]
ANSIBLE_AI_MODEL_MESH_MANAGEMENT_PORT = 7081  # TODO: Update with correct port once exposed

# For wildcard, use a "." prefix.
# Example: .wisdom.ansible.com
ANSIBLE_WISDOM_DOMAIN = os.environ["ANSIBLE_WISDOM_DOMAIN"]

ANSIBLE_AI_MODEL_MESH_INFERENCE_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT}"
)
ANSIBLE_AI_MODEL_MESH_MANAGEMENT_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_MANAGEMENT_PORT}"
)

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [ANSIBLE_WISDOM_DOMAIN]

ANSIBLE_AI_MODEL_MESH_API_TYPE: Literal["grpc", "http"] = "http"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["ANSIBLE_AI_DATABASE_NAME"],
        "USER": os.environ["ANSIBLE_AI_DATABASE_USER"],
        "PASSWORD": os.environ["ANSIBLE_AI_DATABASE_PASSWORD"],
        "HOST": os.environ["ANSIBLE_AI_DATABASE_HOST"],
    }
}
SOCIAL_AUTH_JSONFIELD_ENABLED = True
SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["ANSIBLE_AI_CACHE_URI"],
    }
}
