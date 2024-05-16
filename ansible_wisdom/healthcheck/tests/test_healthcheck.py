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
from http import HTTPStatus
from typing import Optional
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
from ansible_ai_connect.ai.api.model_client.wca_client import (
    WCAClient,
    WcaInferenceFailure,
    WCAOnPremClient,
    WcaTokenFailure,
)
from ansible_ai_connect.test_utils import (
    WisdomAppsBackendMocking,
    WisdomServiceLogAwareTestCase,
)

logger = logging.getLogger(__name__)


def is_status_ok(status):
    if isinstance(status, str):
        return status == 'ok'
    if isinstance(status, dict):
        child_status = [k for (k, v) in status.items() if is_status_ok(v)]
        return len(child_status) == len(status)


@override_settings(LAUNCHDARKLY_SDK_KEY=None)
@override_settings(AUTHZ_BACKEND_TYPE="dummy")
@override_settings(WCA_SECRET_BACKEND_TYPE="dummy")
@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
class BaseTestHealthCheck(WisdomAppsBackendMocking, APITestCase, WisdomServiceLogAwareTestCase):
    def setUp(self):
        super().setUp()
        self.mock_seat_checker_with(Mock())
        self.model_server_patcher = patch('ansible_ai_connect.healthcheck.backends.requests')
        self.mock_requests = self.model_server_patcher.start()
        self.mock_requests.get = BaseTestHealthCheck.mocked_requests_succeed

        self.attribution_search_patcher = patch('ansible_ai_connect.ai.search.search')
        self.mock_ai_search = self.attribution_search_patcher.start()
        self.mock_ai_search.return_value = {"attributions": ["an attribution"]}

    def tearDown(self):
        self.model_server_patcher.stop()
        self.attribution_search_patcher.stop()

    @staticmethod
    def mocked_requests_succeed(*args, **kwargs):
        r = Response()
        r.status_code = HTTPStatus.OK
        return r

    @staticmethod
    def mocked_requests_http_fail(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith('/ping'):
            r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return r

    @staticmethod
    def mocked_requests_grpc_fail(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith('/oauth/healthz'):
            r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        return r

    def test_liveness_probe(self):
        r = self.client.get(reverse('liveness_probe'), format='json')
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assert_common_data(data, 'ok', settings.DEPLOYED_REGION)

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
        logger.error('Dummy Error')  # assertLogs expects at least one log entry...
        self.assertNotInLog(error_msg, log)
        self.assertNotInLog(
            self.getHealthCheckErrorString(plugin_name, plugin_status),
            log,
        )

    def assert_common_data(self, data: dict, expected_status: str, deployed_region: str):
        self.assertIsNotNone(data['timestamp'])
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertEqual(data.get('deployed_region'), deployed_region)
        self.assertEqual(expected_status, data['status'])

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
        timestamp = data['timestamp']
        self.assertIsNotNone(data['model_name'])
        dependencies = data.get('dependencies', [])
        self.assertEqual(6, len(dependencies))
        for dependency in dependencies:
            self.assertIn(
                dependency['name'],
                [
                    'cache',
                    'db',
                    'model-server',
                    'secret-manager',
                    'attribution',
                    'wca',
                    'authorization',
                ],
            )
            self.assertGreaterEqual(dependency['time_taken'], 0)

        return timestamp, dependencies


class TestHealthCheck(BaseTestHealthCheck):
    def setUp(self):
        super().setUp()
        self.mock_wca_client_with(Mock(spec=WCAClient))

    def test_health_check_all_healthy(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        timestamp, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            self.assertTrue(is_status_ok(dependency['status']))

        time.sleep(1)

        # Make sure the cached data is returned in the second call after 1 sec
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assertEqual(timestamp, data['timestamp'])

    @override_settings(DEPLOYED_REGION="")
    def test_health_check_without_deployed_region(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        timestamp, dependencies = self.assert_basic_data(r, 'ok', None)
        for dependency in dependencies:
            self.assertTrue(is_status_ok(dependency['status']))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="http")
    def test_health_check_model_mesh_http_error(self):
        cache.clear()
        self.mock_requests.get = TestHealthCheck.mocked_requests_http_fail

        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            timestamp, dependencies = self.assert_basic_data(r, 'error')
            for dependency in dependencies:
                if dependency['name'] == 'model-server':
                    self.assertTrue(dependency['status'].startswith('unavailable:'))
                else:
                    self.assertTrue(is_status_ok(dependency['status']))
                self.assertGreaterEqual(dependency['time_taken'], 0)

                self.assertHealthCheckErrorInLog(
                    log,
                    'Exception',
                    'model-server',
                    'unavailable: An error occurred',
                )

        time.sleep(1)

        # Make sure the cached data is returned in the second call after 1 sec
        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            data = json.loads(r.content)
            self.assertEqual(timestamp, data['timestamp'])

            self.assertHealthCheckErrorNotInLog(
                log,
                'Exception',
                'model-server',
                'unavailable: An error occurred',
            )

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    def test_health_check_model_mesh_grpc(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            self.assertTrue(is_status_ok(dependency['status']))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    def test_health_check_model_mesh_grpc_error(self):
        cache.clear()
        self.mock_requests.get = TestHealthCheck.mocked_requests_grpc_fail
        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))
            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            _, dependencies = self.assert_basic_data(r, 'error')
            for dependency in dependencies:
                if dependency['name'] == 'model-server':
                    self.assertTrue(dependency['status'].startswith('unavailable:'))
                else:
                    self.assertTrue(is_status_ok(dependency['status']))

            self.assertHealthCheckErrorInLog(
                log,
                'unavailable: An error occurred',
                'model-server',
                'unavailable: An error occurred',
            )

    def test_health_check_model_mesh_mock(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            self.assertTrue(is_status_ok(dependency['status']))

    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @patch.object(feature_flags, 'LDClient')
    def test_health_check_model_mesh_mock_with_launchdarkly(self, LDClient):
        cache.clear()
        LDClient.return_value.variation.return_value = 'server:port:model_name:index'
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            self.assertTrue(is_status_ok(dependency['status']))

    @override_settings(ENABLE_HEALTHCHECK_MODEL_MESH=False)
    def test_health_check_model_mesh_mock_disabled(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            if dependency['name'] == 'model-server':
                self.assertEqual(dependency['status'], 'disabled')
            else:
                self.assertTrue(is_status_ok(dependency['status']))

    def test_health_check_aws_secret_manager_error(self):
        cache.clear()
        mock_secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        mock_secret_manager.get_secret = Mock(side_effect=WcaSecretManagerError)

        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))

            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            _, dependencies = self.assert_basic_data(r, 'error')
            for dependency in dependencies:
                if dependency['name'] == 'secret-manager':
                    self.assertTrue(dependency['status'].startswith('unavailable:'))
                else:
                    self.assertTrue(is_status_ok(dependency['status']))

            self.assertHealthCheckErrorInLog(
                log,
                'ansible_ai_connect.ai.api.aws.exceptions.WcaSecretManagerError',
                'secret-manager',
                'unavailable: An error occurred',
            )

    @override_settings(ENABLE_HEALTHCHECK_SECRET_MANAGER=False)
    def test_health_check_aws_secret_manager_disabled(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            if dependency['name'] == 'secret-manager':
                self.assertEqual(dependency['status'], 'disabled')
            else:
                self.assertTrue(is_status_ok(dependency['status']))

    def test_health_check_authorization_error(self, *args):
        cache.clear()
        apps.get_app_config('ai')._seat_checker.self_test = Mock(side_effect=HTTPError)

        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))

            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            _, dependencies = self.assert_basic_data(r, 'error')
            for dependency in dependencies:
                if dependency['name'] == 'authorization':
                    self.assertTrue(dependency['status'].startswith('unavailable:'))
                else:
                    self.assertTrue(is_status_ok(dependency['status']))

            self.assertHealthCheckErrorInLog(
                log,
                'requests.exceptions.HTTPError',
                'authorization',
                'unavailable: An error occurred',
            )

    @override_settings(ENABLE_HEALTHCHECK_AUTHORIZATION=False)
    def test_health_check_authorization_disabled(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            if dependency['name'] == 'authorization':
                self.assertEqual(dependency['status'], 'disabled')
            else:
                self.assertTrue(is_status_ok(dependency['status']))

    def test_health_check_attribution_error(self, *args):
        cache.clear()

        self.mock_ai_search.return_value = {"something": "is_wrong"}
        r = self.client.get(reverse('health_check'))

        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        attribution_result = None
        for dependency in dependencies:
            if dependency['name'] == 'attribution':
                attribution_result = dependency
                break

        self.assertTrue(attribution_result['status'].startswith('unavailable:'))

    @override_settings(ENABLE_HEALTHCHECK_ATTRIBUTION=False)
    def test_health_check_attribution_disabled(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            if dependency['name'] == 'attribution':
                self.assertEqual(dependency['status'], 'disabled')
            else:
                self.assertTrue(is_status_ok(dependency['status']))


class BaseTestHealthCheckWCAClient(BaseTestHealthCheck):
    def setUp(self):
        super().setUp()
        self.mock_wca_client_with(Mock(spec=self.get_wca_client_type()))

    def get_wca_client_type(self):
        # Overridden by concrete WCA test classes
        return WCAClient

    def _do_test_health_check_wca_token_error(self):
        cache.clear()
        mock_wca_client = apps.get_app_config("ai").get_wca_client()
        self.assertIsInstance(mock_wca_client, self.get_wca_client_type())
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaTokenFailure)

        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))

            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            _, dependencies = self.assert_basic_data(r, 'error')
            for dependency in dependencies:
                if dependency['name'] == 'wca':
                    # If a Token cannot be retrieved we can also not execute Models
                    self.assertTrue(dependency['status']['tokens'].startswith('unavailable:'))
                    self.assertTrue(dependency['status']['models'].startswith('unavailable:'))
                else:
                    self.assertTrue(is_status_ok(dependency['status']))

            self.assertHealthCheckErrorInLog(
                log,
                'ansible_ai_connect.ai.api.model_client.exceptions.WcaTokenFailure',
                'wca',
                {
                    "tokens": "unavailable: An error occurred",
                    "models": "unavailable: An error occurred",
                },
            )

    def _do_test_health_check_wca_inference_error(self):
        cache.clear()
        mock_wca_client = apps.get_app_config("ai").get_wca_client()
        self.assertIsInstance(mock_wca_client, self.get_wca_client_type())
        mock_wca_client.infer_from_parameters = Mock(side_effect=WcaInferenceFailure)

        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))

            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            _, dependencies = self.assert_basic_data(r, 'error')
            for dependency in dependencies:
                if dependency['name'] == 'wca':
                    self.assertEqual(dependency['status']['tokens'], 'ok')
                    self.assertTrue(dependency['status']['models'].startswith('unavailable:'))
                else:
                    self.assertTrue(is_status_ok(dependency['status']))
                self.assertGreaterEqual(dependency['time_taken'], 0)

            self.assertHealthCheckErrorInLog(
                log,
                'ansible_ai_connect.ai.api.model_client.exceptions.WcaInferenceFailure',
                'wca',
                {"tokens": "ok", "models": "unavailable: An error occurred"},
            )

    def _do_test_health_check_wca_inference_generic_error(self):
        cache.clear()
        mock_wca_client = apps.get_app_config("ai").get_wca_client()
        self.assertIsInstance(mock_wca_client, self.get_wca_client_type())
        mock_wca_client.infer_from_parameters = Mock(side_effect=Exception)

        with self.assertLogs(logger='root', level='ERROR') as log:
            r = self.client.get(reverse('health_check'))

            self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
            _, dependencies = self.assert_basic_data(r, 'error')
            for dependency in dependencies:
                if dependency['name'] == 'wca':
                    self.assertTrue(dependency['status']['tokens'].startswith('unavailable:'))
                    self.assertTrue(dependency['status']['models'].startswith('unavailable:'))
                else:
                    self.assertTrue(is_status_ok(dependency['status']))
                self.assertGreaterEqual(dependency['time_taken'], 0)

            self.assertHealthCheckErrorInLog(
                log,
                'Exception',
                'wca',
                {
                    "tokens": "unavailable: An error occurred",
                    "models": "unavailable: An error occurred",
                },
            )

    def _do_test_health_check_wca_enable(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            if dependency['name'] == 'wca':
                self.assertEqual(dependency['status']['tokens'], 'ok')
                self.assertEqual(dependency['status']['models'], 'ok')
            else:
                self.assertTrue(is_status_ok(dependency['status']))

    def _do_test_health_check_wca_disabled(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        _, dependencies = self.assert_basic_data(r, 'ok')
        for dependency in dependencies:
            if dependency['name'] == 'wca':
                self.assertEqual(dependency['status']['tokens'], 'disabled')
                self.assertEqual(dependency['status']['models'], 'disabled')
            else:
                self.assertTrue(is_status_ok(dependency['status']))


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca")
class TestHealthCheckWCAClient(BaseTestHealthCheckWCAClient):

    def get_wca_client_type(self):
        return WCAClient

    def test_health_check_wca_token_error(self):
        self._do_test_health_check_wca_token_error()

    def test_health_check_wca_inference_error(self):
        self._do_test_health_check_wca_inference_error()

    def test_health_check_wca_inference_generic_error(self):
        self._do_test_health_check_wca_inference_generic_error()

    @override_settings(ENABLE_HEALTHCHECK_WCA=True)
    def test_health_check_wca_enable(self):
        self._do_test_health_check_wca_enable()

    @override_settings(ENABLE_HEALTHCHECK_WCA=False)
    def test_health_check_wca_disabled(self):
        self._do_test_health_check_wca_disabled()


@override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="wca-onprem")
class TestHealthCheckWCAOnPremClient(BaseTestHealthCheckWCAClient):

    def get_wca_client_type(self):
        return WCAOnPremClient

    def test_health_check_wca_onprem_token_error(self):
        self._do_test_health_check_wca_token_error()

    def test_health_check_wca_onprem_inference_error(self):
        self._do_test_health_check_wca_inference_error()

    def test_health_check_wca_onprem_inference_generic_error(self):
        self._do_test_health_check_wca_inference_generic_error()

    @override_settings(ENABLE_HEALTHCHECK_WCA=True)
    def test_health_check_wca_on_prem_enable(self):
        self._do_test_health_check_wca_enable()

    @override_settings(ENABLE_HEALTHCHECK_WCA=False)
    def test_health_check_wca_on_prem_disabled(self):
        self._do_test_health_check_wca_disabled()
