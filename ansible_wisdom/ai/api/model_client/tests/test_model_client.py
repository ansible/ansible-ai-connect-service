from unittest import TestCase

from ai.api.model_client.base import ModelMeshClient
from django.test import override_settings

timeout = 271828


class TestModelMeshClient(TestCase):
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=timeout)
    def test_set_inference_url(self):
        url = "https://example.com"
        c = ModelMeshClient(inference_url="https://somethingelse.com/")

        c.set_inference_url(url)

        self.assertEqual(c._inference_url, url)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TIMEOUT=timeout)
    def test_timeout(self):
        c = ModelMeshClient(inference_url="https://example.com")
        self.assertEqual(c.timeout, timeout)
