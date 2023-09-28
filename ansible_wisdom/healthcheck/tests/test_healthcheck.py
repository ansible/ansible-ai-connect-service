import json
import time
from http import HTTPStatus
from unittest import mock
from unittest.mock import Mock, patch

import healthcheck.views as healthcheck_views
from ai.api.aws.wca_secret_manager import WcaSecretManager, WcaSecretManagerError
from ai.feature_flags import FeatureFlags
from django.apps import apps
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from requests import Response
from rest_framework.test import APITestCase


class TestHealthCheck(APITestCase):
    def setUp(self):
        super().setUp()
        self.secret_manager_patcher = patch.object(
            apps.get_app_config('ai'), '_wca_secret_manager', spec=WcaSecretManager
        )
        self.mock_secret_manager = self.secret_manager_patcher.start()
        self.mock_secret_manager.get_secret.return_value = None

    def tearDown(self):
        self.secret_manager_patcher.stop()

    def mocked_requests_succeed(*args, **kwargs):
        r = Response()
        r.status_code = HTTPStatus.OK
        return r

    def mocked_requests_http_fail(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith('/ping'):
            r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        else:
            r.status_code = HTTPStatus.OK
        return r

    def mocked_requests_grpc_fail(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith('/oauth/healthz'):
            r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        else:
            r.status_code = HTTPStatus.OK
        return r

    def test_liveness_probe(self):
        r = self.client.get(reverse('liveness_probe'), format='json')
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertJSONEqual(r.content, {"status": "ok"})

    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="mock")
    def test_health_check(self):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assertEqual('ok', data['status'])
        timestamp = data['timestamp']
        self.assertIsNotNone(timestamp)
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertIsNotNone(data['model_name'])
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server', 'aws-secret-manager'])
            self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

        time.sleep(1)

        # Make sure the cached data is returned in the second call after 1 sec
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assertEqual(timestamp, data['timestamp'])

    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="http")
    @mock.patch('requests.get', side_effect=mocked_requests_http_fail)
    def test_health_check_http_error(self, _):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        data = json.loads(r.content)
        self.assertEqual('error', data['status'])
        timestamp = data['timestamp']
        self.assertIsNotNone(timestamp)
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertIsNotNone(data['model_name'])
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server', 'aws-secret-manager'])
            if dependency['name'] == 'model-server':
                self.assertTrue(dependency['status'].startswith('unavailable:'))
            else:
                self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)
        print(data['timestamp'])

        time.sleep(1)

        # Make sure the cached data is returned in the second call after 1 sec
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        data = json.loads(r.content)
        self.assertEqual(timestamp, data['timestamp'])
        print(data['timestamp'])

    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    @mock.patch('requests.get', side_effect=mocked_requests_succeed)
    def test_health_check_grpc(self, _):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assertEqual('ok', data['status'])
        self.assertIsNotNone(data['timestamp'])
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertIsNotNone(data['model_name'])
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server', 'aws-secret-manager'])
            self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    @mock.patch('requests.get', side_effect=mocked_requests_grpc_fail)
    def test_health_check_grpc_error(self, _):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        data = json.loads(r.content)
        self.assertEqual('error', data['status'])
        self.assertIsNotNone(data['timestamp'])
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertIsNotNone(data['model_name'])
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server', 'aws-secret-manager'])
            if dependency['name'] == 'model-server':
                self.assertTrue(dependency['status'].startswith('unavailable:'))
            else:
                self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="mock")
    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    @mock.patch('requests.get', side_effect=mocked_requests_succeed)
    def test_health_check_mock(self, _):
        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assertEqual('ok', data['status'])
        self.assertIsNotNone(data['timestamp'])
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertIsNotNone(data['model_name'])
        self.assertEqual(data['model_name'], settings.ANSIBLE_AI_MODEL_NAME)
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server', 'aws-secret-manager'])
            self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="mock")
    @override_settings(LAUNCHDARKLY_SDK_KEY='dummy_key')
    @mock.patch('requests.get', side_effect=mocked_requests_succeed)
    @mock.patch('healthcheck.views.get_feature_flags')
    @mock.patch('ldclient.get')
    def test_health_check_mock_with_launchdarkly(self, ldclient_get, get_feature_flags, _):
        class DummyClient:
            def variation(name, *args):
                return 'server:port:model_name:index'

        ldclient_get.return_value = DummyClient()
        get_feature_flags.return_value = FeatureFlags()

        cache.clear()
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assertEqual('ok', data['status'])
        self.assertIsNotNone(data['timestamp'])
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertIsNotNone(data['model_name'])
        self.assertEqual(data['model_name'], 'model_name')
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server', 'aws-secret-manager'])
            self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

    def test_get_feature_flags(self):
        healthcheck_views.feature_flags = "return this"
        self.assertEqual(healthcheck_views.get_feature_flags(), "return this")

    @override_settings(LAUNCHDARKLY_SDK_KEY=None)
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="mock")
    def test_health_check_aws_secret_manager_error(self):
        cache.clear()
        self.mock_secret_manager.get_secret = Mock(side_effect=WcaSecretManagerError)

        r = self.client.get(reverse('health_check'))

        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
        data = json.loads(r.content)
        self.assertEqual('error', data['status'])
        self.assertIsNotNone(data['timestamp'])
        self.assertIsNotNone(data['version'])
        self.assertIsNotNone(data['git_commit'])
        self.assertIsNotNone(data['model_name'])
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server', 'aws-secret-manager'])
            if dependency['name'] == 'aws-secret-manager':
                self.assertTrue(dependency['status'].startswith('unavailable:'))
            else:
                self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)
