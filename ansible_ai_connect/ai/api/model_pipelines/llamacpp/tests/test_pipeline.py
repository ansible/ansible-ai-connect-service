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
from django.test import TestCase
from requests.exceptions import ReadTimeout
from responses import matchers

from ansible_ai_connect.ai.api.model_pipelines.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.model_pipelines.llamacpp.pipelines import (
    LlamaCppCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import CompletionsParameters
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config


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
            "model_id": "a-model-id",
        }

    @responses.activate
    def test_infer(self):
        config = mock_pipeline_config("llamacpp")
        model_client = LlamaCppCompletionsPipeline(config)
        responses.post(
            self.prediction_url,
            match=[
                matchers.header_matcher({"Content-Type": "application/json"}),
                matchers.json_params_matcher(
                    {
                        "prompt": f'{self.model_input["instances"][0]["prompt"]}\n',
                        "model": config.model_id,
                    },
                    strict_match=False,
                ),
            ],
            json={
                "content": self.expected_task_body,
                "model": config.model_id,
            },
        )

        response = model_client.invoke(
            CompletionsParameters.init(request=Mock(), model_input=self.model_input)
        )
        self.assertEqual(json.dumps(self.expected_response), json.dumps(response))

    @responses.activate
    def test_infer_override(self):
        model = "multivac"
        self.expected_response["model_id"] = model

        model_client = LlamaCppCompletionsPipeline(mock_pipeline_config("llamacpp"))
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

        response = model_client.invoke(
            CompletionsParameters.init(request=Mock(), model_input=self.model_input, model_id=model)
        )
        self.assertEqual(json.dumps(self.expected_response), json.dumps(response))

    @responses.activate
    def test_infer_timeout(self):
        model_client = LlamaCppCompletionsPipeline(mock_pipeline_config("llamacpp"))
        model_client.session.post = Mock(side_effect=ReadTimeout())
        with self.assertRaises(ModelTimeoutError):
            model_client.invoke(
                CompletionsParameters.init(request=Mock(), model_input=self.model_input)
            )
