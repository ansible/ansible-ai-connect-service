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
import logging
import time
from abc import abstractmethod
from http import HTTPStatus
from typing import Optional
from unittest import mock
from unittest.mock import Mock, patch

from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from requests import Response
from requests.exceptions import HTTPError
from rest_framework.test import APITestCase

import ansible_ai_connect.ai.feature_flags as feature_flags
from ansible_ai_connect.ai.api.aws.wca_secret_manager import WcaSecretManagerError
from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
    DummyCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaInferenceFailure,
    WcaTokenFailure,
)
from ansible_ai_connect.ai.api.model_pipelines.grpc.pipelines import (
    GrpcCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpChatBotPipeline,
    HttpCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipeline,
    ModelPipelineCompletions,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY_ENTRY
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
    WCAOnPremCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
    WCASaaSCompletionsPipeline,
)
from ansible_ai_connect.main.settings.types import t_model_mesh_api_type
from ansible_ai_connect.test_utils import (
    WisdomAppsBackendMocking,
    WisdomServiceLogAwareTestCase,
)

logger = logging.getLogger(__name__)

aliases = [
    "db",
    "secret-manager",
    "authorization",
]

pipeline_aliases = []
for pipeline in REGISTRY_ENTRY.keys():
    if issubclass(pipeline, ModelPipeline):
        pipeline_aliases.append(pipeline.alias())


@override_settings(LAUNCHDARKLY_SDK_KEY=None)
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(CHATBOT_DEFAULT_PROVIDER="wisdom")
class BaseTestHealthCheck(WisdomAppsBackendMocking, APITestCase, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.mock_seat_checker_with(Mock())

    def is_status_ok(self, status, pipeline_type: t_model_mesh_api_type):
        if isinstance(status, str):
            return status == "ok"
        if isinstance(status, dict):
            children = dict(status)
            if "provider" in children:
                provider = status.get("provider")
                self.assertEqual(provider, pipeline_type)
                children.pop("provider")

            child_status = [k for (k, v) in children.items() if self.is_status_ok(v, pipeline_type)]
            return len(child_status) == len(children)

    @staticmethod
    def mocked_requests_succeed(content=b"", *args, **kwargs):
        r = Response()
        r.status_code = HTTPStatus.OK
        r._content = content
        return r

    @staticmethod
    def mocked_requests_failed(*args, **kwargs):
        r = Response()
        r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return r

    @staticmethod
    def getHealthCheckErrorString(plugin_name, plugin_status):
        return (
            f'HEALTH CHECK ERROR: {{"name": "{plugin_name}", '
            f'"status": {json.dumps(plugin_status)}, "time_taken":'
        )

    def assertHealthCheckErrorInLog(self, log, error_msg, plugin_name, plugin_status):
        self.assertInLog(error_msg, log)
        self.assertInLog(
            self.getHealthCheckErrorString(plugin_name, plugin_status),
            log,
        )

    def assertHealthCheckErrorNotInLog(self, log, error_msg, plugin_name, plugin_status):
        logger.error("Dummy Error")  # assertLogs expects at least one log entry...
        self.assertNotInLog(error_msg, log)
        self.assertNotInLog(
            self.getHealthCheckErrorString(plugin_name, plugin_status),
            log,
        )

    def assert_common_data(self, data: dict, expected_status: str, deployed_region: str):
        self.assertIsNotNone(data["timestamp"])
        self.assertIsNotNone(data["version"])
        self.assertIsNotNone(data["git_commit"])
        self.assertEqual(data.get("deployed_region"), deployed_region)
        self.assertEqual(expected_status, data["status"])

    def assert_basic_data(
        self,
        r: Response,
        expected_status: str,
        deployed_region: Optional[str] = settings.DEPLOYED_REGION,
    ) -> (str, []):
        """
        Performs assertion of the basic data returned for all Health Checks.
        :param r: HTTP Response
        :param expected_status: HTTP status
        :param deployed_region: The region to which the service is deployed
        :return: (timestamp, dependencies) tuple from the basic data.
        """
        data = json.loads(r.content)
        self.assert_common_data(data, expected_status, deployed_region)
        timestamp = data["timestamp"]
        dependencies = data.get("dependencies", [])
        self.assertEqual(11, len(dependencies))
        for dependency in dependencies:
            self.assertIn(
                dependency["name"],
                aliases + pipeline_aliases,
            )
            self.assertGreaterEqual(dependency["time_taken"], 0)

        return timestamp, dependencies


class TestHealthCheck(BaseTestHealthCheck):

    def test_liveness_probe(self):
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=DummyCompletionsPipeline(mock_pipeline_config("dummy"))),
        ):
            r = self.client.get(reverse("liveness_probe"), format="json")
            self.assertEqual(r.status_code, HTTPStatus.OK)
            data = json.loads(r.content)
            self.assert_common_data(data, "ok", settings.DEPLOYED_REGION)

    def test_health_check_all_healthy(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            timestamp, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

            time.sleep(1)

            # Make sure the cached data is returned in the second call after 1 sec
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            data = json.loads(r.content)
            self.assertEqual(timestamp, data["timestamp"])

    @override_settings(DEPLOYED_REGION="")
    def test_health_check_without_deployed_region(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            timestamp, dependencies = self.assert_basic_data(r, "ok", None)
            for dependency in dependencies:
                self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

    def test_health_check_model_mesh_mock(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

    @override_settings(LAUNCHDARKLY_SDK_KEY="dummy_key")
    @patch.object(feature_flags, "LDClient")
    def test_health_check_model_mesh_mock_with_launchdarkly(self, LDClient):
        cache.clear()
        LDClient.return_value.variation.return_value = "server:port:model_name:index"
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

    def test_health_check_model_mesh_mock_disabled(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=False)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                if dependency["name"] in pipeline_aliases:
                    self.assertEqual(dependency["status"], "disabled")
                else:
                    self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

    def test_health_check_aws_secret_manager_error(self):
        cache.clear()
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_secret_manager.get_secret = Mock(side_effect=WcaSecretManagerError)

        with self.assertLogs(logger="root", level="ERROR") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=DummyCompletionsPipeline(
                        mock_pipeline_config("dummy", enable_health_check=True)
                    )
                ),
            ):
                r = self.client.get(reverse("health_check"))

                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] == "secret-manager":
                        self.assertTrue(dependency["status"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "ansible_ai_connect.ai.api.aws.exceptions.WcaSecretManagerError",
                    "secret-manager",
                    "unavailable: An error occurred",
                )

    @override_settings(ENABLE_HEALTHCHECK_SECRET_MANAGER=False)
    def test_health_check_aws_secret_manager_disabled(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                if dependency["name"] == "secret-manager":
                    self.assertEqual(dependency["status"], "disabled")
                else:
                    self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

    def test_health_check_authorization_error(self, *args):
        cache.clear()
        apps.get_app_config("ai")._seat_checker.self_test = Mock(side_effect=HTTPError)

        with self.assertLogs(logger="root", level="ERROR") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=DummyCompletionsPipeline(
                        mock_pipeline_config("dummy", enable_health_check=True)
                    )
                ),
            ):
                r = self.client.get(reverse("health_check"))

                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] == "authorization":
                        self.assertTrue(dependency["status"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "requests.exceptions.HTTPError",
                    "authorization",
                    "unavailable: An error occurred",
                )

    @override_settings(ENABLE_HEALTHCHECK_AUTHORIZATION=False)
    def test_health_check_authorization_disabled(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=DummyCompletionsPipeline(
                    mock_pipeline_config("dummy", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                if dependency["name"] == "authorization":
                    self.assertEqual(dependency["status"], "disabled")
                else:
                    self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

    @mock.patch(
        "requests.get",
        side_effect=lambda *args, **kwargs: BaseTestHealthCheck.mocked_requests_succeed(
            content=b'{ "ready": true, "reason": "service is ready" }'
        ),
    )
    def test_health_check_chatbot_service(self, mock_get):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                self.assertTrue(self.is_status_ok(dependency["status"], "http"))

    @mock.patch(
        "requests.get",
        side_effect=lambda *args, **kwargs: BaseTestHealthCheck.mocked_requests_succeed(
            content=b'{ "ready": false, "reason": "index is not ready" }'
        ),
    )
    def test_health_check_chatbot_service_index_not_ready(self, mock_get):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "index is not ready",
                    "chatbot-service",
                    {"provider": "http", "models": "unavailable: index is not ready"},
                )

    @mock.patch(
        "requests.get",
        side_effect=lambda *args, **kwargs: BaseTestHealthCheck.mocked_requests_succeed(
            content=b'{ "ready": false, "reason": "llm is not ready" }'
        ),
    )
    def test_health_check_chatbot_service_llm_not_ready(self, mock_get):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "llm is not ready",
                    "chatbot-service",
                    {"provider": "http", "models": "unavailable: llm is not ready"},
                )

    @mock.patch(
        "requests.get",
        side_effect=HTTPError,
    )
    def test_health_check_chatbot_service_error(self, mock_get):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "requests.exceptions.HTTPError",
                    "chatbot-service",
                    {"provider": "http", "models": "unavailable: An error occurred"},
                )

    @mock.patch(
        "requests.get",
        side_effect=BaseTestHealthCheck.mocked_requests_failed,
    )
    def test_health_check_chatbot_service_non_200_response(self, mock_get):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "503 Server Error",
                    "chatbot-service",
                    {"provider": "http", "models": "unavailable: An error occurred"},
                )

    @mock.patch(
        "requests.get",
        side_effect=BaseTestHealthCheck.mocked_requests_succeed,
    )
    def test_health_check_chatbot_service_disabled(self, mock_get):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=HttpChatBotPipeline(
                    mock_pipeline_config("http", enable_health_check=False)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                if dependency["name"] in pipeline_aliases:
                    self.assertEqual(dependency["status"], "disabled")
                else:
                    self.assertTrue(self.is_status_ok(dependency["status"], "dummy"))


class TestHealthCheckGrpcClient(BaseTestHealthCheck):

    @staticmethod
    def mocked_requests_grpc_fail(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith("/oauth/healthz"):
            r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return r

    def setUp(self):
        super().setUp()
        self.requests_patcher = patch("requests.get")
        self.mock_requests = self.requests_patcher.start()

    def tearDown(self):
        super().tearDown()
        self.requests_patcher.stop()

    def test_health_check_model_mesh_grpc(self):
        cache.clear()
        self.mock_requests.side_effect = TestHealthCheck.mocked_requests_succeed

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=GrpcCompletionsPipeline(
                    mock_pipeline_config("grpc", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                self.assertTrue(self.is_status_ok(dependency["status"], "grpc"))

    def test_health_check_model_mesh_grpc_error(self):
        cache.clear()
        self.mock_requests.side_effect = TestHealthCheckGrpcClient.mocked_requests_grpc_fail

        with self.assertLogs(logger="root", level="ERROR") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=GrpcCompletionsPipeline(
                        mock_pipeline_config("grpc", enable_health_check=True)
                    )
                ),
            ):
                r = self.client.get(reverse("health_check"))
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "grpc"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "requests.exceptions.HTTPError",
                    "model-server",
                    {
                        "provider": "grpc",
                        "models": "unavailable: An error occurred",
                    },
                )


class TestHealthCheckHttpClient(BaseTestHealthCheck):

    @staticmethod
    def mocked_requests_http_fail(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith("/ping"):
            r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return r

    def setUp(self):
        super().setUp()
        self.requests_patcher = patch("requests.get")
        self.mock_requests = self.requests_patcher.start()

    def tearDown(self):
        super().tearDown()
        self.requests_patcher.stop()

    def test_health_check_model_mesh_http(self):
        cache.clear()
        self.mock_requests.side_effect = TestHealthCheck.mocked_requests_succeed

        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(
                return_value=HttpCompletionsPipeline(
                    mock_pipeline_config("http", enable_health_check=True)
                )
            ),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                self.assertTrue(self.is_status_ok(dependency["status"], "http"))

    def test_health_check_model_mesh_http_error(self):
        cache.clear()
        self.mock_requests.side_effect = TestHealthCheckHttpClient.mocked_requests_http_fail

        with self.assertLogs(logger="root", level="ERROR") as log:
            with patch.object(
                apps.get_app_config("ai"),
                "get_model_pipeline",
                Mock(
                    return_value=HttpCompletionsPipeline(
                        mock_pipeline_config("http", enable_health_check=True)
                    )
                ),
            ):
                r = self.client.get(reverse("health_check"))
                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                timestamp, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "http"))
                    self.assertGreaterEqual(dependency["time_taken"], 0)

                    self.assertHealthCheckErrorInLog(
                        log,
                        "requests.exceptions.HTTPError",
                        "model-server",
                        {
                            "provider": "http",
                            "models": "unavailable: An error occurred",
                        },
                    )


class BaseTestHealthCheckWCAClient(BaseTestHealthCheck):

    def setUp(self):
        super().setUp()
        self.requests_patcher = patch("requests.Session.post")
        self.mock_requests = self.requests_patcher.start()

    def tearDown(self):
        super().tearDown()
        self.requests_patcher.stop()

    @abstractmethod
    def get_wca_client(self, enable_health_check: bool = True):
        pass

    def _do_test_health_check_wca_disabled(self, pipeline_type: t_model_mesh_api_type):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client(False)),
        ):
            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                if dependency["name"] in pipeline_aliases:
                    self.assertEqual(dependency["status"], "disabled")
                else:
                    self.assertTrue(self.is_status_ok(dependency["status"], pipeline_type))


class TestHealthCheckWCAClient(BaseTestHealthCheckWCAClient):

    def get_wca_client(self, enable_health_check: bool = True):
        return WCASaaSCompletionsPipeline(
            mock_pipeline_config("wca", enable_health_check=enable_health_check)
        )

    def test_health_check_wca_token_error(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client()),
        ):
            mock_wca_client: ModelPipelineCompletions = apps.get_app_config(
                "ai"
            ).get_model_pipeline(ModelPipelineCompletions)
            mock_wca_client.infer_from_parameters = Mock(side_effect=WcaTokenFailure)

            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))

                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        # If a Token cannot be retrieved we can also not execute Models
                        self.assertTrue(dependency["status"]["tokens"].startswith("unavailable:"))
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "wca"))

                self.assertHealthCheckErrorInLog(
                    log,
                    "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaTokenFailure",
                    "model-server",
                    {
                        "provider": "wca",
                        "tokens": "unavailable: An error occurred",
                        "models": "unavailable: An error occurred",
                    },
                )

    def test_health_check_wca_inference_error(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client()),
        ):
            mock_wca_client: ModelPipelineCompletions = apps.get_app_config(
                "ai"
            ).get_model_pipeline(ModelPipelineCompletions)
            mock_wca_client.infer_from_parameters = Mock(side_effect=WcaInferenceFailure)

            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))

                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertEqual(dependency["status"]["tokens"], "ok")
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "wca"))
                    self.assertGreaterEqual(dependency["time_taken"], 0)

                self.assertHealthCheckErrorInLog(
                    log,
                    "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaInferenceFailure",
                    "model-server",
                    {"provider": "wca", "tokens": "ok", "models": "unavailable: An error occurred"},
                )

    def test_health_check_wca_inference_generic_error(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client()),
        ):
            mock_wca_client: ModelPipelineCompletions = apps.get_app_config(
                "ai"
            ).get_model_pipeline(ModelPipelineCompletions)
            mock_wca_client.infer_from_parameters = Mock(side_effect=Exception)

            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))

                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["tokens"].startswith("unavailable:"))
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "wca"))
                    self.assertGreaterEqual(dependency["time_taken"], 0)

                self.assertHealthCheckErrorInLog(
                    log,
                    "Exception",
                    "model-server",
                    {
                        "provider": "wca",
                        "tokens": "unavailable: An error occurred",
                        "models": "unavailable: An error occurred",
                    },
                )

    def test_health_check_wca_enabled(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client()),
        ):
            mock_wca_client: ModelPipelineCompletions = apps.get_app_config(
                "ai"
            ).get_model_pipeline(ModelPipelineCompletions)
            mock_wca_client.infer_from_parameters = Mock(return_value=Mock())

            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                if dependency["name"] in pipeline_aliases:
                    self.assertEqual(dependency["status"]["tokens"], "ok")
                    self.assertEqual(dependency["status"]["models"], "ok")
                else:
                    self.assertTrue(self.is_status_ok(dependency["status"], "wca"))

    def test_health_check_wca_disabled(self):
        self._do_test_health_check_wca_disabled("wca")


class TestHealthCheckWCAOnPremClient(BaseTestHealthCheckWCAClient):

    def get_wca_client(self, enable_health_check: bool = True):
        return WCAOnPremCompletionsPipeline(
            mock_pipeline_config("wca-onprem", enable_health_check=enable_health_check)
        )

    def test_health_check_wca_onprem_inference_error(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client()),
        ):
            mock_wca_client: ModelPipelineCompletions = apps.get_app_config(
                "ai"
            ).get_model_pipeline(ModelPipelineCompletions)
            mock_wca_client.infer_from_parameters = Mock(side_effect=WcaInferenceFailure)

            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))

                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "wca-onprem"))
                    self.assertGreaterEqual(dependency["time_taken"], 0)

                self.assertHealthCheckErrorInLog(
                    log,
                    "ansible_ai_connect.ai.api.model_pipelines.exceptions.WcaInferenceFailure",
                    "model-server",
                    {"provider": "wca-onprem", "models": "unavailable: An error occurred"},
                )

    def test_health_check_wca_onprem_inference_generic_error(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client()),
        ):
            mock_wca_client: ModelPipelineCompletions = apps.get_app_config(
                "ai"
            ).get_model_pipeline(ModelPipelineCompletions)
            mock_wca_client.infer_from_parameters = Mock(side_effect=Exception)

            with self.assertLogs(logger="root", level="ERROR") as log:
                r = self.client.get(reverse("health_check"))

                self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
                _, dependencies = self.assert_basic_data(r, "error")
                for dependency in dependencies:
                    if dependency["name"] in pipeline_aliases:
                        self.assertTrue(dependency["status"]["models"].startswith("unavailable:"))
                    else:
                        self.assertTrue(self.is_status_ok(dependency["status"], "wca-onprem"))
                    self.assertGreaterEqual(dependency["time_taken"], 0)

                self.assertHealthCheckErrorInLog(
                    log,
                    "Exception",
                    "model-server",
                    {
                        "provider": "wca-onprem",
                        "models": "unavailable: An error occurred",
                    },
                )

    def test_health_check_wca_on_prem_enabled(self):
        cache.clear()
        with patch.object(
            apps.get_app_config("ai"),
            "get_model_pipeline",
            Mock(return_value=self.get_wca_client()),
        ):
            mock_wca_client: ModelPipelineCompletions = apps.get_app_config(
                "ai"
            ).get_model_pipeline(ModelPipelineCompletions)
            mock_wca_client.infer_from_parameters = Mock(return_value=Mock())

            r = self.client.get(reverse("health_check"))
            self.assertEqual(r.status_code, HTTPStatus.OK)
            _, dependencies = self.assert_basic_data(r, "ok")
            for dependency in dependencies:
                if dependency["name"] in pipeline_aliases:
                    self.assertEqual(dependency["status"]["models"], "ok")
                else:
                    self.assertTrue(self.is_status_ok(dependency["status"], "wca-onprem"))

    def test_health_check_wca_on_prem_disabled(self):
        self._do_test_health_check_wca_disabled("wca-onprem")
