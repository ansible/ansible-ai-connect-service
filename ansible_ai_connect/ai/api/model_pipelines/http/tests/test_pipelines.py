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
import ssl
from typing import cast
from unittest import IsolatedAsyncioTestCase
from unittest.mock import MagicMock, patch

from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    StreamingChatBotParameters,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.ai.api.telemetry.schema1 import StreamingChatBotOperationalEvent
from ansible_ai_connect.test_utils import WisdomLogAwareMixin

logger = logging.getLogger(__name__)


class TestHttpStreamingChatBotPipeline(IsolatedAsyncioTestCase, WisdomLogAwareMixin):
    pipeline: HttpStreamingChatBotPipeline

    STREAM_DATA = [
        {"event": "start", "data": {"conversation_id": "92766ddd-dfc8-4830-b269-7a4b3dbc7c3f"}},
        {"event": "token", "data": {"id": 0, "token": ""}},
        {"event": "token", "data": {"id": 1, "token": "Hello"}},
        {"event": "token", "data": {"id": 2, "token": "!"}},
        {"event": "token", "data": {"id": 3, "token": " I"}},
        {"event": "token", "data": {"id": 4, "token": "'m"}},
        {"event": "token", "data": {"id": 5, "token": " Ansible"}},
        {"event": "token", "data": {"id": 6, "token": " L"}},
        {"event": "token", "data": {"id": 7, "token": "ights"}},
        {"event": "token", "data": {"id": 8, "token": "peed"}},
        {"event": "token", "data": {"id": 9, "token": ","}},
        {"event": "token", "data": {"id": 10, "token": " your"}},
        {"event": "token", "data": {"id": 11, "token": " virtual"}},
        {"event": "token", "data": {"id": 12, "token": " assistant"}},
        {"event": "token", "data": {"id": 13, "token": " for"}},
        {"event": "token", "data": {"id": 14, "token": " all"}},
        {"event": "token", "data": {"id": 15, "token": " things"}},
        {"event": "token", "data": {"id": 16, "token": " Ansible"}},
        {"event": "token", "data": {"id": 17, "token": "."}},
        {"event": "token", "data": {"id": 18, "token": " How"}},
        {"event": "token", "data": {"id": 19, "token": " can"}},
        {"event": "token", "data": {"id": 20, "token": " I"}},
        {"event": "token", "data": {"id": 21, "token": " assist"}},
        {"event": "token", "data": {"id": 22, "token": " you"}},
        {"event": "token", "data": {"id": 23, "token": " today"}},
        {"event": "token", "data": {"id": 24, "token": "?"}},
        {"event": "token", "data": {"id": 25, "token": ""}},
        {
            "event": "end",
            "data": {
                "referenced_documents": [
                    {
                        "doc_title": "Document 1",
                        "doc_url": "https://example.com/document1",
                    },
                    {
                        "title": "Document 2",
                        "docs_url": "https://example.com/document2",
                    },
                ],
                "truncated": False,
                "input_tokens": 241,
                "output_tokens": 25,
            },
        },
    ]

    STREAM_DATA_PROMPT_TOO_LONG = [
        {"event": "start", "data": {"conversation_id": "92766ddd-dfc8-4830-b269-7a4b3dbc7c3e"}},
        {
            "event": "error",
            "data": {"response": "Prompt is too long", "cause": "Prompt length 10000 exceeds LLM"},
        },
    ]

    STREAM_DATA_PROMPT_GENERIC_LLM_ERROR = [
        {"event": "start", "data": {"conversation_id": "92766ddd-dfc8-4830-b269-7a4b3dbc7c3d"}},
        {
            "event": "error",
            "data": {
                "response": "Oops, something went wrong during LLM invocation",
                "cause": "A generic LLM error",
            },
        },
    ]

    STREAM_DATA_PROMPT_ERROR_WITH_NO_DATA = [
        {"event": "start", "data": {"conversation_id": "92766ddd-dfc8-4830-b269-7a4b3dbc7c3c"}},
        {"event": "error"},
    ]

    def setUp(self):
        self.pipeline = HttpStreamingChatBotPipeline(
            cast(HttpConfiguration, mock_pipeline_config("http"))
        )
        self.call_counter = 0

    def assertInLog(self, s, logs, number_of_matches_expected=None):
        self.assertTrue(self.searchInLogOutput(s, logs, number_of_matches_expected), logs)

    def get_return_value(self, stream_data, status=200):
        class MyAsyncContextManager:
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
                self.status = self.status
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

        return MyAsyncContextManager(stream_data, status)

    def get_params(self) -> StreamingChatBotParameters:
        event = StreamingChatBotOperationalEvent()
        event.rh_user_has_seat = True
        return StreamingChatBotParameters(
            query="Hello",
            provider="",
            model_id="",
            conversation_id=None,
            system_prompt="You are a helpful assistant",
            media_type="application/json",
            no_tools=False,  # Do not bypass tool callings
            event=event,
        )

    def send_event(self, ev):
        self.call_counter += 1
        self.assertEqual(ev.conversation_id, "92766ddd-dfc8-4830-b269-7a4b3dbc7c3f")
        if ev.phase == "end":
            self.assertEqual(len(ev.chat_referenced_documents), 2)
            for doc in ev.chat_referenced_documents:
                self.assertIn("title", doc)
                self.assertIn("docs_url", doc)

    @patch("aiohttp.ClientSession.post")
    async def test_async_invoke_with_no_error(self, mock_post):
        mock_post.return_value = self.get_return_value(self.STREAM_DATA)
        with patch(
            "ansible_ai_connect.ai.api.model_pipelines.http.pipelines"
            ".HttpStreamingChatBotPipeline.send_schema1_event",
            wraps=self.send_event,
        ):
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
        self.assertEqual(self.call_counter, 2)

    @patch("aiohttp.ClientSession.post")
    @override_settings(CHATBOT_RETURN_TOOL_CALL=False)
    async def test_async_invoke_tool_call_hidden_with_no_error(self, mock_post):
        tool_call_event_id = 5
        tool_result_event_id = 6
        tool_call_event = {
            "event": "tool_call",
            "data": {
                "id": tool_call_event_id,
                "token": {
                    "tool_name": "knowledge_search",
                    "arguments": {"query": "Exploratory Data Analysis"},
                },
            },
        }
        tool_result_event = {
            "event": "tool_result",
            "data": {
                "id": tool_result_event_id,
                "token": {
                    "tool_name": "knowledge_search",
                    "summary": "knowledge_search tool found 5 chunks:",
                },
            },
        }
        stream_data = [
            {"event": "start", "data": {"conversation_id": "92766ddd-dfc8-4830-b269-7a4b3dbc7c3f"}},
            {"event": "token", "data": {"id": 0, "token": ""}},
            tool_call_event,
            tool_result_event,
            {"event": "token", "data": {"id": 24, "token": "some data"}},
            {"event": "token", "data": {"id": 25, "token": ""}},
            {
                "event": "end",
                "data": {
                    "referenced_documents": [
                        {
                            "doc_title": "Document 1",
                            "doc_url": "https://example.com/document1",
                        },
                        {
                            "title": "Document 2",
                            "docs_url": "https://example.com/document2",
                        },
                    ],
                    "truncated": False,
                    "input_tokens": 241,
                    "output_tokens": 25,
                },
            },
        ]

        mock_post.return_value = self.get_return_value(stream_data)
        with patch(
            "ansible_ai_connect.ai.api.model_pipelines.http.pipelines"
            ".HttpStreamingChatBotPipeline.send_schema1_event",
            wraps=self.send_event,
        ):
            tool_calls_data_counter = 0
            events_counter = 0
            async for chunk in self.pipeline.async_invoke(self.get_params()):
                chunk_string = chunk.decode("utf-8")
                if chunk_string.startswith("data: "):
                    chuck_data = json.loads(chunk_string.lstrip("data: "))
                    if events_counter == 2:
                        # ensure the event type has been changed to simple token
                        self.assertEqual(chuck_data["event"], "token")
                        # ensure the data token is empty
                        self.assertEqual(chuck_data["data"]["token"], "")
                        # ensure the event id is preserved
                        self.assertEqual(chuck_data["data"]["id"], tool_call_event_id)
                        # ensure the original event is in the chunk data
                        self.assertEqual(chuck_data["original"], tool_call_event)
                        tool_calls_data_counter += 1
                    if events_counter == 3:
                        # ensure the event type has been changed to simple token
                        self.assertEqual(chuck_data["event"], "token")
                        # ensure the data token is empty
                        self.assertEqual(chuck_data["data"]["token"], "")
                        # ensure the event id is preserved
                        self.assertEqual(chuck_data["data"]["id"], tool_result_event_id)
                        # ensure the original event is in the chunk data
                        self.assertEqual(chuck_data["original"], tool_result_event)
                        tool_calls_data_counter += 1
                events_counter += 1
        self.assertEqual(tool_calls_data_counter, 2)
        self.assertEqual(events_counter, len(stream_data))
        self.assertEqual(self.call_counter, 2)

    @patch("aiohttp.ClientSession.post")
    @override_settings(CHATBOT_RETURN_TOOL_CALL=True)
    async def test_async_invoke_tool_call_preserved_with_no_error(self, mock_post):
        tool_call_event_id = 5
        tool_result_event_id = 6
        tool_call_event = {
            "event": "tool_call",
            "data": {
                "id": tool_call_event_id,
                "token": {
                    "tool_name": "knowledge_search",
                    "arguments": {"query": "Exploratory Data Analysis"},
                },
            },
        }
        tool_result_event = {
            "event": "tool_result",
            "data": {
                "id": tool_result_event_id,
                "token": {
                    "tool_name": "knowledge_search",
                    "summary": "knowledge_search tool found 5 chunks:",
                },
            },
        }
        stream_data = [
            {"event": "start", "data": {"conversation_id": "92766ddd-dfc8-4830-b269-7a4b3dbc7c3f"}},
            {"event": "token", "data": {"id": 0, "token": ""}},
            tool_call_event,
            tool_result_event,
            {"event": "token", "data": {"id": 24, "token": "some data"}},
            {"event": "token", "data": {"id": 25, "token": ""}},
            {
                "event": "end",
                "data": {
                    "referenced_documents": [
                        {
                            "doc_title": "Document 1",
                            "doc_url": "https://example.com/document1",
                        },
                        {
                            "title": "Document 2",
                            "docs_url": "https://example.com/document2",
                        },
                    ],
                    "truncated": False,
                    "input_tokens": 241,
                    "output_tokens": 25,
                },
            },
        ]

        mock_post.return_value = self.get_return_value(stream_data)
        with patch(
            "ansible_ai_connect.ai.api.model_pipelines.http.pipelines"
            ".HttpStreamingChatBotPipeline.send_schema1_event",
            wraps=self.send_event,
        ):
            tool_calls_data_counter = 0
            events_counter = 0
            async for chunk in self.pipeline.async_invoke(self.get_params()):
                chunk_string = chunk.decode("utf-8")
                if chunk_string.startswith("data: "):
                    chuck_data = json.loads(chunk_string.lstrip("data: "))
                    if events_counter == 2:
                        # ensure the tool_call has not changed
                        self.assertEqual(chuck_data, tool_call_event)
                        tool_calls_data_counter += 1
                    if events_counter == 3:
                        # ensure the tool_result has not changed
                        self.assertEqual(chuck_data, tool_result_event)
                        tool_calls_data_counter += 1
                events_counter += 1
        self.assertEqual(tool_calls_data_counter, 2)
        self.assertEqual(events_counter, len(stream_data))
        self.assertEqual(self.call_counter, 2)

    @patch("aiohttp.ClientSession.post")
    async def test_async_invoke_prompt_too_long(self, mock_post):
        mock_post.return_value = self.get_return_value(self.STREAM_DATA_PROMPT_TOO_LONG)
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("Prompt is too long", log)

    @patch("aiohttp.ClientSession.post")
    async def test_async_invoke_prompt_generic_llm_error(self, mock_post):
        mock_post.return_value = self.get_return_value(self.STREAM_DATA_PROMPT_GENERIC_LLM_ERROR)
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("Oops, something went wrong during LLM invocation", log)

    @patch("aiohttp.ClientSession.post")
    async def test_async_invoke_internal_server_error(self, mock_post):
        mock_post.return_value = self.get_return_value(
            self.STREAM_DATA_PROMPT_GENERIC_LLM_ERROR, 500
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("Streaming query API returned status code=500", log)

    @patch("aiohttp.ClientSession.post")
    async def test_async_invoke_error_with_no_data(self, mock_post):
        mock_post.return_value = self.get_return_value(
            self.STREAM_DATA_PROMPT_ERROR_WITH_NO_DATA,
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("(not provided)", log)

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_ssl_context_verify_ssl_false(self, mock_tcp_connector, mock_post):
        """Test that SSL verification is consistently disabled (ssl=False) when verify_ssl=False"""
        # Setup pipeline with verify_ssl=False
        config = cast(HttpConfiguration, mock_pipeline_config("http", verify_ssl=False))
        pipeline = HttpStreamingChatBotPipeline(config)
        # Mock the connector
        mock_connector_instance = MagicMock()
        mock_tcp_connector.return_value = mock_connector_instance
        # Mock the post method to return our test data
        mock_post.return_value = self.get_return_value(self.STREAM_DATA)
        # Execute the async_invoke method
        params = self.get_params()
        async for _ in pipeline.async_invoke(params):
            pass
        # This provides consistent behavior with requests.Session.verify=False
        mock_tcp_connector.assert_called_once_with(ssl=False)

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_ssl_context_verify_ssl_true(self, mock_tcp_connector, mock_post):
        """Test that SSL context is correctly configured when verify_ssl=True"""
        # Setup pipeline with verify_ssl=True
        config = cast(HttpConfiguration, mock_pipeline_config("http", verify_ssl=True))
        pipeline = HttpStreamingChatBotPipeline(config)
        # Mock the connector
        mock_connector_instance = MagicMock()
        mock_tcp_connector.return_value = mock_connector_instance
        # Mock the post method to return our test data
        mock_post.return_value = self.get_return_value(self.STREAM_DATA)
        # Execute the async_invoke method
        params = self.get_params()
        async for _ in pipeline.async_invoke(params):
            pass
        # Verify TCPConnector was created with an SSL context object (improved behavior)
        mock_tcp_connector.assert_called_once()
        call_args = mock_tcp_connector.call_args
        self.assertIsNotNone(call_args)

        # Check that ssl parameter was passed and is an SSL context object
        ssl_param = call_args.kwargs.get("ssl")
        self.assertIsNotNone(ssl_param, "SSL parameter should be provided")
        self.assertIsInstance(
            ssl_param, ssl.SSLContext, "SSL parameter should be an SSLContext object, not just True"
        )

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_ssl_context_uses_config_value(self, mock_tcp_connector, mock_post):
        """Test that SSL context directly uses the config.verify_ssl value"""
        # Setup pipeline with a specific verify_ssl value
        config = cast(HttpConfiguration, mock_pipeline_config("http", verify_ssl=False))
        pipeline = HttpStreamingChatBotPipeline(config)
        # Mock the connector
        mock_connector_instance = MagicMock()
        mock_tcp_connector.return_value = mock_connector_instance
        # Mock the post method to return our test data
        mock_post.return_value = self.get_return_value(self.STREAM_DATA)
        # Execute the async_invoke method
        params = self.get_params()
        async for _ in pipeline.async_invoke(params):
            pass
        # Verify that ssl_context was set correctly for verify_ssl=False
        mock_tcp_connector.assert_called_once()
        call_args = mock_tcp_connector.call_args
        self.assertIsNotNone(call_args)

        ssl_param = call_args.kwargs.get("ssl")
        # This provides consistent behavior with requests.Session.verify=False
        self.assertFalse(ssl_param, "When verify_ssl=False, should get ssl=False")

    @patch("aiohttp.ClientSession.post")
    @patch("aiohttp.TCPConnector")
    async def test_ssl_context_integration_with_existing_flow(self, mock_tcp_connector, mock_post):
        """Test that SSL changes don't break existing functionality"""
        # Test with both verify_ssl values to ensure no regression
        for verify_ssl_value in [True, False]:
            with self.subTest(verify_ssl=verify_ssl_value):
                config = cast(
                    HttpConfiguration, mock_pipeline_config("http", verify_ssl=verify_ssl_value)
                )
                pipeline = HttpStreamingChatBotPipeline(config)
                # Mock the connector
                mock_connector_instance = MagicMock()
                mock_tcp_connector.return_value = mock_connector_instance
                # Mock the post method to return our test data
                mock_post.return_value = self.get_return_value(self.STREAM_DATA)
                # Execute the async_invoke method
                params = self.get_params()
                result_count = 0
                async for _ in pipeline.async_invoke(params):
                    result_count += 1
                # Verify that streaming still works
                self.assertGreater(result_count, 0, "Streaming should return data")
                # Verify SSL configuration is correct (improved behavior with SSL manager)
                mock_tcp_connector.assert_called_once()
                call_args = mock_tcp_connector.call_args
                self.assertIsNotNone(call_args)

                ssl_param = call_args.kwargs.get("ssl")
                if verify_ssl_value:
                    # When SSL is enabled, we should get an SSL context object
                    self.assertIsInstance(
                        ssl_param,
                        ssl.SSLContext,
                        f"When verify_ssl={verify_ssl_value}, should get SSL context",
                    )
                else:
                    # verify_ssl=False should disable SSL verification
                    # This provides consistent behavior with requests.Session.verify=False
                    self.assertFalse(
                        ssl_param,
                        f"When verify_ssl={verify_ssl_value}, should get ssl=False",
                    )
                # Reset mocks for next iteration
                mock_tcp_connector.reset_mock()
                mock_post.reset_mock()
