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
from unittest.mock import Mock, patch

from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import HttpChatBotPipeline
from ansible_ai_connect.ai.api.model_pipelines.pipelines import ChatBotParameters
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.test_utils import WisdomServiceLogAwareTestCase


class MockResponse:
    def __init__(self, json_data, status_code=200):
        self.json_data = json_data
        self.status_code = status_code
        self.text = json.dumps(json_data)

    def raise_for_status(self):
        if self.status_code >= 400:
            from requests.exceptions import HTTPError

            raise HTTPError(f"HTTP {self.status_code}")


@override_settings(CHATBOT_DEFAULT_SYSTEM_PROMPT="You are a helpful assistant")
class TestHttpChatBotPipelineMCPHeaders(WisdomServiceLogAwareTestCase):
    """
    Test HTTP ChatBot Pipeline with MCP headers functionality in HTTPS/SSL context.
    """

    def setUp(self):
        super().setUp()
        # Use HTTPS configuration consistent with SSL/TLS enablement PR
        config = mock_pipeline_config(
            "http", inference_url="https://example.com:8443", verify_ssl=True, ca_cert_file=None
        )
        assert isinstance(config, HttpConfiguration)
        self.config = config
        self.pipeline = HttpChatBotPipeline(self.config)

        # Mock the session to prevent actual HTTP calls
        self.pipeline.session = Mock()

    def get_params(self, mcp_headers=None) -> ChatBotParameters:
        """Helper to create test parameters"""
        return ChatBotParameters(
            query="Hello, how are you?",
            conversation_id="test-conversation-123",
            provider="test-provider",
            model_id="test-model",
            system_prompt="You are a helpful assistant",
            no_tools=False,
            mcp_headers=mcp_headers,
        )

    def test_invoke_without_mcp_headers(self):
        """Test that invoke works correctly without MCP headers"""
        response_data = {
            "response": "Hello! I'm doing well, thank you.",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params()
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello! I'm doing well, thank you.")
        self.assertFalse(result["truncated"])
        self.assertEqual(result["referenced_documents"], [])

        # Verify the HTTP call was made with correct parameters
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check URL (HTTPS for secure communication)
        self.assertEqual(call_args[0][0], "https://example.com:8443/v1/query")

        # Check headers (should only have Content-Type)
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertNotIn("MCP-HEADERS", headers)

        # Check JSON data
        json_data = call_args[1]["json"]
        self.assertEqual(json_data["query"], "Hello, how are you?")
        self.assertEqual(json_data["conversation_id"], "test-conversation-123")
        self.assertEqual(json_data["provider"], "test-provider")
        self.assertEqual(json_data["model"], "test-model")
        self.assertEqual(json_data["system_prompt"], "You are a helpful assistant")
        # no_tools is only included in JSON if it's True, not when False
        self.assertNotIn("no_tools", json_data)

    def test_invoke_with_mcp_headers(self):
        """Test that invoke correctly includes MCP headers in the HTTP request"""
        mcp_headers = {
            "server1": {"type": "stdio", "command": "node", "args": ["server.js"]},
            "server2": {"type": "http", "url": "http://localhost:3000"},
        }

        response_data = {
            "response": "Hello with MCP!",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params(mcp_headers=mcp_headers)
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello with MCP!")

        # Verify the HTTP call was made with correct parameters
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check that MCP headers are included in the request headers
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertIn("MCP-HEADERS", headers)

        # Verify the MCP headers are correctly JSON encoded
        mcp_headers_in_request = json.loads(headers["MCP-HEADERS"])
        self.assertEqual(mcp_headers_in_request, mcp_headers)

    def test_invoke_with_empty_mcp_headers(self):
        """Test that invoke handles empty MCP headers correctly (empty dict is not included)"""
        response_data = {
            "response": "Hello with empty MCP!",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        # Test with empty dict
        params = self.get_params(mcp_headers={})
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello with empty MCP!")

        # Verify the HTTP call was made
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check that MCP headers are NOT included when empty dict is provided
        # Empty dict is falsy, so MCP headers won't be included
        headers = call_args[1]["headers"]
        self.assertNotIn("MCP-HEADERS", headers)

    def test_invoke_none_mcp_headers(self):
        """Test that invoke handles None MCP headers correctly"""
        response_data = {
            "response": "Hello without MCP!",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params(mcp_headers=None)
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello without MCP!")
        # Verify the HTTP call was made
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args
        # Check that MCP headers are NOT included when None
        headers = call_args[1]["headers"]
        self.assertNotIn("MCP-HEADERS", headers)

    def test_invoke_error_response_401(self):
        """Test that invoke handles 401 error responses correctly"""
        from ansible_ai_connect.ai.api.exceptions import ChatbotUnauthorizedException

        error_response = {"detail": "Unauthorized access"}
        self.pipeline.session.post.return_value = MockResponse(error_response, 401)
        params = self.get_params()
        with self.assertRaises(ChatbotUnauthorizedException) as cm:
            self.pipeline.invoke(params)
        self.assertEqual(str(cm.exception.detail), "Unauthorized access")

    def test_invoke_error_response_403(self):
        """Test that invoke handles 403 error responses correctly"""
        from ansible_ai_connect.ai.api.exceptions import ChatbotForbiddenException

        error_response = {"detail": "Forbidden"}
        self.pipeline.session.post.return_value = MockResponse(error_response, 403)
        params = self.get_params()
        with self.assertRaises(ChatbotForbiddenException) as cm:
            self.pipeline.invoke(params)
        self.assertEqual(str(cm.exception.detail), "Forbidden")

    def test_invoke_error_response_422(self):
        """Test that invoke handles 422 validation error responses correctly"""
        from ansible_ai_connect.ai.api.exceptions import ChatbotValidationException

        error_response = {"detail": "Validation failed"}
        self.pipeline.session.post.return_value = MockResponse(error_response, 422)
        params = self.get_params()

        with self.assertRaises(ChatbotValidationException) as cm:
            self.pipeline.invoke(params)
        self.assertEqual(str(cm.exception.detail), "Validation failed")

    def test_headers_initialization(self):
        """Test that headers are properly initialized from self.headers"""
        # Test that when self.headers is empty dict, it works properly
        original_headers = self.pipeline.headers
        self.pipeline.headers = {}
        response_data = {"response": "test", "truncated": False, "referenced_documents": []}
        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params()
        self.pipeline.invoke(params)
        # Verify headers were properly handled
        self.pipeline.session.post.assert_called_once()
        # Restore original headers
        self.pipeline.headers = original_headers

    @patch("ansible_ai_connect.main.ssl_manager.ssl_manager.get_requests_session")
    def test_ssl_manager_integration(self, mock_get_session):
        """Test that the pipeline properly uses SSL manager for session creation"""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        # Create a new pipeline instance to test __init__
        config = HttpConfiguration(
            inference_url="https://example.com:8443",
            model_id="test-model",
            timeout=5000,
            enable_health_check=True,
            verify_ssl=True,
        )
        pipeline = HttpChatBotPipeline(config)
        # Verify SSL manager was called with correct parameters
        mock_get_session.assert_called_once_with()
        # Verify the session is properly set
        self.assertEqual(pipeline.session, mock_session)

    def test_mcp_headers_with_ssl_disabled(self):
        """Test that MCP headers work correctly when SSL verification is disabled"""
        # Create pipeline with SSL verification disabled
        config = mock_pipeline_config(
            "http",
            inference_url="https://example.com:8443",
            verify_ssl=False,  # SSL verification disabled
            ca_cert_file=None,
        )
        assert isinstance(config, HttpConfiguration)
        pipeline = HttpChatBotPipeline(config)
        pipeline.session = Mock()

        mcp_headers = {"server1": {"type": "stdio", "command": "node", "args": ["server.js"]}}
        response_data = {
            "response": "Hello with MCP (SSL disabled)!",
            "truncated": False,
            "referenced_documents": [],
        }

        pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = ChatBotParameters(
            query="Hello, how are you?",
            conversation_id="test-conversation-123",
            provider="test-provider",
            model_id="test-model",
            system_prompt="You are a helpful assistant",
            no_tools=False,
            mcp_headers=mcp_headers,
        )
        result = pipeline.invoke(params)
        # Verify the response
        self.assertEqual(result["response"], "Hello with MCP (SSL disabled)!")
        # Verify the HTTP call was made with correct parameters
        pipeline.session.post.assert_called_once()
        call_args = pipeline.session.post.call_args
        # Check that MCP headers are included even when SSL is disabled
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertIn("MCP-HEADERS", headers)
        # Verify the MCP headers are correctly JSON encoded
        mcp_headers_in_request = json.loads(headers["MCP-HEADERS"])
        self.assertEqual(mcp_headers_in_request, mcp_headers)
        # Verify SSL configuration
        self.assertFalse(pipeline.config.verify_ssl)

    def test_mcp_headers_with_ca_cert_file(self):
        """Test that MCP headers work correctly with custom CA certificate file"""
        # Create pipeline with custom CA cert file
        config = mock_pipeline_config(
            "http",
            inference_url="https://example.com:8443",
            verify_ssl=True,
            ca_cert_file="/path/to/custom/ca.crt",
        )
        assert isinstance(config, HttpConfiguration)
        pipeline = HttpChatBotPipeline(config)
        pipeline.session = Mock()

        mcp_headers = {
            "secure_server": {"type": "https", "url": "https://secure-mcp-server.com:8443"}
        }
        response_data = {
            "response": "Hello with MCP (custom CA)!",
            "truncated": False,
            "referenced_documents": [],
        }
        pipeline.session.post.return_value = MockResponse(response_data, 200)
        params = ChatBotParameters(
            query="Secure query",
            conversation_id="secure-conversation-456",
            provider="secure-provider",
            model_id="secure-model",
            system_prompt="You are a secure assistant",
            no_tools=False,
            mcp_headers=mcp_headers,
        )
        result = pipeline.invoke(params)
        # Verify the response
        self.assertEqual(result["response"], "Hello with MCP (custom CA)!")
        # Verify the HTTP call was made with correct parameters
        pipeline.session.post.assert_called_once()
        call_args = pipeline.session.post.call_args
        # Check that MCP headers are included with custom CA configuration
        headers = call_args[1]["headers"]
        self.assertIn("MCP-HEADERS", headers)
        # Verify the MCP headers are correctly JSON encoded
        mcp_headers_in_request = json.loads(headers["MCP-HEADERS"])
        self.assertEqual(mcp_headers_in_request, mcp_headers)
        # Verify SSL configuration
        self.assertTrue(pipeline.config.verify_ssl)
        self.assertEqual(pipeline.config.ca_cert_file, "/path/to/custom/ca.crt")

    def test_invoke_with_no_tools_true(self):
        """Test that no_tools field is included when set to True"""
        response_data = {
            "response": "Hello with no tools!",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = ChatBotParameters(
            query="Hello, how are you?",
            conversation_id="test-conversation-123",
            provider="test-provider",
            model_id="test-model",
            system_prompt="You are a helpful assistant",
            no_tools=True,  # Set to True
            mcp_headers=None,
        )

        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello with no tools!")

        # Verify the HTTP call was made with correct parameters
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check JSON data - no_tools should be included when True
        json_data = call_args[1]["json"]
        self.assertIn("no_tools", json_data)
        self.assertTrue(json_data["no_tools"])


@override_settings(CHATBOT_DEFAULT_SYSTEM_PROMPT="You are a helpful assistant")
class TestHttpChatBotPipelineAuthorizationHeader(WisdomServiceLogAwareTestCase):
    """
    Test HTTP ChatBot Pipeline's Authorization header.
    """

    def setUp(self):
        super().setUp()
        # Use HTTPS configuration consistent with SSL/TLS enablement PR
        config = mock_pipeline_config(
            "http", inference_url="https://example.com:8443", verify_ssl=True, ca_cert_file=None
        )
        assert isinstance(config, HttpConfiguration)
        self.config = config
        self.pipeline = HttpChatBotPipeline(self.config)

        # Mock the session to prevent actual HTTP calls
        self.pipeline.session = Mock()

    @staticmethod
    def get_params(auth_header=None) -> ChatBotParameters:
        """Helper to create test parameters"""
        return ChatBotParameters(
            query="Hello, how are you?",
            conversation_id="test-conversation-123",
            provider="test-provider",
            model_id="test-model",
            system_prompt="You are a helpful assistant",
            no_tools=False,
            mcp_headers=None,
            auth_header=auth_header,
        )

    def test_invoke_with_auth_header(self):
        """Test that invoke correctly includes Authorization header in the HTTP request"""
        auth_header = {"Authentication": "***"}

        response_data = {
            "response": "Hello",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params(auth_header=auth_header)
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello")

        # Verify the HTTP call was made with correct parameters
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check that Authorization header are included in the request headers
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertIn("Authorization", headers)

        # Verify the Authorization header are correctly JSON encoded
        auth_header_in_request = headers["Authorization"]
        self.assertEqual(auth_header_in_request, auth_header)

    def test_invoke_with_no_auth_header(self):
        """Test that invoke correctly handles no Authorization header in the HTTP request"""
        response_data = {
            "response": "Hello",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params(auth_header=None)
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello")

        # Verify the HTTP call was made with correct parameters
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check that Authorization header are included in the request headers
        headers = call_args[1]["headers"]
        self.assertEqual(headers["Content-Type"], "application/json")
        self.assertNotIn("Authorization", headers)


@override_settings(CHATBOT_DEFAULT_SYSTEM_PROMPT="You are a helpful assistant")
class TestHttpChatBotPipelineNormalizeReferencedDocuments(WisdomServiceLogAwareTestCase):
    """
    Test HTTP ChatBot Pipeline's _normalize_referenced_documents method.
    """

    def setUp(self):
        super().setUp()
        config = mock_pipeline_config(
            "http", inference_url="https://example.com:8443", verify_ssl=True, ca_cert_file=None
        )
        assert isinstance(config, HttpConfiguration)
        self.config = config
        self.pipeline = HttpChatBotPipeline(self.config)

    def test_normalize_new_format_to_old_format(self):
        """Test that new format (doc_title/doc_url) is converted to old format (title/docs_url)"""
        new_format_docs = [
            {"doc_title": "Ansible Guide", "doc_url": "https://docs.ansible.com/guide"},
            {"doc_title": "Best Practices", "doc_url": "https://docs.ansible.com/best-practices"},
        ]

        result = self.pipeline._normalize_referenced_documents(new_format_docs)

        expected = [
            {"title": "Ansible Guide", "docs_url": "https://docs.ansible.com/guide"},
            {"title": "Best Practices", "docs_url": "https://docs.ansible.com/best-practices"},
        ]
        self.assertEqual(result, expected)

    def test_normalize_old_format_unchanged(self):
        """Test that old format (title/docs_url) is passed through unchanged"""
        old_format_docs = [
            {"title": "Ansible Guide", "docs_url": "https://docs.ansible.com/guide"},
            {"title": "Best Practices", "docs_url": "https://docs.ansible.com/best-practices"},
        ]

        result = self.pipeline._normalize_referenced_documents(old_format_docs)

        self.assertEqual(result, old_format_docs)

    def test_normalize_mixed_format_documents(self):
        """Test that mixed format documents are handled correctly"""
        mixed_docs = [
            {"doc_title": "New Format Doc", "doc_url": "https://example.com/new"},
            {"title": "Old Format Doc", "docs_url": "https://example.com/old"},
            {"doc_title": "Another New Doc", "doc_url": "https://example.com/new2"},
        ]

        result = self.pipeline._normalize_referenced_documents(mixed_docs)

        expected = [
            {"title": "New Format Doc", "docs_url": "https://example.com/new"},
            {"title": "Old Format Doc", "docs_url": "https://example.com/old"},
            {"title": "Another New Doc", "docs_url": "https://example.com/new2"},
        ]
        self.assertEqual(result, expected)

    def test_normalize_empty_list(self):
        """Test that empty list is handled correctly"""
        result = self.pipeline._normalize_referenced_documents([])
        self.assertEqual(result, [])

    def test_normalize_documents_with_additional_fields(self):
        """Test that documents with additional fields preserve those fields"""
        docs_with_extra_fields = [
            {
                "doc_title": "Guide",
                "doc_url": "https://example.com/guide",
                "score": 0.95,
                "metadata": {"source": "ansible-docs"},
            }
        ]

        result = self.pipeline._normalize_referenced_documents(docs_with_extra_fields)

        # Only title and docs_url should be in the result
        expected = [{"title": "Guide", "docs_url": "https://example.com/guide"}]
        self.assertEqual(result, expected)

    def test_invoke_normalizes_referenced_documents(self):
        """Test that invoke() uses _normalize_referenced_documents on response data"""
        # Mock the session to prevent actual HTTP calls
        self.pipeline.session = Mock()

        response_data = {
            "response": "Test response",
            "referenced_documents": [
                {"doc_title": "Doc 1", "doc_url": "https://example.com/1"},
                {"doc_title": "Doc 2", "doc_url": "https://example.com/2"},
            ],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = ChatBotParameters(
            query="Test query",
            conversation_id="test-123",
            provider="test-provider",
            model_id="test-model",
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )

        result = self.pipeline.invoke(params)

        # Verify that referenced_documents were normalized
        expected_docs = [
            {"title": "Doc 1", "docs_url": "https://example.com/1"},
            {"title": "Doc 2", "docs_url": "https://example.com/2"},
        ]
        self.assertEqual(result["referenced_documents"], expected_docs)
        self.assertEqual(result["response"], "Test response")
        self.assertFalse(result["truncated"])  # Default value added

    def test_invoke_handles_missing_referenced_documents(self):
        """Test that invoke() handles response without referenced_documents field"""
        # Mock the session to prevent actual HTTP calls
        self.pipeline.session = Mock()

        response_data = {"response": "Test response"}

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = ChatBotParameters(
            query="Test query",
            conversation_id="test-123",
            provider="test-provider",
            model_id="test-model",
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )

        result = self.pipeline.invoke(params)

        # Verify that empty list is returned for referenced_documents
        self.assertEqual(result["referenced_documents"], [])
        self.assertEqual(result["response"], "Test response")
        self.assertFalse(result["truncated"])


@override_settings(CHATBOT_DEFAULT_SYSTEM_PROMPT="You are a helpful assistant")
class TestHttpChatBotPipelineGenerateTopicSummary(WisdomServiceLogAwareTestCase):
    """
    Test HTTP ChatBot Pipeline's generate_topic_summary field.
    """

    def setUp(self):
        super().setUp()
        config = mock_pipeline_config(
            "http", inference_url="https://example.com:8443", verify_ssl=True, ca_cert_file=None
        )
        assert isinstance(config, HttpConfiguration)
        self.config = config
        self.pipeline = HttpChatBotPipeline(self.config)
        self.pipeline.session = Mock()

    def get_params(self) -> ChatBotParameters:
        """Helper to create test parameters"""
        return ChatBotParameters(
            query="Hello, how are you?",
            conversation_id="test-conversation-123",
            provider="test-provider",
            model_id="test-model",
            system_prompt="You are a helpful assistant",
            no_tools=False,
        )

    @override_settings(CHATBOT_GENERATE_TOPIC_SUMMARY=False)
    def test_invoke_with_generate_topic_summary_false(self):
        """Test that generate_topic_summary is set to False when setting is False"""
        response_data = {
            "response": "Hello!",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params()
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello!")

        # Verify the HTTP call includes generate_topic_summary
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check JSON data includes generate_topic_summary with correct value
        json_data = call_args[1]["json"]
        self.assertIn("generate_topic_summary", json_data)
        self.assertFalse(json_data["generate_topic_summary"])

    @override_settings(CHATBOT_GENERATE_TOPIC_SUMMARY=True)
    def test_invoke_with_generate_topic_summary_true(self):
        """Test that generate_topic_summary is set to True when setting is True"""
        response_data = {
            "response": "Hello with topic summary!",
            "truncated": False,
            "referenced_documents": [],
        }

        self.pipeline.session.post.return_value = MockResponse(response_data, 200)

        params = self.get_params()
        result = self.pipeline.invoke(params)

        # Verify the response
        self.assertEqual(result["response"], "Hello with topic summary!")

        # Verify the HTTP call includes generate_topic_summary
        self.pipeline.session.post.assert_called_once()
        call_args = self.pipeline.session.post.call_args

        # Check JSON data includes generate_topic_summary with correct value
        json_data = call_args[1]["json"]
        self.assertIn("generate_topic_summary", json_data)
        self.assertTrue(json_data["generate_topic_summary"])
