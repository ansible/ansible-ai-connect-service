import os
from typing import Literal

from .base import *  # NOQA

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

MOCK_ANSIBLE_AI_SEARCH_RESULT = {
    'attributions': [
        {
            'repo_name': "performance-test",
            'repo_url': "https://github.com/ansible/perf",
            'path': "bar",
            'license': "v1",
            'data_source': "aws",
            'ansible_type': "lightspeed",
            'score': 0,
        }
    ],
    'meta': {
        'encode_duration': 1,
        'search_duration': 1,
    },
}
