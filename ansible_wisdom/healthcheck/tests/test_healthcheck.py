import json
import time
from http import HTTPStatus
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from requests import Response
from rest_framework.test import APITestCase


class TestHealthCheck(APITestCase):
    def mocked_requests_get(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith('/ping'):
            r.status_code = HTTPStatus.SERVICE_UNAVAILABLE
        else:
            r.status_code = HTTPStatus.OK
        return r

    def mocked_requests_get_grpc(*args, **kwargs):
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
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server'])
            self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

        time.sleep(1)

        # Make sure the cached data is returned in the second call after 1 sec
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        data = json.loads(r.content)
        self.assertEqual(timestamp, data['timestamp'])

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_health_check_error(self, _):
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
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server'])
            if dependency['name'] == 'model-server':
                self.assertTrue(dependency['status'].startswith('unavailable:'))
            else:
                self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    @mock.patch('requests.get', side_effect=mocked_requests_get)
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
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server'])
            self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    @mock.patch('requests.get', side_effect=mocked_requests_get_grpc)
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
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server'])
            if dependency['name'] == 'model-server':
                self.assertTrue(dependency['status'].startswith('unavailable:'))
            else:
                self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="mock")
    @mock.patch('requests.get', side_effect=mocked_requests_get)
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
        dependencies = data.get('dependencies', [])
        self.assertEqual(3, len(dependencies))
        for dependency in dependencies:
            self.assertIn(dependency['name'], ['cache', 'db', 'model-server'])
            self.assertEqual('ok', dependency['status'])
            self.assertGreaterEqual(dependency['time_taken'], 0)
