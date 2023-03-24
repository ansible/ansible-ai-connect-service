import uuid
from http import HTTPStatus
from unittest.mock import patch

import grpc
from ai.api.model_client.grpc_client import GrpcClient
from ai.api.model_client.http_client import HttpClient
from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from requests.exceptions import ReadTimeout

from .test_views import WisdomServiceAPITestCaseBase

WISDOM_API_VERSION = "v0"


class TestApiTimeout(WisdomServiceAPITestCaseBase):
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
    def test_timeout_settings_is_none(self):
        model_client = HttpClient(inference_url='http://example.com/')
        self.assertIsNone(model_client.timeout)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none(self):
        model_client = HttpClient(inference_url='http://example.com/')
        self.assertEqual(123, model_client.timeout)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
    def test_timeout_settings_is_none_grpc(self):
        model_client = GrpcClient(inference_url='http://example.com/')
        self.assertIsNone(model_client.timeout)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none_grpc(self):
        model_client = GrpcClient(inference_url='http://example.com/')
        self.assertEqual(123, model_client.timeout)

    @patch("requests.Session.post", side_effect=ReadTimeout())
    def test_timeout_http_timeout(self, _):
        self.client.force_authenticate(user=self.user)
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        r = self.client.post(reverse('wisdom_api:completions'), payload)
        self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
        self.assertEqual(None, r.data)

    def mock_timeout_error():
        e = grpc.RpcError(grpc.StatusCode.DEADLINE_EXCEEDED, 'Deadline exceeded')
        e.code = lambda: grpc.StatusCode.DEADLINE_EXCEEDED
        return e

    @patch("grpc._channel._UnaryUnaryMultiCallable.__call__", side_effect=mock_timeout_error())
    def test_timeout_grpc_timeout(self, _):
        self.client.force_authenticate(user=self.user)
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            GrpcClient(inference_url='http://example.com/'),
        ):
            r = self.client.post(reverse('wisdom_api:completions'), payload)
            self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
            self.assertEqual(None, r.data)
