import uuid
from http import HTTPStatus
from unittest.mock import patch

import grpc
from ai.api.model_client.grpc_client import GrpcClient
from ai.api.model_client.http_client import HttpClient
from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from requests.exceptions import Timeout

from .test_views import WisdomServiceAPITestCaseBase


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

    @patch("ai.api.model_client.http_client.HttpClient.infer", side_effect=Timeout())
    def test_timeout_http_timeout(self, _):
        self.client.force_authenticate(user=self.user)
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        r = self.client.post(reverse('completions'), payload)
        self.assertEqual(HTTPStatus.SERVICE_UNAVAILABLE, r.status_code)
        self.assertEqual("Unable to complete the request", r.data)

    @patch("grpc.UnaryUnaryMultiCallable.__call__", side_effect=grpc.RpcError())
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
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(HTTPStatus.SERVICE_UNAVAILABLE, r.status_code)
            self.assertEqual("Unable to complete the request", r.data)
