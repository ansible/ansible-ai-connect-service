import os
from typing import Literal

from .base import *  # NOQA

DEBUG = False

ANSIBLE_AI_MODEL_MESH_HOST = os.environ["ANSIBLE_AI_MODEL_MESH_HOST"]
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT = os.environ["ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT"]

# For wildcard, use a "." prefix.
# Example: .wisdom.ansible.com
ANSIBLE_WISDOM_DOMAIN = os.environ["ANSIBLE_WISDOM_DOMAIN"]

ANSIBLE_AI_MODEL_MESH_INFERENCE_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT}"
)

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = [ANSIBLE_WISDOM_DOMAIN]

ANSIBLE_AI_MODEL_MESH_API_TYPE: Literal["grpc", "http", "mock"] = os.getenv(
    "ANSIBLE_AI_MODEL_MESH_API_TYPE", "http"
)
SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ["ANSIBLE_AI_CACHE_URI"],
    }
}
