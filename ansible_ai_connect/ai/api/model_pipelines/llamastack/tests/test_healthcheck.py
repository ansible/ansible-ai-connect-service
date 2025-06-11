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

import unittest
from unittest.mock import MagicMock, patch

from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.llamastack.configuration import (
    LlamaStackConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines import (
    LLAMA_STACK_PROVIDER_ID,
    LlamaStackMetaData,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ModelPipelineChatBot,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    ModelPipelineStreamingChatBot,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.ai.api.model_pipelines.tests.test_healthcheck import (
    TestModelPipelineHealthCheck,
)


@override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("llama-stack"))
class TestModelPipelineFactory(TestModelPipelineHealthCheck):

    def test_completions_healthcheck(self):
        self.assert_skipped(ModelPipelineCompletions, "nop")

    def test_content_match_healthcheck(self):
        self.assert_skipped(ModelPipelineContentMatch, "nop")

    def test_playbook_generation_healthcheck(self):
        self.assert_skipped(ModelPipelinePlaybookGeneration, "nop")

    def test_role_generation_healthcheck(self):
        self.assert_skipped(ModelPipelineRoleGeneration, "nop")

    def test_playbook_explanation_healthcheck(self):
        self.assert_skipped(ModelPipelinePlaybookExplanation, "nop")

    def test_role_explanation_healthcheck(self):
        self.assert_skipped(ModelPipelineRoleExplanation, "nop")

    def test_chatbot_healthcheck(self):
        self.assert_skipped(ModelPipelineChatBot, "nop")

    def test_streaming_chatbot_healthcheck(self):
        self.assert_skipped(ModelPipelineStreamingChatBot, "llama-stack")


class TestLlamaStackSelfTest(unittest.TestCase):
    def setUp(self):
        # Set up the configuration
        self.config = LlamaStackConfiguration(
            inference_url="https://localhost:8321/v1/providers",
            model_id="test-model",
            timeout=30,
            enable_health_check=True,
        )
        self.metadata = LlamaStackMetaData(config=self.config)

    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    def test_self_test_success(self, mock_client_class):
        """Test the self_test method when the provider health check returns OK status."""
        # Set up the mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        mock_provider = MagicMock()
        mock_provider.health = {"status": "OK"}
        mock_client_instance.providers.retrieve.return_value = mock_provider

        result = self.metadata.self_test()

        # Verify the result has expected items
        self.assertEqual(result.items["provider"], "llama-stack")
        self.assertEqual(result.items["models"], "ok")

        # Verify the mock was called correctly
        mock_client_class.assert_called_once_with(base_url=self.config.inference_url)
        mock_client_instance.providers.retrieve.assert_called_once_with(LLAMA_STACK_PROVIDER_ID)

    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    def test_self_test_failure_not_ok_status(self, mock_client_class):
        """Test the self_test method when the provider health check returns a non-OK status."""
        # Set up the mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        # Mock the provider.retrieve response with Not Implemented status
        mock_provider = MagicMock()
        mock_provider.health = {
            "status": "Not Implemented",
            "message": "Provider does not implement health check",
        }
        mock_client_instance.providers.retrieve.return_value = mock_provider

        result = self.metadata.self_test()

        # Verify the result has expected items
        self.assertEqual(result.items["provider"], "llama-stack")
        # For failure cases, we can check if the status is not 'ok'
        self.assertNotEqual(result.items.get("models"), "ok")

        # Verify the mock was called correctly
        mock_client_class.assert_called_once_with(base_url=self.config.inference_url)
        mock_client_instance.providers.retrieve.assert_called_once_with(LLAMA_STACK_PROVIDER_ID)

    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.logger")
    def test_self_test_failure_exception(self, mock_logger, mock_client_class):
        """Test the self_test method when an exception occurs during the health check."""
        # Set up the mock to raise an exception
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        mock_client_instance.providers.retrieve.side_effect = Exception("Connection error")

        result = self.metadata.self_test()

        # Verify the result has expected items
        self.assertEqual(result.items["provider"], "llama-stack")
        # For failure cases, we can check if the status is not 'ok'
        self.assertNotEqual(result.items.get("models"), "ok")

        mock_client_class.assert_called_once_with(base_url=self.config.inference_url)
        mock_client_instance.providers.retrieve.assert_called_once_with(LLAMA_STACK_PROVIDER_ID)
        # Verify that the exception was logged
        mock_logger.exception.assert_called_once_with("Connection error")


if __name__ == "__main__":
    unittest.main()
