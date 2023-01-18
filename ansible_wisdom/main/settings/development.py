import os
from typing import Literal

from .base import *  # NOQA

DEBUG = True

ANSIBLE_AI_MODEL_NAME = "wisdom"
ANSIBLE_AI_MODEL_MESH_HOST = os.getenv('ANSIBLE_AI_MODEL_MESH_HOST', 'https://wisdom-wisdom-dev.apps.dev.wisdom.testing.ansible.com')
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT = os.getenv('ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT', 443)
ANSIBLE_AI_MODEL_MESH_MANAGEMENT_PORT = 7081 # TODO: Update with correct port once exposed

ANSIBLE_AI_MODEL_MESH_INFERENCE_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT}"
)
ANSIBLE_AI_MODEL_MESH_MANAGEMENT_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_MANAGEMENT_PORT}"
)

ANSIBLE_AI_MODEL_MESH_API_TYPE: Literal["grpc", "http"] = "http"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "wisdom",
        "USER": "wisdom",
        "PASSWORD": "wisdom",
        "HOST": "db",
    }
}
SOCIAL_AUTH_JSONFIELD_ENABLED = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://redis:6379",
    }
}
