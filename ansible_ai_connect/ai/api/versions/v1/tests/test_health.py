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
import json
from http import HTTPStatus
from unittest import mock

from django.apps import apps
from django.core.cache import cache
from requests.exceptions import HTTPError

from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
    DummyCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import HttpChatBotPipeline
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION
from ansible_ai_connect.healthcheck.tests.test_healthcheck import BaseTestHealthCheck
from ansible_ai_connect.main.tests.test_views import (
    APITransactionTestCase,
    APIVersionTestCaseBase,
)


class TestHealthAnonymousUser(APIVersionTestCaseBase, APITransactionTestCase):
    api_version = API_VERSION

    def test_health_access(self):
        response = self.client.get(self.api_version_reverse("health"))
        self.assertEqual(response.status_code, HTTPStatus.OK)
        self.assertEqual(response.json().get("status"), "ok")

    def test_health_status_access(self):
        cache.clear()
        with mock.patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            mock.Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=True)
                )
            ),
        ):
            response = self.client.get(self.api_version_reverse("health_status"))
            self.assertEqual(response.status_code, HTTPStatus.OK)
            data = response.json()
            self.assertEqual(data.get("status"), "ok")
            self.assertTrue("dependencies" in data)
            self.assertTrue(len(data["dependencies"]) > 0)


class TestHealthChatbotView(APIVersionTestCaseBase, APITransactionTestCase):
    api_version = API_VERSION

    @mock.patch(
        "requests.get",
        side_effect=lambda *args, **kwargs: BaseTestHealthCheck.mocked_requests_succeed(
            content=b'{ "ready": true, "reason": "service is ready" }'
        ),
    )
    def test_health_check_chatbot_service(self, mock_get):
        cache.clear()
        with mock.patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            mock.Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(self.api_version_reverse("health_status_chatbot"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            data = json.loads(r.content)
            self.assertEqual(data["chatbot-service"], "ok")
            self.assertEqual(data["streaming-chatbot-service"], "ok")

    @mock.patch(
        "requests.get",
        side_effect=HTTPError,
    )
    def test_health_check_chatbot_service_error(self, mock_get):
        cache.clear()
        with mock.patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            mock.Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(self.api_version_reverse("health_status_chatbot"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            data = json.loads(r.content)
            self.assertEqual(data["chatbot-service"], "unavailable: An error occurred")
            self.assertEqual(data["streaming-chatbot-service"], "unavailable: An error occurred")

    @mock.patch(
        "requests.get",
        side_effect=BaseTestHealthCheck.mocked_requests_succeed,
    )
    def test_health_check_chatbot_service_disabled(self, mock_get):
        cache.clear()
        with mock.patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            mock.Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=False)
                )
            ),
        ):
            r = self.client.get(self.api_version_reverse("health_status_chatbot"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            data = json.loads(r.content)
            self.assertEqual(data["chatbot-service"], "disabled")
            self.assertEqual(data["streaming-chatbot-service"], "disabled")
