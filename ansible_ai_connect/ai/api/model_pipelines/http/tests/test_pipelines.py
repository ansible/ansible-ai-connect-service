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
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
    HttpStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    StreamingChatBotParameters,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
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
        self.pipeline = HttpStreamingChatBotPipeline(mock_pipeline_config("http"))
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
        return StreamingChatBotParameters(
            query="Hello",
            provider="",
            model_id="",
            conversation_id=None,
            system_prompt=None,
            media_type="application/json",
        )

    def send_event(self, ev):
        self.call_counter += 1
        self.assertEqual(ev.chat_prompt, "Hello")
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
