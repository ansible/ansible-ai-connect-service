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

import responses
from django.test import TestCase, override_settings
from responses import matchers

from ansible_ai_connect.ai.api.model_client.bam_client import BAMClient


class TestBam(TestCase):
    def setUp(self):
        super().setUp()
        self.inference_url = "http://localhost"
        self.prediction_url = f"{self.inference_url}/v2/text/chat?version=2024-01-10"
        self.model_input = {
            "instances": [
                {
                    "context": "",
                    "prompt": "- name: hey siri, return a task that installs ffmpeg",
                }
            ]
        }

        self.expected_task_body = "ansible.builtin.debug:\n  msg: something went wrong"
        self.expected_response = {
            "predictions": [self.expected_task_body],
            "model_id": "test",
        }

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_KEY="my_key")
    @override_settings(ANSIBLE_AI_MODEL_NAME="test")
    @responses.activate
    def test_infer(self):
        model = "test"
        model_client = BAMClient(self.inference_url)
        responses.post(
            self.prediction_url,
            match=[
                matchers.header_matcher({"Content-Type": "application/json"}),
                matchers.json_params_matcher(
                    {
                        "model_id": "test",
                        "messages": [
                            {
                                "content": (
                                    "You are an Ansible expert. Return a single task that "
                                    "best completes the partial playbook. Return only the "
                                    "task as YAML. Do not return multiple tasks. Do not explain "
                                    "your response. Do not include the prompt in your response."
                                ),
                                "role": "system",
                            },
                            {
                                "content": "- name: hey siri, return a task that installs ffmpeg\n",
                                "role": "user",
                            },
                        ],
                        "parameters": {
                            "temperature": 0.1,
                            "decoding_method": "greedy",
                            "repetition_penalty": 1.05,
                            "min_new_tokens": 1,
                            "max_new_tokens": 2048,
                        },
                    },
                    strict_match=False,
                ),
            ],
            json={
                "results": [
                    {"generated_text": "ansible.builtin.debug:\n  msg: something went wrong"}
                ],
            },
        )

        response = model_client.infer(self.model_input, model_id=model)
        self.assertEqual(json.dumps(self.expected_response), json.dumps(response))
