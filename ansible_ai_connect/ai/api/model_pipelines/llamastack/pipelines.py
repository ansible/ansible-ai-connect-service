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
import re
import uuid
from typing import Any, AsyncGenerator, AsyncIterator, Iterator, Mapping

from django.conf import settings
from django.http import StreamingHttpResponse
from health_check.exceptions import ServiceUnavailable
from llama_stack_client import AsyncLlamaStackClient
from llama_stack_client import LlamaStackClient
from llama_stack_client import BadRequestError
from llama_stack_client.lib.agents.agent import AsyncAgent
from llama_stack_client.lib.agents.event_logger import TurnStreamPrintableEvent
from llama_stack_client.types.agents import AgentTurnResponseStreamChunk
from llama_stack_client.types.agents.turn_create_params import (
    ToolgroupAgentToolGroupWithArgs,
)
from llama_stack_client.types.shared import UserMessage
from llama_stack_client.types.shared.interleaved_content_item import TextContentItem

from ansible_ai_connect.ai.api.exceptions import (
    AgentInternalServerException,
    ChatbotForbiddenException,
    ChatbotInternalServerException,
    ChatbotPromptTooLongException,
    ChatbotUnauthorizedException,
    ChatbotValidationException,
)
from ansible_ai_connect.ai.api.model_pipelines.llamastack.configuration import (
    LlamaStackConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ChatBotParameters,
    ChatBotResponse,
    MetaData,
    ModelPipelineChatBot,
    ModelPipelineStreamingChatBot,
    StreamingChatBotParameters,
    StreamingChatBotResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
    HealthCheckSummaryException,
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
LLAMA_STACK_PROVIDER_HEALTH = "provider_id"
LLAMA_STACK_PROVIDER_ID = os.getenv("LLAMA_STACK_PROVIDER_ID", "vllm-inference")


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

    def self_test(self) -> HealthCheckSummary:
        """
        Perform a self-test to check the health of the LlamaStack provider.
        Returns:
            HealthCheckSummary: A summary of the health check results.
        """
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "llama-stack",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
        try:
            client = LlamaStackClient(base_url=self.config.inference_url)
            response = client.providers.retrieve(LLAMA_STACK_PROVIDER_ID)
            health_status = response.health.get("status")
            if health_status != "OK":
                reason = (
                    f"Provider {LLAMA_STACK_PROVIDER_ID} health status: {health_status}"
                )
                summary.add_exception(
                    MODEL_MESH_HEALTH_CHECK_MODELS,
                    HealthCheckSummaryException(ServiceUnavailable(reason)),
                )
        except BadRequestError as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(ServiceUnavailable(str(e)), e),
            )
        except Exception as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(ServiceUnavailable(str(e)), e),
            )

        return summary


@Register(api_type="llama-stack")
class LlamaStackChatBotPipeline(LlamaStackMetaData, ModelPipelineChatBot[LlamaStackConfiguration]):
    def __init__(self, config: LlamaStackConfiguration):
        super().__init__(config=config)

    def invoke(self, params: ChatBotParameters) -> ChatBotResponse:
        query = params.query
        conversation_id = params.conversation_id
        provider = params.provider
        model_id = params.model_id
        system_prompt = params.system_prompt

        # Initialize the LlamaStackClient with the base URL from config
        client = LlamaStackClient(base_url=self.config.inference_url)
        try:
            if system_prompt:
                # Prepend the system prompt to the user query
                prompt_text = f"System: {system_prompt}\nUser: {query}"
            else:
                prompt_text = query
            if provider:
                model_name = f"{provider}/{model_id}"
            else:
                model_name = model_id
            # For conversation_id, we can't pass it directly to completions.create
            if conversation_id:
                logger.info("Using conversation ID: %s", conversation_id)

            response = client.completions.create(
                model=model_name,
                prompt=prompt_text
            )
            return response
        except BadRequestError as e:
            # Handle specific errors based on the error code or message
            if "401" in str(e):
                raise ChatbotUnauthorizedException(detail=str(e))
            elif "403" in str(e):
                raise ChatbotForbiddenException(detail=str(e))
            elif "413" in str(e):
                raise ChatbotPromptTooLongException(detail=str(e))
            elif "422" in str(e):
                raise ChatbotValidationException(detail=str(e))
            else:
                raise ChatbotInternalServerException(detail=str(e))


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
        """
        Returns a StreamingHttpResponse for the given parameters.
        :param params: StreamingChatBotParameters containing the query and conversation_id.
        :return: StreamingHttpResponse that streams the response from the agent."""
        return StreamingHttpResponse(
            self.async_invoke(params),
            content_type="text/event-stream",
        )

    def format_record(self, d, event_name=None):
        """
        Formats a record as a string for streaming.
        :param d: The data to format.
        :param event_name: The name of the event, if any.
        :return: A formatted string for the record.
        """
        return (
            f"event: {event_name}\ndata: {json.dumps(d)}\n\n"
            if event_name
            else f"data: {json.dumps(d)}\n\n"
        )

    def format_token(self, token, event_name="token"):
        """
        Formats a token for streaming.
        :param token: The token to format.
        :param event_name: The name of the event, defaults to "token".
        :return: A formatted string for the token.
        """
        d = {
            "id": self.id,
            "token": token,
        }
        self.id += 1
        return f"event: {event_name}\ndata: {json.dumps(d)}\n\n"

    def stream_end_event(self, ref_docs_metadata: Mapping[str, dict]):
        """
        Formats the end event for the stream, including referenced documents.
        :param ref_docs_metadata: A mapping of document IDs to their metadata.
        :return: A formatted string for the end event.
        """
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
        """
        Asynchronously invokes the agent with the given parameters and yields the response.
        :param params: StreamingChatBotParameters containing the query and conversation_id.
        :return: An AsyncGenerator that yields formatted tokens or events.
        """
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
