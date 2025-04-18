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
from textwrap import indent
from unittest.mock import Mock, patch

from django.test import TestCase

from ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines import (
    OllamaCompletionsPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import CompletionsParameters
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config


class TestOllama(TestCase):
    def setUp(self):
        super().setUp()
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
            "model_id": "a-model-id",
        }

    @patch("ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines.OllamaLLM")
    def test_infer(self, m_ollama):
        def final(_):
            return f"- name: Vache volante!\n{indent(self.expected_task_body, '  ')}"

        m_ollama.return_value = final
        config = mock_pipeline_config("ollama")
        model_client = OllamaCompletionsPipeline(config)
        response = model_client.invoke(
            CompletionsParameters.init(
                request=Mock(), model_input=self.model_input, model_id=config.model_id
            )
        )
        self.assertEqual(json.dumps(self.expected_response), json.dumps(response))
