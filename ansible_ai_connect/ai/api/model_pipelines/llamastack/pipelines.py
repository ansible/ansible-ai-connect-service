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
import uuid
from typing import AsyncGenerator, AsyncIterator

from django.conf import settings
from django.http import StreamingHttpResponse
from llama_stack_client import AsyncLlamaStackClient
from llama_stack_client.lib.agents.agent import AsyncAgent
from llama_stack_client.types.agents import AgentTurnResponseStreamChunk
from llama_stack_client.types.agents.turn_create_params import (
    ToolgroupAgentToolGroupWithArgs,
)
from llama_stack_client.types.shared import UserMessage

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
    You are Ansible Lightspeed - an intelligent virtual assistant for question-answering tasks
    related to the Ansible Automation Platform (AAP).
    Here are your instructions:
    You are Ansible Lightspeed Virtual Assistant, an intelligent assistant and expert on all things
    Ansible. Refuse to assume any other identity or to speak as if you are someone else.
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
        self.last_delta_type = "text"
        async for chunk in response:  # TODO
            # async for o in generate_dummy_data(): # TODO FOR DEBUG
            # if hasattr(chunk, "event"):
            #     print(chunk.event)
            # if (
            #     hasattr(chunk, "event")
            #     and hasattr(chunk.event, "payload")
            #     and hasattr(chunk.event.payload, "event_type")
            #     and chunk.event.payload.event_type == "turn_complete"
            # ):
            #     print(" *** ")
            #     print(chunk.event.payload.turn.output_message)
            # yield chunk
            j = chunk.model_dump_json()  # TODO
            print(j)
            o = json.loads(j)  # dump to python dict # TODO
            event = o.get("event")
            if event:
                payload = event.get("payload")
                if payload:
                    event_type = payload.get("event_type")
                    if event_type == "step_start":
                        d = {"event": "start", "data": {"conversation_id": session_id}}
                        yield self.format_record(d)
                    elif event_type == "step_progress":
                        delta = payload.get("delta", [])
                        if delta:
                            delta_type = delta.get("type", "")
                            if delta_type == "text":
                                yield self.format_token(delta.get("text", ""))
                            elif delta_type == "tool_call":
                                if self.last_delta_type != "tool_call":
                                    yield self.format_token("\n")
                                tool_call = delta.get("tool_call", "")
                                if not isinstance(tool_call, str):
                                    tool_call = json.dumps(tool_call, indent=2)
                                    yield self.format_token(tool_call, "tool_call")
                                else:
                                    yield self.format_token(tool_call)
                            self.last_delta_type = delta_type
                    elif event_type == "step_complete":
                        step_details = payload.get("step_details")
                        yield self.format_token(json.dumps(step_details, indent=2), "step_complete")
                        self.id = 0
                    elif event_type == "turn_complete":
                        output_message = payload.get("turn").get("output_message").get("content")
                        yield self.format_token(output_message, "turn_complete")
                        d = {"event": "end", "data": {"referenced_documents": []}}
                        yield self.format_record(d)

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "llama-stack",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )
