import os
from typing import Literal

from .base import *  # NOQA

DEBUG = True

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = ["*"]

ANSIBLE_AI_MODEL_MESH_HOST = os.getenv(
    'ANSIBLE_AI_MODEL_MESH_HOST', 'https://model.wisdom.testing.ansible.com'
)
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT = os.getenv('ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT', 443)

ANSIBLE_AI_MODEL_MESH_INFERENCE_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT}"
)

ANSIBLE_AI_MODEL_MESH_API_TYPE: Literal["grpc", "http", "mock"] = (
    os.getenv("ANSIBLE_AI_MODEL_MESH_API_TYPE") or "http"
)

ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PROTOCOL = (
    os.getenv("ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PROTOCOL") or "https"
)

ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PORT = (
    ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT
    if ANSIBLE_AI_MODEL_MESH_API_TYPE == 'http'
    else os.getenv('ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PORT', "8443")
    if ANSIBLE_AI_MODEL_MESH_API_TYPE == 'grpc'
    else None
)

if DEBUG:
    SPECTACULAR_SETTINGS = {
        'TITLE': 'Ansible Lightspeed with IBM Watson Code Assistant Service',
        'DESCRIPTION': 'Equip the automation developer at Lightspeed.',
        'VERSION': '0.0.7',
        'SERVE_INCLUDE_SCHEMA': False,
        # OTHER SETTINGS
        'TAGS': [
            {"name": "ai", "description": "AI-related operations"},
            {"name": "me", "description": "Authenticated user information"},
            {"name": "check", "description": "Health check"},
        ],
        'SCHEMA_PATH_PREFIX': r'/api/v[0-9]+',
    }

    # social_django does not process auth exceptions when DEBUG=True by default.
    # Following is for overriding the social_django middleware so that auth exceptions
    # are processed by middleware even when DEBUG=True.
    if "social_django.middleware.SocialAuthExceptionMiddleware" in MIDDLEWARE:  # noqa: F405
        index = MIDDLEWARE.index(  # noqa: F405
            "social_django.middleware.SocialAuthExceptionMiddleware"
        )
        MIDDLEWARE[index] = "main.middleware.WisdomSocialAuthExceptionMiddleware"  # noqa: F405
