#!/usr/bin/env python3

from unittest.mock import patch
from django.test import TestCase
from django.test import Client
from django.apps import apps
from rest_framework.response import Response


class CompletionsTestCase(TestCase):
    def test_rate_limit(self):
        class DummyMeshClient:
            def infer(self, data, model_name=None):
                return Response(data)

        c = Client()
        with patch.object(apps.get_app_config('ai'), 'model_mesh_client', DummyMeshClient()):
            r = c.post('/api/ai/completions/', {"instances": []})
            self.assertTrue(r.status_code == 200)
            for _ in range(10):
                r = c.post('/api/ai/completions/', {"instances": []})
            self.assertTrue(r.status_code == 429)
