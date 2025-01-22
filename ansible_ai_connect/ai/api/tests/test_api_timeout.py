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
from unittest.mock import Mock, patch

import grpc
from django.apps import apps
from django.test import override_settings
from requests.exceptions import ReadTimeout

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutException
from ansible_ai_connect.ai.api.model_pipelines.grpc.pipelines import (
    GrpcCompletionsPipeline,
    GrpcMetaData,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpCompletionsPipeline,
    HttpMetaData,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
)
from ansible_ai_connect.ai.api.utils.version import api_version_reverse as reverse

from ..model_pipelines.tests import mock_pipeline_config
from .test_views import WisdomServiceAPITestCaseBase


def mock_timeout_error():
    e = grpc.RpcError(grpc.StatusCode.DEADLINE_EXCEEDED, "Deadline exceeded")
    e.code = lambda: grpc.StatusCode.DEADLINE_EXCEEDED
    return e


class TestApiTimeout(WisdomServiceAPITestCaseBase):

    def test_timeout_settings_is_none(self):
        model_client = HttpMetaData(mock_pipeline_config("http", timeout=None))
        self.assertIsNone(model_client.timeout(1))

    def test_timeout_settings_is_not_none(self):
        model_client = HttpMetaData(mock_pipeline_config("http", timeout=123))
        self.assertEqual(123, model_client.timeout(1))

    def test_timeout_settings_is_not_none_multi_task(self):
        model_client = HttpMetaData(mock_pipeline_config("http", timeout=123))
        self.assertEqual(123 * 2, model_client.timeout(2))

    def test_timeout_settings_is_none_grpc(self):
        model_client = GrpcMetaData(mock_pipeline_config("grpc", timeout=None))
        self.assertIsNone(model_client.timeout(1))

    def test_timeout_settings_is_not_none_grpc(self):
        model_client = GrpcMetaData(mock_pipeline_config("grpc", timeout=123))
        self.assertEqual(123, model_client.timeout(1))

    def test_timeout_settings_is_not_none_grpc_multi_task(self):
        model_client = GrpcMetaData(mock_pipeline_config("grpc", timeout=123))
        self.assertEqual(123 * 2, model_client.timeout(2))

    def test_timeout_settings_is_none_wca(self):
        model_client = WCASaaSCompletionsPipeline(mock_pipeline_config("wca", timeout=None))
        self.assertIsNone(model_client.timeout(1))

    def test_timeout_settings_is_not_none_wca(self):
        model_client = WCASaaSCompletionsPipeline(mock_pipeline_config("wca", timeout=123))
        self.assertEqual(123, model_client.timeout(1))

    def test_timeout_settings_is_not_none_wca_multitask(self):
        model_client = WCASaaSCompletionsPipeline(mock_pipeline_config("wca", timeout=123))
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
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=HttpCompletionsPipeline(mock_pipeline_config("http"))),
        ):
            r = self.client.post(reverse("completions"), payload)
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
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=GrpcCompletionsPipeline(mock_pipeline_config("grpc"))),
        ):
            r = self.client.post(reverse("completions"), payload)
            self.assertEqual(HTTPStatus.NO_CONTENT, r.status_code)
            self.assert_error_detail(
                r, ModelTimeoutException.default_code, ModelTimeoutException.default_detail
            )
