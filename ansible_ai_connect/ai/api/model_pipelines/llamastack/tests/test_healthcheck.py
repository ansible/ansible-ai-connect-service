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
from unittest import mock
from unittest.mock import MagicMock, patch

from django.test import override_settings
from health_check.exceptions import ServiceUnavailable

from ansible_ai_connect.ai.api.model_pipelines.llamastack.configuration import (
    LlamaStackConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines import (
    LLAMA_STACK_DB_PROVIDER,
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
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummaryException,
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

    @mock.patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    def test_streaming_chatbot_healthcheck(self, mock_client_class):
        """Test the health check for the streaming chatbot pipeline."""
        # Set up the mock client instance and its methods
        mock_client_instance = mock.MagicMock()
        mock_client_class.return_value = mock_client_instance
        # Mock the response from providers.retrieve
        mock_response = mock.MagicMock()
        mock_response.health = {"status": "OK"}
        mock_client_instance.providers.retrieve.return_value = mock_response

        self.assert_ok(ModelPipelineStreamingChatBot, "llama-stack")


class TestLlamaStackSelfTest(unittest.TestCase):
    """Unit tests for the LlamaStackMetaData self_test method."""

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
    def test_self_test_both_health_checks_pass(self, mock_client_class):
        """Test self_test when both index_health and llm_health return True."""
        # Set up the mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        # Mock successful responses for both providers
        mock_provider = MagicMock()
        mock_provider.health = {"status": "OK"}
        mock_client_instance.providers.retrieve.return_value = mock_provider

        result = self.metadata.self_test()

        # Verify the result has expected items and no exceptions
        self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_PROVIDER], "llama-stack")
        self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_MODELS], "ok")
        # Check that no exceptions were added to items
        exception_items = [
            k for k, v in result.items.items() if isinstance(v, HealthCheckSummaryException)
        ]
        self.assertEqual(len(exception_items), 0)

        # Verify both providers were checked
        self.assertEqual(mock_client_instance.providers.retrieve.call_count, 2)
        mock_client_instance.providers.retrieve.assert_any_call(LLAMA_STACK_DB_PROVIDER)
        mock_client_instance.providers.retrieve.assert_any_call(LLAMA_STACK_PROVIDER_ID)

    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    def test_self_test_index_health_fails(self, mock_client_class):
        """Test self_test when index_health fails but llm_health passes."""
        # Set up the mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        def mock_provider_retrieve(provider_id):
            mock_provider = MagicMock()
            if provider_id == LLAMA_STACK_DB_PROVIDER:
                # Index provider fails
                mock_provider.health = {"status": "Not Ready"}
            else:
                # LLM provider succeeds
                mock_provider.health = {"status": "OK"}
            return mock_provider

        mock_client_instance.providers.retrieve.side_effect = mock_provider_retrieve

        result = self.metadata.self_test()

        # Verify the result has expected items and one exception for index health
        self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_PROVIDER], "llama-stack")
        # The initial value is "ok" but gets overwritten by the exception
        self.assertIn(MODEL_MESH_HEALTH_CHECK_MODELS, result.items)

        # Check that an exception was added for the models health check
        models_item = result.items[MODEL_MESH_HEALTH_CHECK_MODELS]
        self.assertIsInstance(models_item, HealthCheckSummaryException)
        self.assertIsInstance(models_item.exception, ServiceUnavailable)
        self.assertIn(
            f"Provider {LLAMA_STACK_DB_PROVIDER} health status: Not ready",
            str(models_item.exception),
        )

    def test_self_test_llm_health_fails(self):
        """Test self_test when llm_health fails but index_health passes."""
        # Directly patch the health methods for precise control
        with (
            patch.object(self.metadata, "index_health", return_value=True),
            patch.object(self.metadata, "llm_health", return_value=False),
        ):
            result = self.metadata.self_test()

            # Verify the result has expected items and one exception for llm health
            self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_PROVIDER], "llama-stack")
            # The initial value is "ok" but gets overwritten by the exception
            self.assertIn(MODEL_MESH_HEALTH_CHECK_MODELS, result.items)

            # Check that an exception was added for the models health check
            models_item = result.items[MODEL_MESH_HEALTH_CHECK_MODELS]
            self.assertIsInstance(models_item, HealthCheckSummaryException)
            self.assertIsInstance(models_item.exception, ServiceUnavailable)
            self.assertIn(
                f"Provider {LLAMA_STACK_PROVIDER_ID} health status: Not ready",
                str(models_item.exception),
            )

    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    def test_self_test_both_health_checks_fail(self, mock_client_class):
        """Test self_test when both index_health and llm_health fail."""
        # Set up the mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        # Mock failed responses for both providers
        mock_provider = MagicMock()
        mock_provider.health = {"status": "Failed"}
        mock_client_instance.providers.retrieve.return_value = mock_provider

        result = self.metadata.self_test()

        # Verify the result has expected items and exception (second overwrites first)
        self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_PROVIDER], "llama-stack")
        # The initial value is "ok" but gets overwritten by the exception
        self.assertIn(MODEL_MESH_HEALTH_CHECK_MODELS, result.items)
        # Check that an exception was added for the models health check
        # Note: The second exception overwrites the first one due to the same key
        models_item = result.items[MODEL_MESH_HEALTH_CHECK_MODELS]
        self.assertIsInstance(models_item, HealthCheckSummaryException)
        self.assertIsInstance(models_item.exception, ServiceUnavailable)

    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.logger")
    def test_self_test_index_health_exception(self, mock_logger, mock_client_class):
        """Test self_test when index_health raises an exception."""
        # Set up the mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        def mock_provider_retrieve(provider_id):
            if provider_id == LLAMA_STACK_DB_PROVIDER:
                # Index provider raises exception
                raise Exception("Connection error")
            else:
                # LLM provider succeeds
                mock_provider = MagicMock()
                mock_provider.health = {"status": "OK"}
                return mock_provider

        mock_client_instance.providers.retrieve.side_effect = mock_provider_retrieve

        result = self.metadata.self_test()

        # Verify the result has expected items and one exception for index health
        self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_PROVIDER], "llama-stack")
        # The initial value is "ok" but gets overwritten by the exception
        self.assertIn(MODEL_MESH_HEALTH_CHECK_MODELS, result.items)

        # Check that an exception was added for the models health check
        models_item = result.items[MODEL_MESH_HEALTH_CHECK_MODELS]
        self.assertIsInstance(models_item, HealthCheckSummaryException)

        # Verify that the exception was logged
        mock_logger.exception.assert_called_with("Connection error")

    def test_self_test_llm_health_exception(self):
        """Test self_test when llm_health raises an exception."""
        # Directly patch the health methods for precise control
        with (
            patch.object(self.metadata, "index_health", return_value=True),
            patch.object(self.metadata, "llm_health", return_value=False),
        ):
            result = self.metadata.self_test()

            # Verify the result has expected items and one exception for llm health
            self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_PROVIDER], "llama-stack")
            # The initial value is "ok" but gets overwritten by the exception
            self.assertIn(MODEL_MESH_HEALTH_CHECK_MODELS, result.items)

            # Check that an exception was added for the models health check
            models_item = result.items[MODEL_MESH_HEALTH_CHECK_MODELS]
            self.assertIsInstance(models_item, HealthCheckSummaryException)

    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.LlamaStackClient")
    @patch("ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.logger")
    def test_self_test_both_health_checks_exception(self, mock_logger, mock_client_class):
        """Test self_test when both index_health and llm_health raise exceptions."""
        # Set up the mock
        mock_client_instance = MagicMock()
        mock_client_class.return_value = mock_client_instance

        # Both providers raise exceptions
        mock_client_instance.providers.retrieve.side_effect = Exception("Service unavailable")

        result = self.metadata.self_test()

        # Verify the result has expected items and one exception (second overwrites first)
        self.assertEqual(result.items[MODEL_MESH_HEALTH_CHECK_PROVIDER], "llama-stack")
        # The initial value is "ok" but gets overwritten by the exception
        self.assertIn(MODEL_MESH_HEALTH_CHECK_MODELS, result.items)

        # Check that an exception was added for the models health check
        models_item = result.items[MODEL_MESH_HEALTH_CHECK_MODELS]
        self.assertIsInstance(models_item, HealthCheckSummaryException)

        # Verify both calls were made and exceptions logged
        self.assertEqual(mock_client_instance.providers.retrieve.call_count, 2)
        self.assertEqual(mock_logger.exception.call_count, 2)
        mock_logger.exception.assert_called_with("Service unavailable")


if __name__ == "__main__":
    unittest.main()
