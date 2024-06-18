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

from unittest import TestCase

from django.test import override_settings

from ansible_ai_connect.ai.api.model_client.base import ModelMeshClient

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
        self.assertEqual(c.timeout(1), timeout)

    def test_not_implemented(self):
        c = ModelMeshClient(inference_url="https://example.com")

        with self.assertRaises(NotImplementedError):
            c.get_chat_model("a")
        with self.assertRaises(NotImplementedError):
            c.generate_playbook(None, "a")
        with self.assertRaises(NotImplementedError):
            c.explain_playbook(None, "a")
