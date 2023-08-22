import os
from typing import Literal

from .base import *  # NOQA

DEBUG = False

ANSIBLE_AI_MODEL_MESH_HOST = os.environ["ANSIBLE_AI_MODEL_MESH_HOST"]
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT = os.environ["ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT"]

# For wildcard, use a "." prefix.
# Example: .wisdom.ansible.com

ANSIBLE_AI_MODEL_MESH_INFERENCE_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT}"
)

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = list(filter(len, os.getenv("ANSIBLE_WISDOM_DOMAIN", "").split(",")))

ANSIBLE_AI_MODEL_MESH_API_TYPE: Literal["grpc", "http", "mock", "wca"] = os.getenv(
    "ANSIBLE_AI_MODEL_MESH_API_TYPE", "http"
)

ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PROTOCOL = os.getenv(
    "ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PROTOCOL", "https"
)

ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PORT = (
    ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT
    if ANSIBLE_AI_MODEL_MESH_API_TYPE == 'http'
    else os.getenv('ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PORT', "8443")
    if ANSIBLE_AI_MODEL_MESH_API_TYPE == 'grpc'
    else None
)

SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
