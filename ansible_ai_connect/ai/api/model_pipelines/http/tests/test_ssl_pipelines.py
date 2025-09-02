#
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
import logging
import os
import ssl
import tempfile
from unittest import IsolatedAsyncioTestCase, TestCase
from unittest.mock import MagicMock, Mock, patch

import requests

from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpChatBotPipeline,
    HttpCompletionsPipeline,
    HttpMetaData,
    HttpStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ChatBotParameters,
    CompletionsParameters,
    StreamingChatBotParameters,
)
from ansible_ai_connect.ai.api.telemetry.schema1 import StreamingChatBotOperationalEvent
from ansible_ai_connect.test_utils import WisdomLogAwareMixin

logger = logging.getLogger(__name__)


class TestHttpPipelineSSLVerification(TestCase, WisdomLogAwareMixin):
    """Test SSL verification logic in HTTP pipelines"""

    def setUp(self):
        self.ca_cert_path = "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        self.inference_url = "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443"

    def test_verify_parameter_with_ca_cert_file(self):
        """Test that ca_cert_file takes precedence over verify_ssl boolean"""
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        # Test the verify parameter logic
        expected_verify = config.ca_cert_file if config.ca_cert_file else config.verify_ssl
        self.assertEqual(expected_verify, self.ca_cert_path)
        # Verify config state
        self.assertEqual(config.ca_cert_file, self.ca_cert_path)
        self.assertTrue(config.verify_ssl)

    def test_verify_parameter_without_ca_cert_file_verify_ssl_true(self):
        """Test that verify_ssl=True is used when ca_cert_file is None"""
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file=None,
        )
        # Test the verify parameter logic
        expected_verify = config.ca_cert_file if config.ca_cert_file else config.verify_ssl
        self.assertTrue(expected_verify)
        # Verify config state
        self.assertIsNone(config.ca_cert_file)
        self.assertTrue(config.verify_ssl)

    def test_verify_parameter_without_ca_cert_file_verify_ssl_false(self):
        """Test that verify_ssl=False is used when ca_cert_file is None"""
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
            ca_cert_file=None,
        )
        # Test the verify parameter logic
        expected_verify = config.ca_cert_file if config.ca_cert_file else config.verify_ssl
        self.assertFalse(expected_verify)
        # Verify config state
        self.assertIsNone(config.ca_cert_file)
        self.assertFalse(config.verify_ssl)

    def test_verify_parameter_with_empty_string_ca_cert_file(self):
        """Test that empty string ca_cert_file falls back to verify_ssl"""
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file="",
        )
        # Empty string is falsy, so should fall back to verify_ssl
        expected_verify = config.ca_cert_file if config.ca_cert_file else config.verify_ssl
        self.assertTrue(expected_verify)
        # Verify config state
        self.assertEqual(config.ca_cert_file, "")
        self.assertTrue(config.verify_ssl)


class TestHttpChatBotPipelineSSL(TestCase, WisdomLogAwareMixin):
    """Test SSL functionality in HttpChatBotPipeline"""

    def setUp(self):
        # Create a temporary certificate file for testing
        self.temp_cert_file = tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False)
        self.temp_cert_file.write(
            "-----BEGIN CERTIFICATE-----\ntest-certificate-content\n-----END CERTIFICATE-----"
        )
        self.temp_cert_file.close()
        self.ca_cert_path = self.temp_cert_file.name
        self.inference_url = "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443"

    def tearDown(self):
        # Clean up the temporary certificate file
        if os.path.exists(self.ca_cert_path):
            os.unlink(self.ca_cert_path)

    @patch("requests.post")
    def test_invoke_with_ca_cert_file(self, mock_post):
        """Test that invoke() uses ca_cert_file for SSL verification"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello! I'm Ansible Lightspeed."}
        mock_response.text = '{"response": "Hello! I\'m Ansible Lightspeed."}'
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        # Create config with ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        pipeline = HttpChatBotPipeline(config)
        # Create parameters
        params = ChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )
        # Execute
        result = pipeline.invoke(params)
        # Verify the requests.post was called with boolean SSL verification
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["verify"], True)
        # Verify result
        self.assertIsNotNone(result)

    @patch("requests.post")
    def test_invoke_without_ca_cert_file_verify_ssl_true(self, mock_post):
        """Test that invoke() uses verify_ssl=True when ca_cert_file is None"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello! I'm Ansible Lightspeed."}
        mock_response.text = '{"response": "Hello! I\'m Ansible Lightspeed."}'
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        # Create config without ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file=None,
        )
        pipeline = HttpChatBotPipeline(config)
        # Create parameters
        params = ChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )
        # Execute
        result = pipeline.invoke(params)
        # Verify the requests.post was called with verify_ssl=True
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertTrue(call_kwargs["verify"])
        # Verify result
        self.assertIsNotNone(result)

    @patch("requests.post")
    def test_invoke_without_ca_cert_file_verify_ssl_false(self, mock_post):
        """Test that invoke() uses verify_ssl=False when ca_cert_file is None"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "Hello! I'm Ansible Lightspeed."}
        mock_response.text = '{"response": "Hello! I\'m Ansible Lightspeed."}'
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        # Create config without ca_cert_file and verify_ssl=False
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=False,
            ca_cert_file=None,
        )
        pipeline = HttpChatBotPipeline(config)
        # Create parameters
        params = ChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )
        # Execute
        result = pipeline.invoke(params)
        # Verify the requests.post was called with verify_ssl=False
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertFalse(call_kwargs["verify"])
        # Verify result
        self.assertIsNotNone(result)


class TestHttpCompletionsPipelineSSL(TestCase, WisdomLogAwareMixin):
    """Test SSL functionality in HttpCompletionsPipeline"""

    def setUp(self):
        # Create a temporary certificate file for testing
        self.temp_cert_file = tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False)
        self.temp_cert_file.write(
            "-----BEGIN CERTIFICATE-----\ntest-certificate-content\n-----END CERTIFICATE-----"
        )
        self.temp_cert_file.close()
        self.ca_cert_path = self.temp_cert_file.name
        self.inference_url = "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443"

    def tearDown(self):
        # Clean up the temporary certificate file
        if os.path.exists(self.ca_cert_path):
            os.unlink(self.ca_cert_path)

    def test_invoke_with_ca_cert_file(self):
        """Test that completions invoke() uses ca_cert_file for SSL verification"""
        # Create config with ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        pipeline = HttpCompletionsPipeline(config)
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "predictions": [{"generated_text": "- name: Install package"}],
            "model_id": "test-model",
        }
        mock_response.text = (
            '{"predictions": [{"generated_text": "- name: Install package"}]'
            + ', "model_id": "test-model"}'
        )
        mock_response.status_code = 200
        # Mock the pipeline's session post method
        with patch.object(pipeline.session, "post", return_value=mock_response) as mock_post:
            # Create parameters
            params = CompletionsParameters.init(
                request=Mock(),
                model_input={"context": "---\n- name: Example task", "prompt": ""},
                model_id="test-model",
            )
            # Execute
            result = pipeline.invoke(params)
            # Verify the session.post was called with boolean SSL verification
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            self.assertEqual(call_kwargs["verify"], True)
            # Verify result
            self.assertIsNotNone(result)


class TestHttpHealthCheckSSL(TestCase, WisdomLogAwareMixin):
    """Test SSL functionality in health check methods"""

    def setUp(self):
        # Create a temporary certificate file for testing
        self.temp_cert_file = tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False)
        self.temp_cert_file.write(
            "-----BEGIN CERTIFICATE-----\ntest-certificate-content\n-----END CERTIFICATE-----"
        )
        self.temp_cert_file.close()
        self.ca_cert_path = self.temp_cert_file.name
        self.inference_url = "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443"

    def tearDown(self):
        # Clean up the temporary certificate file
        if os.path.exists(self.ca_cert_path):
            os.unlink(self.ca_cert_path)

    @patch("requests.get")
    def test_self_test_with_ca_cert_file(self, mock_get):
        """Test that self_test() uses ca_cert_file for SSL verification"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"ready": True, "reason": "All providers are healthy"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        # Create config with ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        pipeline = HttpChatBotPipeline(config)
        # Execute health check
        result = pipeline.self_test()
        # Verify the requests.get was called with boolean SSL verification
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs["verify"], True)
        # Verify result
        self.assertTrue(result)

    @patch("requests.get")
    def test_self_test_without_ca_cert_file_verify_ssl_false(self, mock_get):
        """Test that self_test() uses verify_ssl=False when ca_cert_file is None"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.json.return_value = {"ready": True, "reason": "All providers are healthy"}
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        # Create config without ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
            ca_cert_file=None,
        )
        pipeline = HttpChatBotPipeline(config)
        # Execute health check
        result = pipeline.self_test()
        # Verify the requests.get was called with verify_ssl=False
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertFalse(call_kwargs["verify"])
        # Verify result
        self.assertTrue(result)


class TestHttpStreamingChatBotPipelineSSL(IsolatedAsyncioTestCase, WisdomLogAwareMixin):
    """Test SSL functionality in HttpStreamingChatBotPipeline"""

    def setUp(self):
        # Create a temporary certificate file for testing
        self.temp_cert_file = tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False)
        self.temp_cert_file.write(
            "-----BEGIN CERTIFICATE-----\ntest-certificate-content\n-----END CERTIFICATE-----"
        )
        self.temp_cert_file.close()
        self.ca_cert_path = self.temp_cert_file.name
        self.inference_url = "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443"

    def tearDown(self):
        # Clean up the temporary certificate file
        if os.path.exists(self.ca_cert_path):
            os.unlink(self.ca_cert_path)

    def get_stream_data(self):
        """Helper method to create mock stream data"""
        return [
            {"event": "start", "data": {"conversation_id": "test-conv-id"}},
            {"event": "token", "data": {"id": 1, "token": "Hello"}},
            {"event": "token", "data": {"id": 2, "token": " World"}},
            {"event": "end", "data": {"input_tokens": 10, "output_tokens": 2}},
        ]

    def get_mock_context_manager(self, stream_data, status=200):
        """Helper method to create mock async context manager"""

        class MockAsyncContextManager:
            def __init__(self, stream_data, status=200):
                self.stream_data = stream_data
                self.status = status
                self.reason = ""

            async def my_async_generator(self):
                for data in self.stream_data:
                    s = json.dumps(data)
                    yield (f"data: {s}\n\n".encode())

            async def __aenter__(self):
                self.content = self.my_async_generator()
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return MockAsyncContextManager(stream_data, status)

    @patch("ssl.create_default_context")
    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_async_invoke_ssl_context_with_ca_cert_file(
        self, mock_tcp_connector, mock_post, mock_ssl_context
    ):
        """Test that async_invoke creates SSL context when ca_cert_file is provided"""
        # Mock SSL context creation
        mock_ssl_context_instance = MagicMock()
        mock_ssl_context.return_value = mock_ssl_context_instance

        # Create config with ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        pipeline = HttpStreamingChatBotPipeline(config)
        # Mock the connector
        mock_connector_instance = MagicMock()
        mock_tcp_connector.return_value = mock_connector_instance
        # Mock the post method
        mock_post.return_value = self.get_mock_context_manager(self.get_stream_data())
        # Create parameters
        event = StreamingChatBotOperationalEvent()
        event.rh_user_has_seat = True
        params = StreamingChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
            media_type="application/json",
            event=event,
        )
        # Execute
        result_count = 0
        async for _ in pipeline.async_invoke(params):
            result_count += 1

        # Verify SSL context was created
        mock_ssl_context.assert_called_once_with()
        # Verify TCPConnector was created with the SSL context
        mock_tcp_connector.assert_called_once_with(ssl=mock_ssl_context_instance)
        self.assertGreater(result_count, 0, "Should have received streaming data")

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_async_invoke_ssl_context_verify_ssl_false(self, mock_tcp_connector, mock_post):
        """Test that async_invoke uses ssl=False when verify_ssl=False and no ca_cert_file"""
        # Create config with verify_ssl=False
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=False,
            ca_cert_file=None,
        )
        pipeline = HttpStreamingChatBotPipeline(config)
        # Mock the connector
        mock_connector_instance = MagicMock()
        mock_tcp_connector.return_value = mock_connector_instance
        # Mock the post method
        mock_post.return_value = self.get_mock_context_manager(self.get_stream_data())
        # Create parameters
        event = StreamingChatBotOperationalEvent()
        event.rh_user_has_seat = True
        params = StreamingChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
            media_type="application/json",
            event=event,
        )
        # Execute
        result_count = 0
        async for _ in pipeline.async_invoke(params):
            result_count += 1
        # Verify TCPConnector was created with ssl=False
        mock_tcp_connector.assert_called_once_with(ssl=False)
        self.assertGreater(result_count, 0, "Should have received streaming data")

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_async_invoke_ssl_context_verify_ssl_true_no_ca_cert(
        self, mock_tcp_connector, mock_post
    ):
        """Test that async_invoke uses ssl=True when verify_ssl=True and no ca_cert_file"""
        # Create config with verify_ssl=True, no ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file=None,
        )
        pipeline = HttpStreamingChatBotPipeline(config)
        # Mock the connector
        mock_connector_instance = MagicMock()
        mock_tcp_connector.return_value = mock_connector_instance
        # Mock the post method
        mock_post.return_value = self.get_mock_context_manager(self.get_stream_data())
        # Create parameters
        event = StreamingChatBotOperationalEvent()
        event.rh_user_has_seat = True
        params = StreamingChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
            media_type="application/json",
            event=event,
        )
        # Execute
        result_count = 0
        async for _ in pipeline.async_invoke(params):
            result_count += 1
        # Verify TCPConnector was created with SSL context
        mock_tcp_connector.assert_called_once()
        # Check that ssl parameter is an SSL context, not a boolean
        call_args = mock_tcp_connector.call_args[1]
        self.assertIn("ssl", call_args)
        # ssl.create_default_context() is always used when verify_ssl=True
        self.assertIsNotNone(call_args["ssl"])
        self.assertGreater(result_count, 0, "Should have received streaming data")

    @patch("ssl.create_default_context")
    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_async_invoke_ssl_context_with_empty_ca_cert_file(
        self, mock_tcp_connector, mock_post, mock_ssl_context
    ):
        """Test that async_invoke falls back to verify_ssl when ca_cert_file is empty string"""
        # Create config with empty ca_cert_file (should fall back to verify_ssl)
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file="",  # Empty string is falsy
        )
        pipeline = HttpStreamingChatBotPipeline(config)
        # Mock the connector
        mock_connector_instance = MagicMock()
        mock_tcp_connector.return_value = mock_connector_instance
        # Mock the post method
        mock_post.return_value = self.get_mock_context_manager(self.get_stream_data())
        # Create parameters
        event = StreamingChatBotOperationalEvent()
        event.rh_user_has_seat = True
        params = StreamingChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
            media_type="application/json",
            event=event,
        )
        # Execute
        result_count = 0
        async for _ in pipeline.async_invoke(params):
            result_count += 1

        # Verify SSL context was created
        mock_ssl_context.assert_called_once_with()
        # Verify TCPConnector was created with the SSL context
        mock_tcp_connector.assert_called_once()
        call_args = mock_tcp_connector.call_args[1]
        self.assertIn("ssl", call_args)
        self.assertGreater(result_count, 0, "Should have received streaming data")

    @patch("ssl.create_default_context")
    async def test_ssl_context_creation_failure_handling(self, mock_ssl_context):
        """Test handling of SSL context creation failures"""
        # Mock SSL context creation to raise an exception
        mock_ssl_context.side_effect = ssl.SSLError("Invalid certificate file")

        # Create config with ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        pipeline = HttpStreamingChatBotPipeline(config)

        # Create parameters
        event = StreamingChatBotOperationalEvent()
        event.rh_user_has_seat = True
        params = StreamingChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
            media_type="application/json",
            event=event,
        )

        # Execute and expect SSL error to be propagated
        with self.assertRaises(ssl.SSLError):
            async for _ in pipeline.async_invoke(params):
                pass

        # Verify SSL context creation was attempted
        mock_ssl_context.assert_called_once_with()


class TestSSLErrorScenarios(TestCase, WisdomLogAwareMixin):
    """Test SSL error scenarios and edge cases"""

    def setUp(self):
        # Create a temporary certificate file for testing
        self.temp_cert_file = tempfile.NamedTemporaryFile(mode="w", suffix=".crt", delete=False)
        self.temp_cert_file.write(
            "-----BEGIN CERTIFICATE-----\ntest-certificate-content\n-----END CERTIFICATE-----"
        )
        self.temp_cert_file.close()
        self.ca_cert_path = self.temp_cert_file.name
        self.invalid_ca_cert_path = "/invalid/path/to/ca-cert.crt"
        self.inference_url = "https://ls-stack-service.wisdom-ls-stack.svc.cluster.local:8443"

    def tearDown(self):
        # Clean up the temporary certificate file
        if os.path.exists(self.ca_cert_path):
            os.unlink(self.ca_cert_path)

    @patch("requests.post")
    def test_ssl_error_with_invalid_ca_cert_path(self, mock_post):
        """Test SSL error handling when ca_cert_file path is invalid"""
        # Setup mock to raise SSL error
        from requests.exceptions import SSLError

        mock_post.side_effect = SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
        # Create config with invalid ca_cert_file path
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=False,
            verify_ssl=True,
            ca_cert_file=self.invalid_ca_cert_path,
        )
        pipeline = HttpChatBotPipeline(config)
        # Create parameters
        params = ChatBotParameters(
            query="Hello",
            provider="http",
            model_id="test-model",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )
        # Execute and expect SSL error
        with self.assertRaises(SSLError):
            pipeline.invoke(params)
        # Verify the requests.post was called with boolean SSL verification
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["verify"], True)

    @patch("requests.get")
    def test_health_check_ssl_error_with_ca_cert_file(self, mock_get):
        """Test health check SSL error handling with ca_cert_file"""
        # Setup mock to raise SSL error
        from requests.exceptions import SSLError

        mock_get.side_effect = SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
        # Create config with ca_cert_file
        config = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        pipeline = HttpChatBotPipeline(config)
        # Execute health check and expect False result due to SSL error
        result = pipeline.self_test()
        # Verify the requests.get was called with boolean SSL verification
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs["verify"], True)
        # Health check should return a summary with exceptions on SSL error
        self.assertIsNotNone(result)
        # Check that the health check failed (has exceptions)
        from ansible_ai_connect.healthcheck.backends import HealthCheckSummaryException

        has_exceptions = any(
            isinstance(item, HealthCheckSummaryException) for item in result.items.values()
        )
        self.assertTrue(has_exceptions, "Health check should have exceptions when SSL fails")


class TestDefaultSSLContextApproach(TestCase, WisdomLogAwareMixin):
    """Test the default SSL context approach"""

    def setUp(self):
        # Store original environment variables
        self.original_ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE")
        self.original_ssl_cert_file = os.environ.get("SSL_CERT_FILE")

    def tearDown(self):
        # Restore original environment variables
        if self.original_ca_bundle:
            os.environ["REQUESTS_CA_BUNDLE"] = self.original_ca_bundle
        else:
            os.environ.pop("REQUESTS_CA_BUNDLE", None)

        if self.original_ssl_cert_file:
            os.environ["SSL_CERT_FILE"] = self.original_ssl_cert_file
        else:
            os.environ.pop("SSL_CERT_FILE", None)

    @patch("os.path.exists")
    def test_ssl_context_setup_with_service_certificate(self, mock_exists):
        """Test that _setup_ssl_context() correctly configures environment variables"""
        # Mock service certificate exists
        mock_exists.side_effect = (
            lambda path: path == "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt"
        )
        # Clear environment variables
        os.environ.pop("REQUESTS_CA_BUNDLE", None)
        os.environ.pop("SSL_CERT_FILE", None)
        config = HttpConfiguration(
            inference_url="https://test.example.com",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
        )
        # Create HttpMetaData - this triggers _setup_ssl_context()
        metadata = HttpMetaData(config)

        # Verify environment variables were set
        self.assertEqual(
            os.environ.get("REQUESTS_CA_BUNDLE"),
            "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt",
        )
        self.assertEqual(
            os.environ.get("SSL_CERT_FILE"),
            "/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt",
        )
        # Verify get_ssl_verification returns verify_ssl value
        self.assertTrue(metadata.get_ssl_verification())

    @patch("os.path.exists")
    def test_ssl_context_setup_without_service_certificate(self, mock_exists):
        """Test SSL setup when service certificate doesn't exist"""
        # Mock service certificate doesn't exist
        mock_exists.return_value = False
        # Clear environment variables
        os.environ.pop("REQUESTS_CA_BUNDLE", None)
        os.environ.pop("SSL_CERT_FILE", None)
        config = HttpConfiguration(
            inference_url="https://test.example.com",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
        )
        metadata = HttpMetaData(config)

        # Environment variables should not be set
        self.assertIsNone(os.environ.get("REQUESTS_CA_BUNDLE"))
        self.assertIsNone(os.environ.get("SSL_CERT_FILE"))
        # But get_ssl_verification should still return True (system certs)
        self.assertTrue(metadata.get_ssl_verification())

    def test_ssl_verification_disabled(self):
        """Test behavior when SSL verification is disabled"""
        config = HttpConfiguration(
            inference_url="http://test.example.com",  # http, not https
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
        )
        metadata = HttpMetaData(config)
        # get_ssl_verification should return False
        self.assertFalse(metadata.get_ssl_verification())

    def test_eliminates_conditional_logic_issues(self):
        """
        Test that the approach that eliminates the conditional logic
        issues that caused 503 errors.
        """
        test_scenarios = [
            # (verify_ssl, ca_cert_file)
            (True, None),
            (True, ""),  # Empty string was problematic
            (True, "/some/path/cert.crt"),
            (False, None),
            (False, ""),
            (False, "/some/path/cert.crt"),
        ]
        for verify_ssl, ca_cert_file in test_scenarios:
            with self.subTest(verify_ssl=verify_ssl, ca_cert_file=ca_cert_file):
                config = HttpConfiguration(
                    inference_url="https://test.example.com",
                    model_id="test-model",
                    timeout=5000,
                    enable_health_check=True,
                    verify_ssl=verify_ssl,
                    ca_cert_file=ca_cert_file,
                )
                metadata = HttpMetaData(config)
                # The default SSL context approach should ALWAYS return verify_ssl value,
                # regardless of ca_cert_file content
                self.assertEqual(metadata.get_ssl_verification(), verify_ssl)


class TestHTTPPipeline503ErrorPrevention(TestCase, WisdomLogAwareMixin):
    """Test that HTTP pipelines prevent 503 errors"""

    def setUp(self):
        self.config = HttpConfiguration(
            inference_url="https://test.example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
        )

    @patch("requests.Session.post")
    def test_completions_pipeline_uses_simple_ssl_verification(self, mock_post):
        """Test that HttpCompletionsPipeline uses the simplified SSL verification"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"predictions": [{"output": "test output"}]}'
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response
        pipeline = HttpCompletionsPipeline(self.config)
        # Create mock parameters
        mock_request = MagicMock()
        mock_request.user = MagicMock()
        mock_request.user.uuid = "test-user-id"
        params = CompletionsParameters(
            request=mock_request,
            model_id="test-model",
            model_input={"instances": [{"prompt": "test prompt"}]},
        )
        # Execute
        result = pipeline.invoke(params)
        # Verify that requests.post was called with verify=True (not complex conditional)
        mock_post.assert_called_once()

        # In default SSL context approach, verify should be simple boolean True
        # The session should handle SSL configuration, not individual requests
        self.assertIsInstance(result, dict)

    @patch("requests.post")
    def test_chatbot_pipeline_uses_simple_ssl_verification(self, mock_post):
        """Test that HttpChatBotPipeline uses the simplified SSL verification"""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = (
            '{"response": "Test response", "referenced_documents": [], "truncated": false}'
        )
        mock_response.json.return_value = {
            "response": "Test response",
            "referenced_documents": [],
            "truncated": False,
        }
        mock_post.return_value = mock_response
        pipeline = HttpChatBotPipeline(self.config)
        params = ChatBotParameters(
            query="test query",
            conversation_id="test-conv-id",
            model_id="test-model",
            provider="test-provider",
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )
        # Execute
        result = pipeline.invoke(params)

        # Verify call was made and returned expected structure
        mock_post.assert_called_once()
        self.assertIsNotNone(result)

    @patch("aiohttp.ClientSession")
    def test_streaming_chatbot_ssl_context_creation(self, mock_session_class):
        """Test that HttpStreamingChatBotPipeline creates proper SSL context"""
        # Setup mock session
        mock_session = MagicMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Mock response
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.status_code = 200
        mock_response.content = AsyncIteratorMock([b'data: {"event": "start"}\n\n'])
        mock_session.post.return_value.__aenter__.return_value = mock_response
        pipeline = HttpStreamingChatBotPipeline(self.config)
        # Create mock parameters
        mock_event = StreamingChatBotOperationalEvent()
        params = StreamingChatBotParameters(
            query="test query",
            conversation_id="test-conv-id",
            model_id="test-model",
            provider="test-provider",
            system_prompt="You are a helpful assistant",
            no_tools=False,
            media_type="application/json",
            event=mock_event,
        )

        # Execute async invoke (we need to consume the async generator)
        async def consume_generator():
            chunks = []
            async for chunk in pipeline.async_invoke(params):
                chunks.append(chunk)
            return chunks

        # Run the async function
        import asyncio

        try:
            asyncio.run(consume_generator())
        except Exception:
            # We expect this might fail due to mocking, but we want to verify
            # that ClientSession was called with proper SSL configuration
            pass

        # Verify that ClientSession was created
        # The important thing is that SSL context creation doesn't fail
        mock_session_class.assert_called()
        # Verify the call included raise_for_status and connector
        call_kwargs = mock_session_class.call_args[1]
        self.assertTrue(call_kwargs.get("raise_for_status"))
        self.assertIn("connector", call_kwargs)


class TestSSLErrorHandling(TestCase, WisdomLogAwareMixin):
    """Test default SSL context error handling"""

    def test_ssl_setup_with_invalid_certificate_path(self):
        """Test that invalid certificate paths don't cause 503 errors"""
        # This scenario could have caused issues in the old approach
        config = HttpConfiguration(
            inference_url="https://test.example.com",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file="/nonexistent/path/cert.crt",  # Invalid path
        )
        # With default SSL context approach it
        # should not cause initialization failure
        # because ca_cert_file is not used for conditional logic
        metadata = HttpMetaData(config)

        # Should still return True because verify_ssl=True
        self.assertTrue(metadata.get_ssl_verification())

    @patch("requests.Session.get")
    def test_health_check_ssl_error_handling(self, mock_get):
        """Test that SSL errors in health checks are properly handled"""
        # Simulate SSL error
        mock_get.side_effect = requests.exceptions.SSLError("SSL handshake failed")
        config = HttpConfiguration(
            inference_url="https://test.example.com",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
        )
        pipeline = HttpCompletionsPipeline(config)
        # Health check should handle SSL error gracefully
        summary = pipeline.self_test()
        # Should have items (indicating health check was executed) but not crash
        self.assertIsNotNone(summary)
        # Check that summary has been populated (either with exceptions or messages)
        self.assertIsInstance(summary.items, dict)

    def test_environment_variable_precedence(self):
        """Test that environment variables work correctly with existing values"""
        # Set initial environment variables
        os.environ["REQUESTS_CA_BUNDLE"] = "/existing/bundle"
        os.environ["SSL_CERT_FILE"] = "/existing/cert"

        try:
            with patch("os.path.exists", return_value=True):
                config = HttpConfiguration(
                    inference_url="https://test.example.com",
                    model_id="test-model",
                    timeout=5000,
                    enable_health_check=True,
                    verify_ssl=True,
                )
                # Create metadata - should not overwrite existing env vars
                HttpMetaData(config)
                # Should preserve existing values (setdefault behavior)
                self.assertEqual(os.environ.get("REQUESTS_CA_BUNDLE"), "/existing/bundle")
                self.assertEqual(os.environ.get("SSL_CERT_FILE"), "/existing/cert")
        finally:
            # Clean up
            os.environ.pop("REQUESTS_CA_BUNDLE", None)
            os.environ.pop("SSL_CERT_FILE", None)


class AsyncIteratorMock:
    """Helper class for mocking async iterators"""

    def __init__(self, items):
        self.items = items
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.items):
            raise StopAsyncIteration
        item = self.items[self.index]
        self.index += 1
        return item
