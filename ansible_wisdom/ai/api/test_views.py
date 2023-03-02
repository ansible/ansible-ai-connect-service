#!/usr/bin/env python3

from unittest.mock import patch

from django.apps import apps
from django.test import Client, TestCase
from rest_framework.response import Response


class DummyMeshClient:
    def __init__(self, test, payload):
        self.test = test
        self.expects = {
            "instances": [
                {
                    "prompt": payload.get("prompt"),
                    "context": payload.get("context"),
                    "userId": payload.get("userId"),
                    "suggestionId": payload.get("suggestionId"),
                }
            ]
        }

    def infer(self, data, model_name=None):
        self.test.assertEqual(data, self.expects)
        return Response(data)


class CompletionsTestCase(TestCase):
    def test_full_payload(self):
        c = Client()
        payload = {
            "prompt": "- name: install openshift\n",
            "context": "",
            "userId": "bixler",
            "suggestionId": "105625",
        }

        with patch.object(
            apps.get_app_config('ai'), 'model_mesh_client', DummyMeshClient(self, payload)
        ):
            r = c.post('/api/ai/completions/', payload)
            self.assertEqual(r.status_code, 200)

    def test_rate_limit(self):
        c = Client()
        payload = {
            "prompt": "- name: install rhel\n",
        }
        with patch.object(
            apps.get_app_config('ai'), 'model_mesh_client', DummyMeshClient(self, payload)
        ):
            r = c.post('/api/ai/completions/', payload)
            self.assertEqual(r.status_code, 200)
            for _ in range(10):
                r = c.post('/api/ai/completions/', payload)
            self.assertEqual(r.status_code, 429)
