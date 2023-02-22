import os
from typing import Literal

from .base import *  # NOQA

DEBUG = True

SECRET_KEY = os.environ["SECRET_KEY"]

ALLOWED_HOSTS = ["*"]

ANSIBLE_AI_MODEL_NAME = "wisdom"
ANSIBLE_AI_MODEL_MESH_HOST = os.getenv(
    'ANSIBLE_AI_MODEL_MESH_HOST', 'https://model.wisdom.testing.ansible.com'
)
ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT = os.getenv('ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT', 443)
ANSIBLE_AI_MODEL_MESH_MANAGEMENT_PORT = 7081  # TODO: Update with correct port once exposed

ANSIBLE_AI_MODEL_MESH_INFERENCE_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_INFERENCE_PORT}"
)
ANSIBLE_AI_MODEL_MESH_MANAGEMENT_URL = (
    f"{ANSIBLE_AI_MODEL_MESH_HOST}:{ANSIBLE_AI_MODEL_MESH_MANAGEMENT_PORT}"
)

ANSIBLE_AI_MODEL_MESH_API_TYPE: Literal["grpc", "http"] = "http"
SOCIAL_AUTH_JSONFIELD_ENABLED = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("ANSIBLE_AI_CACHE_URI", "redis://redis:6379"),
    }
}

ENABLE_ARI_POSTPROCESS = os.getenv('ENABLE_ARI_POSTPROCESS', 'False').lower() == 'true'
ARI_BASE_DIR = os.getenv('ARI_KB_PATH', '/etc/ari/kb/')
ARI_RULES_DIR = os.path.join(ARI_BASE_DIR, 'rules')
ARI_DATA_DIR = os.path.join(ARI_BASE_DIR, 'data')
ARI_RULES = [
    "P001",
    "P002",
    "P003",
    "P004",
    "W001",
    "W003",
    "W004",
    "W005",
    "W006",
    "W007",
    "W008",
    "W009",
    "W010",
    "W012",
    "W013",
]
ARI_RULE_FOR_OUTPUT_RESULT = "W007"

if DEBUG:
    SPECTACULAR_SETTINGS = {
        'TITLE': 'Ansible Wisdom Service',
        'DESCRIPTION': 'Equip the automation developer with Wisdom super powers.',
        'VERSION': '0.0.2',
        'SERVE_INCLUDE_SCHEMA': False,
        # OTHER SETTINGS
        'TAGS': [{"name": "ai", "description": "AI-related operations"}],
    }
