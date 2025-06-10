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
import unittest
from unittest.mock import MagicMock, patch

from requests.exceptions import ConnectionError, HTTPError, Timeout

from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.llamastack.configuration import LlamaStackConfiguration
from ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines import (
    LlamaStackChatBotPipeline,
    LlamaStackStreamingChatBotPipeline,
)
from ansible_ai_connect.healthcheck.backends import HealthCheckSummaryException
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


class TestLlamaStackHealthCheck(unittest.TestCase):
    """Test cases for LlamaStack pipelines health check functionality."""

    def setUp(self):
        """Set up test configuration."""
        self.config = LlamaStackConfiguration(
            inference_url="https://llama-stack-api.example.com",
            model_id="test-model",
            timeout=30,
            enable_health_check=True,
        )

        # Sample successful health check response
        self.success_response = json.dumps({
            "data": [
                {
                    "api": "inference",
                    "provider_id": "vllm-inference",
                    "provider_type": "remote::vllm",
                    "config": {
                        "url": "https://llm-dev-wisdom-model-staging.apps.stage2-west.v2dz.p1.openshiftapps.com/v1",
                        "max_tokens": "4096",
                        "api_token": "********",
                        "tls_verify": "true"
                    },
                    "health": {
                        "status": "OK"
                    }
                }
            ]
        })

        # Sample failed health check response
        self.failed_response = json.dumps({
            "data": [
                {
                    "api": "inference",
                    "provider_id": "vllm-inference",
                    "provider_type": "remote::vllm",
                    "config": {
                        "url": "https://llm-dev-wisdom-model-staging.apps.stage2-west.v2dz.p1.openshiftapps.com/v1",
                        "max_tokens": "4096",
                        "api_token": "********",
                        "tls_verify": "true"
                    },
                    "health": {
                        "status": "Not Implemented",
                        "message": "Provider does not implement health check"
                    }
                }
            ]
        })

    @patch('requests.get')
    def test_llamastack_chatbot_pipeline_health_check_success(self, mock_get):
        """Test successful health check for LlamaStackChatBotPipeline."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json.loads(self.success_response)
        mock_get.return_value = mock_response

        # Create pipeline and run health check
        pipeline = LlamaStackChatBotPipeline(self.config)
        summary = pipeline.self_test()

        # Verify results
        self.assertEqual(summary.items["provider"], "llama-stack")
        self.assertEqual(summary.items["models"], "ok")
        # Check that no exceptions are in the summary items
        self.assertFalse(any(isinstance(item, HealthCheckSummaryException) for item in summary.items.values()))

        # Verify the correct URL was called
        mock_get.assert_called_once_with(
            self.config.inference_url + "/v1/providers",
            headers={"Content-Type": "application/json"},
            timeout=30
        )

    @patch('requests.get')
    def test_llamastack_chatbot_pipeline_health_check_failure(self, mock_get):
        """Test failed health check for LlamaStackChatBotPipeline."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json.loads(self.failed_response)
        mock_get.return_value = mock_response

        # Create pipeline and run health check
        pipeline = LlamaStackChatBotPipeline(self.config)
        summary = pipeline.self_test()

        # Verify results
        self.assertEqual(summary.items["provider"], "llama-stack")
        # Check that models key has an exception
        self.assertIn("models", summary.items)
        self.assertIsInstance(summary.items["models"], HealthCheckSummaryException)

        # Verify the correct URL was called
        mock_get.assert_called_once_with(
            self.config.inference_url + "/v1/providers",
            headers={"Content-Type": "application/json"},
            timeout=30
        )

    @patch('requests.get')
    def test_llamastack_chatbot_pipeline_provider_not_found(self, mock_get):
        """Test health check when provider is not found."""
        # Setup mock response with no matching provider
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "api": "inference",
                    "provider_id": "different-provider",
                    "provider_type": "remote::other",
                    "health": {"status": "OK"}
                }
            ]
        }
        mock_get.return_value = mock_response

        # Create pipeline and run health check
        pipeline = LlamaStackChatBotPipeline(self.config)
        summary = pipeline.self_test()

        # Verify results
        self.assertEqual(summary.items["provider"], "llama-stack")
        # Check that models key has an exception
        self.assertIn("models", summary.items)
        self.assertIsInstance(summary.items["models"], HealthCheckSummaryException)

    @patch('requests.get')
    def test_llamastack_chatbot_pipeline_connection_error(self, mock_get):
        """Test health check with connection error."""
        # Setup mock to raise exception
        mock_get.side_effect = ConnectionError("Failed to connect")

        # Create pipeline and run health check
        pipeline = LlamaStackChatBotPipeline(self.config)
        summary = pipeline.self_test()

        # Verify results
        self.assertEqual(summary.items["provider"], "llama-stack")
        # Check that models key has an exception
        self.assertIn("models", summary.items)
        self.assertIsInstance(summary.items["models"], HealthCheckSummaryException)

    @patch('requests.get')
    def test_llamastack_chatbot_pipeline_timeout_error(self, mock_get):
        """Test health check with timeout error."""
        # Setup mock to raise exception
        mock_get.side_effect = Timeout("Request timed out")

        # Create pipeline and run health check
        pipeline = LlamaStackChatBotPipeline(self.config)
        summary = pipeline.self_test()

        # Verify results
        self.assertEqual(summary.items["provider"], "llama-stack")
        # Check that models key has an exception
        self.assertIn("models", summary.items)
        self.assertIsInstance(summary.items["models"], HealthCheckSummaryException)

    @patch('requests.get')
    def test_llamastack_chatbot_pipeline_http_error(self, mock_get):
        """Test health check with HTTP error."""
        # Setup mock to raise exception
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = HTTPError("404 Not Found")
        mock_get.return_value = mock_response

        # Create pipeline and run health check
        pipeline = LlamaStackChatBotPipeline(self.config)
        summary = pipeline.self_test()

        # Verify results
        self.assertEqual(summary.items["provider"], "llama-stack")
        # Check that models key has an exception
        self.assertIn("models", summary.items)
        self.assertIsInstance(summary.items["models"], HealthCheckSummaryException)

    @patch('requests.get')
    def test_llamastack_streaming_chatbot_pipeline_health_check_success(self, mock_get):
        """Test successful health check for LlamaStackStreamingChatBotPipeline."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json.loads(self.success_response)
        mock_get.return_value = mock_response

        # Create pipeline with mocked AsyncLlamaStackClient and AsyncAgent
        with patch('ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.AsyncLlamaStackClient'), \
             patch('ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.AsyncAgent'):
            pipeline = LlamaStackStreamingChatBotPipeline(self.config)
            summary = pipeline.self_test()

            # Verify results
            self.assertEqual(summary.items["provider"], "llama-stack")
            self.assertEqual(summary.items["models"], "ok")
            # Check that no exceptions are in the summary items
            self.assertFalse(any(isinstance(item, HealthCheckSummaryException) for item in summary.items.values()))

            # Verify the correct URL was called
            mock_get.assert_called_once_with(
                self.config.inference_url + "/v1/providers",
                headers={"Content-Type": "application/json"},
                timeout=30
            )

    @patch('requests.get')
    def test_llamastack_streaming_chatbot_pipeline_health_check_failure(self, mock_get):
        """Test failed health check for LlamaStackStreamingChatBotPipeline."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = json.loads(self.failed_response)
        mock_get.return_value = mock_response

        # Create pipeline with mocked AsyncLlamaStackClient and AsyncAgent
        with patch('ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.AsyncLlamaStackClient'), \
             patch('ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines.AsyncAgent'):
            pipeline = LlamaStackStreamingChatBotPipeline(self.config)
            summary = pipeline.self_test()

            # Verify results
            self.assertEqual(summary.items["provider"], "llama-stack")
            # Check that models key has an exception
            self.assertIn("models", summary.items)
            self.assertIsInstance(summary.items["models"], HealthCheckSummaryException)

            # Verify the correct URL was called
            mock_get.assert_called_once_with(
                self.config.inference_url + "/v1/providers",
                headers={"Content-Type": "application/json"},
                timeout=30
            )
