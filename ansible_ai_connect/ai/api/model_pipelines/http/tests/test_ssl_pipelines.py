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
from unittest.mock import MagicMock, patch

from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpChatBotPipeline,
    HttpCompletionsPipeline,
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
        # Verify the requests.post was called with ca_cert_file
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["verify"], self.ca_cert_path)
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
            from unittest.mock import Mock

            params = CompletionsParameters.init(
                request=Mock(),
                model_input={"context": "---\n- name: Example task", "prompt": ""},
                model_id="test-model",
            )
            # Execute
            result = pipeline.invoke(params)
            # Verify the session.post was called with ca_cert_file
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args[1]
            self.assertEqual(call_kwargs["verify"], self.ca_cert_path)
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
        # Verify the requests.get was called with ca_cert_file
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs["verify"], self.ca_cert_path)
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

        # Verify SSL context was created with ca_cert_file
        mock_ssl_context.assert_called_once_with(cafile=self.ca_cert_path)
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
        # Verify TCPConnector was created with ssl=True (default SSL context)
        mock_tcp_connector.assert_called_once_with(ssl=True)
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

        # Verify SSL context was NOT created (empty string is falsy)
        mock_ssl_context.assert_not_called()
        # Verify TCPConnector was created with ssl=True (falls back to verify_ssl)
        mock_tcp_connector.assert_called_once_with(ssl=True)
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
        mock_ssl_context.assert_called_once_with(cafile=self.ca_cert_path)


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
        # Verify the requests.post was called with invalid ca_cert_file
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs["verify"], self.invalid_ca_cert_path)

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
        # Verify the requests.get was called with ca_cert_file
        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        self.assertEqual(call_kwargs["verify"], self.ca_cert_path)
        # Health check should return a summary with exceptions on SSL error
        self.assertIsNotNone(result)
        # Check that the health check failed (has exceptions)
        from ansible_ai_connect.healthcheck.backends import HealthCheckSummaryException

        has_exceptions = any(
            isinstance(item, HealthCheckSummaryException) for item in result.items.values()
        )
        self.assertTrue(has_exceptions, "Health check should have exceptions when SSL fails")

    def test_ssl_configuration_precedence_logic(self):
        """Test the exact logic used in the application for SSL verification parameter"""
        # Test Case 1: ca_cert_file provided (should take precedence)
        config1 = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file=self.ca_cert_path,
        )
        verify_param_1 = config1.ca_cert_file if config1.ca_cert_file else config1.verify_ssl
        self.assertEqual(verify_param_1, self.ca_cert_path)
        # Test Case 2: ca_cert_file is None, verify_ssl=True
        config2 = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file=None,
        )
        verify_param_2 = config2.ca_cert_file if config2.ca_cert_file else config2.verify_ssl
        self.assertTrue(verify_param_2)
        # Test Case 3: ca_cert_file is None, verify_ssl=False
        config3 = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=False,
            ca_cert_file=None,
        )
        verify_param_3 = config3.ca_cert_file if config3.ca_cert_file else config3.verify_ssl
        self.assertFalse(verify_param_3)
        # Test Case 4: ca_cert_file is empty string (falsy), verify_ssl=True
        config4 = HttpConfiguration(
            inference_url=self.inference_url,
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
            ca_cert_file="",
        )
        verify_param_4 = config4.ca_cert_file if config4.ca_cert_file else config4.verify_ssl
        self.assertTrue(verify_param_4)  # Falls back to verify_ssl=True
