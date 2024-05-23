#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import uuid
from http import HTTPStatus
from unittest.mock import patch

import grpc
from django.apps import apps
from django.test import override_settings
from django.urls import reverse
from requests.exceptions import ReadTimeout

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutException
from ansible_ai_connect.ai.api.model_client.grpc_client import GrpcClient
from ansible_ai_connect.ai.api.model_client.http_client import HttpClient
from ansible_ai_connect.ai.api.model_client.wca_client import WCAClient

from .test_views import WisdomServiceAPITestCaseBase


def mock_timeout_error():
    e = grpc.RpcError(grpc.StatusCode.DEADLINE_EXCEEDED, 'Deadline exceeded')
    e.code = lambda: grpc.StatusCode.DEADLINE_EXCEEDED
    return e


class TestApiTimeout(WisdomServiceAPITestCaseBase):
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
    def test_timeout_settings_is_none(self):
        model_client = HttpClient(inference_url='http://example.com/')
        self.assertIsNone(model_client.timeout(1))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none(self):
        model_client = HttpClient(inference_url='http://example.com/')
        self.assertEqual(123, model_client.timeout(1))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none_multi_task(self):
        model_client = HttpClient(inference_url='http://example.com/')
        self.assertEqual(123 * 2, model_client.timeout(2))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
    def test_timeout_settings_is_none_grpc(self):
        model_client = GrpcClient(inference_url='http://example.com/')
        self.assertIsNone(model_client.timeout(1))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none_grpc(self):
        model_client = GrpcClient(inference_url='http://example.com/')
        self.assertEqual(123, model_client.timeout(1))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none_grpc_multi_task(self):
        model_client = GrpcClient(inference_url='http://example.com/')
        self.assertEqual(123 * 2, model_client.timeout(2))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=None)
    def test_timeout_settings_is_none_wca(self):
        model_client = WCAClient(inference_url='http://example.com/')
        self.assertIsNone(model_client.timeout(1))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none_wca(self):
        model_client = WCAClient(inference_url='http://example.com/')
        self.assertEqual(123, model_client.timeout(1))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=123)
    def test_timeout_settings_is_not_none_wca_multitask(self):
        model_client = WCAClient(inference_url='http://example.com/')
        self.assertEqual(123 * 2, model_client.timeout(2))

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
    @patch("requests.Session.post", side_effect=ReadTimeout())
    def test_timeout_http_timeout(self, _):
        self.client.force_authenticate(user=self.user)
        payload = {
            "prompt": "---\n- hosts: all\n  become: yes\n\n  tasks:\n    - name: Install Apache\n",
            "suggestionId": str(uuid.uuid4()),
        }
        with patch.object(
            apps.get_app_config('ai'),
            'model_mesh_client',
            HttpClient(inference_url='http://example.com/'),
        ):
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
            self.assert_error_detail(
                r, ModelTimeoutException.default_code, ModelTimeoutException.default_detail
            )

    @override_settings(ANSIBLE_AI_ENABLE_TECH_PREVIEW=True)
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
            r = self.client.post(reverse('completions'), payload)
            self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
            self.assert_error_detail(
                r, ModelTimeoutException.default_code, ModelTimeoutException.default_detail
            )
