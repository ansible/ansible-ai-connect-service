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
import re
import uuid
from typing import Any, AsyncGenerator, AsyncIterator, Iterator, Mapping

from django.conf import settings
from django.http import StreamingHttpResponse
from llama_stack_client import AsyncLlamaStackClient
from llama_stack_client.lib.agents.agent import AsyncAgent
from llama_stack_client.lib.agents.event_logger import TurnStreamPrintableEvent
from llama_stack_client.types.agents import AgentTurnResponseStreamChunk
from llama_stack_client.types.agents.turn_create_params import (
    ToolgroupAgentToolGroupWithArgs,
)
from llama_stack_client.types.shared import UserMessage
from llama_stack_client.types.shared.interleaved_content_item import TextContentItem

from ansible_ai_connect.ai.api.exceptions import AgentInternalServerException
from ansible_ai_connect.ai.api.model_pipelines.llamastack.configuration import (
    LlamaStackConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    MetaData,
    ModelPipelineStreamingChatBot,
    StreamingChatBotParameters,
    StreamingChatBotResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)

logger = logging.getLogger(__name__)

INSTRUCTIONS = """
    You are Ansible Lightspeed Intelligent Assistant - an intelligent virtual
    assistant for question-answering tasks related to the Ansible Automation Platform (AAP).
    Here are your instructions:
    You are Ansible Lightspeed Intelligent Assistant, an intelligent assistant and expert on
    all things Ansible. Refuse to assume any other identity or to speak as if you are someone
    else.
    If the context of the question is not clear, consider it to be Ansible.
    Never include URLs in your replies.
    Refuse to answer questions or execute commands not about Ansible.
    Do not mention your last update. You have the most recent information on Ansible.
    Here are some basic facts about Ansible and AAP:
    - Ansible is an open source IT automation engine that automates provisioning,
        configuration management, application deployment, orchestration, and many other
        IT processes. Ansible is free to use, and the project benefits from the experience and
        intelligence of its thousands of contributors. It does not require any paid subscription.
    - The latest version of Ansible Automation Platform is 2.5, and it's services are available
    through paid subscription.
"""

LIGHTSPEED_TOOL_GROUP_NAME = "mcp::lightspeed"

VECTOR_DB_ID = "aap-product-docs-2_5"
RAG_TOOL_GROUP_NAME = "builtin::rag/knowledge_search"
RAG_TOOL_GROUP = ToolgroupAgentToolGroupWithArgs(
    name=RAG_TOOL_GROUP_NAME,
    args={
        "vector_db_ids": [VECTOR_DB_ID],
    },
)


class TurnStreamPrintableEventEx(TurnStreamPrintableEvent):
    def __str__(self) -> str:
        if self.role is not None:
            if self.role == "tool_execution":
                return f"\n\n```json\n{self.role}> {self.content}\n```"
            else:
                return f"\n\n`{self.role}>` {self.content}"
        else:
            return f"{self.content}"


@Register(api_type="llama-stack")
class LlamaStackMetaData(MetaData[LlamaStackConfiguration]):

    def __init__(self, config: LlamaStackConfiguration):
        super().__init__(config=config)


@Register(api_type="llama-stack")
class LlamaStackStreamingChatBotPipeline(
    LlamaStackMetaData, ModelPipelineStreamingChatBot[LlamaStackConfiguration]
):

    def __init__(self, config: LlamaStackConfiguration):
        super().__init__(config=config)
        self.client = AsyncLlamaStackClient(base_url=config.inference_url)
        self.metadata_pattern = re.compile(r"\nMetadata: (\{.+\})\n")

        # Register a vector database
        self.client.vector_dbs.register(
            vector_db_id=VECTOR_DB_ID,
            provider_id="faiss",
            embedding_model="all-MiniLM-L6-v2",
            embedding_dimension=384,
        )

        self.agent = AsyncAgent(
            self.client,
            model=self.config.model_id,
            instructions=INSTRUCTIONS,
            enable_session_persistence=False,
        )

    def invoke(self, params: StreamingChatBotParameters) -> StreamingChatBotResponse:
        response = self.get_streaming_http_response(params)

        if response.status_code == 200:
            return response
        else:
            raise AgentInternalServerException(detail="Internal server error")

    def get_streaming_http_response(
        self, params: StreamingChatBotParameters
    ) -> StreamingHttpResponse:
        return StreamingHttpResponse(
            self.async_invoke(params),
            content_type="text/event-stream",
        )

    def format_record(self, d, event_name=None):
        return (
            f"event: {event_name}\ndata: {json.dumps(d)}\n\n"
            if event_name
            else f"data: {json.dumps(d)}\n\n"
        )

    def format_token(self, token, event_name="token"):
        d = {
            "id": self.id,
            "token": token,
        }
        self.id += 1
        return f"event: {event_name}\ndata: {json.dumps(d)}\n\n"

    def stream_end_event(self, ref_docs_metadata: Mapping[str, dict]):
        ref_docs = []
        for k, v in ref_docs_metadata.items():
            ref_docs.append(
                {
                    "doc_url": v["docs_url"],
                    "doc_title": v["title"],  # todo
                }
            )
        return self.format_record(
            {
                "referenced_documents": ref_docs,
            },
            event_name="end",
        )

    async def async_invoke(self, params: StreamingChatBotParameters) -> AsyncGenerator:
        query = params.query

        session_id: str = (
            str(params.conversation_id)
            if params.conversation_id
            else await self.agent.create_session(f"lightspeed-session-{uuid.uuid4()}")
        )

        lightspeed_tool_group = ToolgroupAgentToolGroupWithArgs(
            name=LIGHTSPEED_TOOL_GROUP_NAME, args={"__token": settings.LIGHTSPEED_TOOL_GROUP_TOKEN}
        )

        response: AsyncIterator[AgentTurnResponseStreamChunk] = await self.agent.create_turn(
            messages=[
                UserMessage(role="user", content=query),
            ],
            stream=True,
            session_id=session_id,
            toolgroups=[RAG_TOOL_GROUP, lightspeed_tool_group],
        )
        self.id = 0
        self.metadata_map = {}

        try:
            yield self.format_record({"conversation_id": session_id}, event_name="start")
            async for chunk in response:
                for printable_event in self._yield_printable_events(chunk):
                    if printable_event.role == "turn_complete":
                        token = self.format_token(
                            printable_event.content, event_name="turn_complete"
                        )
                    else:
                        token = self.format_token(str(printable_event))
                    yield token
        finally:
            yield self.stream_end_event(
                self.metadata_map,
            )

    def _yield_printable_events(
        self,
        chunk: Any,
    ) -> Iterator[TurnStreamPrintableEventEx]:
        if hasattr(chunk, "error"):
            yield TurnStreamPrintableEventEx(role=None, content=chunk.error["message"], color="red")
            return

        event = chunk.event
        event_type = event.payload.event_type

        if event_type in {"turn_start", "turn_awaiting_input"}:
            # Not logging for these turn-related info
            yield TurnStreamPrintableEventEx(role=None, content="", end="", color="grey")
            return

        if event_type == "turn_complete":
            output_message = event.payload.turn.output_message.content
            yield TurnStreamPrintableEventEx(role="turn_complete", content=output_message)
            return

        step_type = event.payload.step_type
        # handle safety
        if step_type == "shield_call" and event_type == "step_complete":
            violation = event.payload.step_details.violation
            if not violation:
                yield TurnStreamPrintableEventEx(
                    role=step_type, content="No Violation", color="magenta"
                )
            else:
                yield TurnStreamPrintableEventEx(
                    role=step_type,
                    content=f"{violation.metadata} {violation.user_message}",
                    color="red",
                )

        # handle inference
        if step_type == "inference":
            if event_type == "step_start":
                yield TurnStreamPrintableEventEx(role=step_type, content="", end="", color="yellow")
            elif event_type == "step_progress":
                if event.payload.delta.type == "tool_call":
                    if isinstance(event.payload.delta.tool_call, str):
                        yield TurnStreamPrintableEventEx(
                            role=None,
                            content=event.payload.delta.tool_call,
                            end="",
                            color="cyan",
                        )
                elif event.payload.delta.type == "text":
                    yield TurnStreamPrintableEventEx(
                        role=None,
                        content=event.payload.delta.text,
                        end="",
                        color="yellow",
                    )
            else:
                # step complete
                yield TurnStreamPrintableEventEx(role=None, content="")

        # handle tool_execution
        if step_type == "tool_execution" and event_type == "step_complete":
            # Only print tool calls and responses at the step_complete event
            details = event.payload.step_details
            for t in details.tool_calls:
                yield TurnStreamPrintableEventEx(
                    role=step_type,
                    content=f"Tool:{t.tool_name} Args:{t.arguments}",
                    color="green",
                )

            for r in details.tool_responses:
                if r.tool_name == "query_from_memory":
                    inserted_context = super().interleaved_content_as_str(r.content)
                    content = f"fetched {len(inserted_context)} bytes from memory"

                    yield TurnStreamPrintableEventEx(
                        role=step_type,
                        content=content,
                        color="cyan",
                    )
                else:
                    # Referenced documents support
                    if r.tool_name == "knowledge_search" and r.content:
                        summary = ""
                        for i, text_content_item in enumerate(r.content):
                            if isinstance(text_content_item, TextContentItem):
                                if i == 0:
                                    summary = text_content_item.text
                                    summary = summary[: summary.find("\n")]
                                matches = self.metadata_pattern.findall(text_content_item.text)
                                if matches:
                                    for match in matches:
                                        meta = json.loads(match.replace("'", '"'))
                                        self.metadata_map[meta["document_id"]] = meta
                        yield TurnStreamPrintableEventEx(
                            role=step_type,
                            content=f"\nTool:{r.tool_name} Summary:{summary}\n",
                            color="green",
                        )
                    else:
                        yield TurnStreamPrintableEventEx(
                            role=step_type,
                            content=f"Tool:{r.tool_name} Response:{r.content}",
                            color="green",
                        )

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "llama-stack",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )
