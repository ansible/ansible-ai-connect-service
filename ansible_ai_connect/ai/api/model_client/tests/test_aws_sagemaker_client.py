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

from ansible_ai_connect.ai.api.model_client.aws_sagemaker_client import AWSSageMakerClient


class TestAWSSageMakerClient(TestCase):
    def setUp(self):
        super().setUp()
        self.inference_url = "endpoint-1"
        self.model_input = {
            "instances": [
                {
                    "context": "",
                    "prompt": "- name: hey siri, return a task that installs ffmpeg",
                }
            ]
        }

    @override_settings(ANSIBLE_AI_MODEL_MESH_MODEL_ID="test")
    @responses.activate
    def test_infer(self):
        expected_task_body = "  ansible.builtin.debug:\n  msg: something went wrong"
        expected_response = {
            "predictions": [expected_task_body],
            "model_id": "test",
        }
        model_client = AWSSageMakerClient(inference_url=self.inference_url)
        """
                response = MockResponse(
                    json=expected_response,
                    status_code=200,
                )
                model_client.session.post = Mock(return_value=response)
        """
        responses.post(
            self.inference_url,
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
                "content": expected_task_body,
                "model": "test",
            },
        )

        response = model_client.infer(self.model_input)
        self.assertEqual(json.dumps(expected_response), json.dumps(response))
