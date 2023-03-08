import json
from http import HTTPStatus
from unittest import mock

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

    def test_liveness_probe(self):
        r = self.client.get(reverse('liveness_probe'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        self.assertEqual(r.content, b'ok')

    def test_health_check(self):
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        expected = {
            "Cache backend: default": "working",
            "DatabaseBackend": "working",
            "ModelServerHealthCheck": "working",
            "RedisHealthCheck": "working",
        }
        self.assertEqual(expected, json.loads(r.content))

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_health_check_error(self, _):
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.INTERNAL_SERVER_ERROR)
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
        r = self.client.get(reverse('health_check'))
        self.assertEqual(r.status_code, HTTPStatus.OK)
        expected = {
            "Cache backend: default": "working",
            "DatabaseBackend": "working",
            "ModelServerHealthCheck": "working",
            "RedisHealthCheck": "working",
        }
        self.assertEqual(expected, json.loads(r.content))
