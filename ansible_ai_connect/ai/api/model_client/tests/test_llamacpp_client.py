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
from unittest.mock import Mock

import responses
from django.test import TestCase, override_settings
from requests.exceptions import ReadTimeout
from responses import matchers

from ansible_ai_connect.ai.api.model_client.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.model_client.llamacpp_client import LlamaCPPClient


class TestLlamaCPPClient(TestCase):
    def setUp(self):
        super().setUp()
        self.inference_url = "http://localhost"
        self.prediction_url = f"{self.inference_url}/completion"
        self.model_input = {
            "instances": [
                {
                    "context": "",
                    "prompt": "- name: hey siri, return a task that installs ffmpeg",
                }
            ]
        }

        self.expected_task_body = "  ansible.builtin.debug:\n  msg: something went wrong"
        self.expected_response = {
            "predictions": [self.expected_task_body],
            "model_id": "test",
        }

    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_ID="test")
    @responses.activate
    def test_infer(self):
        model_client = LlamaCPPClient(inference_url=self.inference_url)
        responses.post(
            self.prediction_url,
            match=[
                matchers.header_matcher({"Content-Type": "application/json"}),
                matchers.json_params_matcher(
                    {
                        "prompt": f'{self.model_input["instances"][0]["prompt"]}\n',
                        "model": "test",
                    },
                    strict_match=False,
                ),
            ],
            json={
                "content": self.expected_task_body,
                "model": "test",
            },
        )

        response = model_client.infer(None, self.model_input)
        self.assertEqual(json.dumps(self.expected_response), json.dumps(response))

    @responses.activate
    def test_infer_override(self):
        model = "multivac"
        self.expected_response["model_id"] = model

        model_client = LlamaCPPClient(inference_url=self.inference_url)
        responses.post(
            self.prediction_url,
            match=[
                matchers.header_matcher({"Content-Type": "application/json"}),
                matchers.json_params_matcher(
                    {
                        "prompt": f'{self.model_input["instances"][0]["prompt"]}\n',
                        "model": model,
                    },
                    strict_match=False,
                ),
            ],
            json={
                "content": self.expected_task_body,
                "model": model,
            },
        )

        response = model_client.infer(None, self.model_input, model_id=model)
        self.assertEqual(json.dumps(self.expected_response), json.dumps(response))

    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_ID="test")
    @responses.activate
    def test_infer_timeout(self):
        model_client = LlamaCPPClient(inference_url=self.inference_url)
        model_client.session.post = Mock(side_effect=ReadTimeout())
        with self.assertRaises(ModelTimeoutError):
            model_client.infer(None, self.model_input)
