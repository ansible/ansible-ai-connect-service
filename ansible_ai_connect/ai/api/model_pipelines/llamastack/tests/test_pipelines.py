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
import logging
from datetime import datetime
from unittest import IsolatedAsyncioTestCase, TestCase, skip
from unittest.mock import patch

from llama_stack_client.types import (
    CompletionMessage,
    InferenceStep,
    ToolCall,
    ToolExecutionStep,
    ToolResponse,
)
from llama_stack_client.types.agents import (
    AgentTurnResponseStreamChunk,
    Turn,
    TurnResponseEvent,
)
from llama_stack_client.types.agents.turn_response_event_payload import (
    AgentTurnResponseStepCompletePayload,
    AgentTurnResponseStepProgressPayload,
    AgentTurnResponseStepStartPayload,
    AgentTurnResponseTurnCompletePayload,
)
from llama_stack_client.types.shared.content_delta import TextDelta, ToolCallDelta

from ansible_ai_connect.ai.api.model_pipelines.llamastack.pipelines import (
    GraniteToolParser,
    LlamaStackStreamingChatBotPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    StreamingChatBotParameters,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_pipeline_config
from ansible_ai_connect.test_utils import WisdomLogAwareMixin

logger = logging.getLogger(__name__)


class TestHttpStreamingChatBotPipeline(IsolatedAsyncioTestCase, WisdomLogAwareMixin):
    pipeline: LlamaStackStreamingChatBotPipeline

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
        {"event": "tool_call", "data": {"id": 26, "tool_call": "knowledge_search"}},
        {
            "event": "tool_call",
            "data": {
                "id": 27,
                "tool_call": {
                    "arguments": {
                        "query": "What is EDA?",
                    },
                    "tool_name": "knowledge_search",
                },
            },
        },
        {
            "event": "tool_call",
            "data": {
                "id": 28,
                "tool_calls": [
                    {
                        "arguments": {
                            "query": "What is EDA?",
                        },
                        "tool_name": "knowledge_search",
                    },
                ],
                "tool_responses": [
                    {
                        "tool_name": "knowledge_search",
                        "content": [
                            {
                                "text": """knowledge_search tool found 2 chunks:
BEGIN of knowledge_search tool results.
"""
                            },
                            {
                                "text": """Result 1"
Content: ABC
Metadata: {'docs_url': 'https://docs.example.com/1', 'title': 'ref-1', 'document_id': 'doc-1'}
"""
                            },
                            {
                                "text": """Result 2"
Content: XYZ
Metadata: {'docs_url': 'https://docs.example.com/2', 'title': 'ref-2', 'document_id': 'doc-2'}
"""
                            },
                            {"text": "END of knowledge_search tool results.\n"},
                        ],
                    },
                ],
            },
        },
        {
            "event": "end",
            "data": {
                "referenced_documents": [],
                "truncated": False,
                "input_tokens": 241,
                "output_tokens": 25,
            },
        },
        {
            "event": "turn_complete",
            "data": {
                "content": "EDA stands for Event Driven Ansible.",
                "id": 0,
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
        self.pipeline = LlamaStackStreamingChatBotPipeline(mock_pipeline_config("llama-stack"))

    def assertInLog(self, s, logs, number_of_matches_expected=None):
        self.assertTrue(self.searchInLogOutput(s, logs, number_of_matches_expected), logs)

    def get_return_value(self, stream_data, status=200):
        class MyAsyncContextManager:
            def __init__(self, stream_data, status=200):
                self.stream_data = stream_data
                self.status = status
                self.reason = ""

            @staticmethod
            def _make_payload(data: dict):
                event_type = data["event"]
                match event_type:
                    case "start":
                        payload = data["data"]
                        return AgentTurnResponseStepStartPayload(
                            event_type="step_start",
                            step_id="step-start",
                            step_type="inference",
                            metadata={"conversation_id": payload["conversation_id"]},
                        )
                    case "token":
                        payload = data["data"]
                        return AgentTurnResponseStepProgressPayload(
                            event_type="step_progress",
                            step_id=f"step-{payload['id']}",
                            step_type="inference",
                            delta=TextDelta(type="text", text=payload["token"]),
                        )
                    case "end":
                        return AgentTurnResponseStepCompletePayload(
                            event_type="step_complete",
                            step_id="step-end",
                            step_type="inference",
                            step_details=InferenceStep(
                                step_id="step-end",
                                step_type="inference",
                                turn_id="turn-end",
                                model_response=CompletionMessage(
                                    content="done", role="assistant", stop_reason="end_of_turn"
                                ),
                            ),
                        )
                    case "error":
                        return AgentTurnResponseStepCompletePayload(
                            event_type="step_complete",
                            step_id="step-error",
                            step_type="inference",
                            step_details=InferenceStep(
                                step_id="step-end",
                                step_type="inference",
                                turn_id="turn-end",
                                model_response=CompletionMessage(
                                    content="done", role="assistant", stop_reason="end_of_turn"
                                ),
                            ),
                        )
                    case "tool_call":
                        payload = data["data"]
                        _tool_call = payload.get("tool_call")
                        _tool_calls = payload.get("tool_calls")
                        if isinstance(_tool_call, str):
                            return AgentTurnResponseStepProgressPayload(
                                event_type="step_progress",
                                step_id=f"step-{payload['id']}",
                                step_type="tool_execution",
                                delta=ToolCallDelta(
                                    parse_status="in_progress",
                                    tool_call=_tool_call,
                                    type="tool_call",
                                ),
                            )
                        elif not _tool_calls:
                            tool_call = ToolCall(
                                arguments=_tool_call["arguments"],
                                call_id=f"call_id-{payload['id']}",
                                tool_name=_tool_call["tool_name"],
                            )
                            return AgentTurnResponseStepProgressPayload(
                                event_type="step_progress",
                                step_id=f"step-{payload['id']}",
                                step_type="tool_execution",
                                delta=ToolCallDelta(
                                    parse_status="in_progress",
                                    tool_call=tool_call,
                                    type="tool_call",
                                ),
                            )
                        else:
                            tool_call = ToolCall(
                                arguments=_tool_calls[0]["arguments"],
                                call_id=f"call_id-{payload['id']}",
                                tool_name=_tool_calls[0]["tool_name"],
                            )
                            tool_responses = []
                            for r in payload["tool_responses"]:
                                content = []
                                for c in r["content"]:
                                    content.append(
                                        {
                                            "text": c["text"],
                                            "type": "text",
                                        }
                                    )
                                tool_responses.append(
                                    ToolResponse(
                                        call_id="call_id",
                                        tool_name=_tool_calls[0]["tool_name"],
                                        content=content,
                                    )
                                )
                            step_details = ToolExecutionStep(
                                step_id=f"step-{payload['id']}",
                                step_type="tool_execution",
                                tool_calls=[tool_call],
                                tool_responses=tool_responses,
                                turn_id="turn-in-progress",
                            )
                            return AgentTurnResponseStepCompletePayload(
                                event_type="step_complete",
                                step_id=f"step-{payload['id']}",
                                step_type="tool_execution",
                                step_details=step_details,
                            )
                    case "turn_complete":
                        payload = data["data"]
                        output_message = CompletionMessage(
                            content=payload["content"], role="assistant", stop_reason="end_of_turn"
                        )
                        turn = Turn(
                            input_messages=[],
                            output_message=output_message,
                            session_id=f"session-{payload['id']}",
                            started_at=datetime.now(),
                            steps=[],
                            turn_id=f"turn-{payload['id']}",
                        )
                        return AgentTurnResponseTurnCompletePayload(
                            event_type="turn_complete",
                            turn=turn,
                        )

            async def __aiter__(self):
                for data in self.stream_data:
                    yield AgentTurnResponseStreamChunk(
                        event=TurnResponseEvent(payload=MyAsyncContextManager._make_payload(data))
                    )

            async def __aenter__(self):
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
            system_prompt="",
            media_type="application/json",
        )

    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_session")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_turn")
    async def test_async_invoke_with_no_error(self, mock_create_turn, mock_create_session):
        mock_create_session.return_value = "session_id"
        mock_create_turn.return_value = self.get_return_value(self.STREAM_DATA)
        async for _ in self.pipeline.async_invoke(self.get_params()):
            pass

    @skip("Error handling is not implemented for llama-stack stream")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_session")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_turn")
    async def test_async_invoke_prompt_too_long(self, mock_create_turn, mock_create_session):
        mock_create_session.return_value = "session_id"
        mock_create_turn.return_value = self.get_return_value(self.STREAM_DATA_PROMPT_TOO_LONG)
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("Prompt is too long", log)

    @skip("Error handling is not implemented for llama-stack stream")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_session")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_turn")
    async def test_async_invoke_prompt_generic_llm_error(
        self, mock_create_turn, mock_create_session
    ):
        mock_create_session.return_value = "session_id"
        mock_create_turn.return_value = self.get_return_value(
            self.STREAM_DATA_PROMPT_GENERIC_LLM_ERROR
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("Oops, something went wrong during LLM invocation", log)

    @skip("Error handling is not implemented for llama-stack stream")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_session")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_turn")
    async def test_async_invoke_internal_server_error(self, mock_create_turn, mock_create_session):
        mock_create_session.return_value = "session_id"
        mock_create_turn.return_value = self.get_return_value(
            self.STREAM_DATA_PROMPT_GENERIC_LLM_ERROR, 500
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("Streaming query API returned status code=500", log)

    @skip("Error handling is not implemented for llama-stack stream")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_session")
    @patch("llama_stack_client.lib.agents.agent.AsyncAgent.create_turn")
    async def test_async_invoke_error_with_no_data(self, mock_create_turn, mock_create_session):
        mock_create_session.return_value = "session_id"
        mock_create_turn.return_value = self.get_return_value(
            self.STREAM_DATA_PROMPT_ERROR_WITH_NO_DATA,
        )
        with self.assertLogs(logger="root", level="ERROR") as log:
            async for _ in self.pipeline.async_invoke(self.get_params()):
                pass
            self.assertInLog("(not provided)", log)


class TestGraniteToolParser(TestCase):

    def test_get_parser(self):
        parser = GraniteToolParser.get_parser("somemodel")
        self.assertIsNone(parser)
        parser = GraniteToolParser.get_parser("granite-8b")
        self.assertIsInstance(parser, GraniteToolParser)

    def test_get_tool_calls(self):
        tool_call = ToolCall(
            call_id="ABC",
            tool_name="knowledge_search",
            arguments={"query": "EDA in Ansible"},
        )
        output_message_with_tool_call = CompletionMessage(
            content="done", role="assistant", stop_reason="end_of_turn", tool_calls=[tool_call]
        )
        output_message_without_tool_call = CompletionMessage(
            content="done", role="assistant", stop_reason="end_of_turn", tool_calls=[]
        )
        parser = GraniteToolParser.get_parser("granite-8b")

        tool_calls = parser.get_tool_calls(None)
        self.assertEqual(len(tool_calls), 0)

        tool_calls = parser.get_tool_calls(output_message_without_tool_call)
        self.assertEqual(len(tool_calls), 0)

        tool_calls = parser.get_tool_calls(output_message_with_tool_call)
        self.assertEqual(len(tool_calls), 1)
        self.assertEqual(tool_calls[0], tool_call)
