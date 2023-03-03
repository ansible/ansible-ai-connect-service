import json
from unittest import mock

from django.test import override_settings
from requests import Response
from rest_framework.test import APITestCase


class TestHealthCheck(APITestCase):
    def mocked_requests_get(*args, **kwargs):
        r = Response()
        if len(args) > 0 and args[0].endswith('/ping'):
            r.status_code = 503
        else:
            r.status_code = 200
        return r

    def test_liveness_probe(self):
        r = self.client.get('/healthz/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'ok')

    def test_health_check(self):
        r = self.client.get('/healthz/status/')
        self.assertEqual(r.status_code, 200)
        expected = {
            "Cache backend: default": "working",
            "DatabaseBackend": "working",
            "ModelServerHealthCheck": "working",
            "RedisHealthCheck": "working",
        }
        self.assertEqual(expected, json.loads(r.content))

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_health_check_error(self, _):
        r = self.client.get('/healthz/status/')
        self.assertEqual(r.status_code, 500)
        expected = {
            "Cache backend: default": "working",
            "DatabaseBackend": "working",
            "ModelServerHealthCheck": "unavailable: An error occurred",
            "RedisHealthCheck": "working",
        }
        self.assertEqual(expected, json.loads(r.content))

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_health_check_grpc(self, _):
        r = self.client.get('/healthz/status/')
        self.assertEqual(r.status_code, 200)
        expected = {
            "Cache backend: default": "working",
            "DatabaseBackend": "working",
            "ModelServerHealthCheck": "working",
            "RedisHealthCheck": "working",
        }
        self.assertEqual(expected, json.loads(r.content))
