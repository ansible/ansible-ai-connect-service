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

from http import HTTPStatus
from unittest import mock

from django.apps import apps
from django.core.cache import cache

from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
    DummyCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.versions.v1.test_base import API_VERSION
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
