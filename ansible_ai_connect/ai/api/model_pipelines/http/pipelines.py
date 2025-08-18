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

import copy
import json
import logging
from json import JSONDecodeError
from typing import Any, AsyncGenerator

import aiohttp
import requests
from django.conf import settings
from django.http import StreamingHttpResponse
from health_check.exceptions import ServiceUnavailable

from ansible_ai_connect.ai.api.exceptions import (
    ChatbotForbiddenException,
    ChatbotInternalServerException,
    ChatbotPromptTooLongException,
    ChatbotUnauthorizedException,
    ChatbotValidationException,
    ModelTimeoutError,
)
from ansible_ai_connect.ai.api.formatter import get_task_names_from_prompt
from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ChatBotParameters,
    ChatBotResponse,
    CompletionsParameters,
    CompletionsResponse,
    MetaData,
    ModelPipelineChatBot,
    ModelPipelineCompletions,
    ModelPipelineStreamingChatBot,
    StreamingChatBotParameters,
    StreamingChatBotResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.healthcheck.backends import (
    ERROR_MESSAGE,
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
    HealthCheckSummaryException,
)

logger = logging.getLogger(__name__)


@Register(api_type="http")
class HttpMetaData(MetaData[HttpConfiguration]):

    def __init__(self, config: HttpConfiguration):
        super().__init__(config=config)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}
        i = self.config.timeout
        self._timeout = int(i) if i is not None else None

    def task_gen_timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None


@Register(api_type="http")
class HttpCompletionsPipeline(HttpMetaData, ModelPipelineCompletions[HttpConfiguration]):

    def __init__(self, config: HttpConfiguration):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        request = params.request
        model_id = params.model_id
        model_input = params.model_input
        model_id = self.get_model_id(request.user, model_id)
        self._prediction_url = f"{self.config.inference_url}/predictions/{model_id}"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")

        try:
            task_count = len(get_task_names_from_prompt(prompt))
            result = self.session.post(
                self._prediction_url,
                headers=self.headers,
                json=model_input,
                timeout=self.task_gen_timeout(task_count),
                verify=self.config.verify_ssl,
            )
            result.raise_for_status()
            response = json.loads(result.text)
            response["model_id"] = model_id
            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError

    def self_test(self) -> HealthCheckSummary:
        url = f"{self.config.inference_url}/ping"
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "http",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
        try:
            res = requests.get(url, verify=self.config.verify_ssl, timeout=1)
            res.raise_for_status()
        except Exception as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(ServiceUnavailable(ERROR_MESSAGE), e),
            )
        return summary

    def infer_from_parameters(self, model_id, context, prompt, suggestion_id=None, headers=None):
        raise NotImplementedError


class HttpChatBotMetaData(HttpMetaData):

    def __init__(self, config: HttpConfiguration):
        super().__init__(config=config)

    def self_test(self) -> HealthCheckSummary:
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "http",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
        try:
            headers = {"Content-Type": "application/json"}
            r = requests.get(
                self.config.inference_url + "/readiness",
                headers=headers,
                timeout=1,
                verify=self.config.verify_ssl,
            )
            r.raise_for_status()

            data = r.json()
            ready = data.get("ready")
            if not ready:
                reason = data.get("reason")
                summary.add_exception(
                    MODEL_MESH_HEALTH_CHECK_MODELS,
                    HealthCheckSummaryException(ServiceUnavailable(reason)),
                )

        except Exception as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(ServiceUnavailable(ERROR_MESSAGE), e),
            )
        return summary


@Register(api_type="http")
class HttpChatBotPipeline(HttpChatBotMetaData, ModelPipelineChatBot[HttpConfiguration]):

    def __init__(self, config: HttpConfiguration):
        super().__init__(config=config)

    def invoke(self, params: ChatBotParameters) -> ChatBotResponse:
        query = params.query
        conversation_id = params.conversation_id
        provider = params.provider
        model_id = params.model_id
        system_prompt = params.system_prompt or settings.CHATBOT_DEFAULT_SYSTEM_PROMPT
        no_tools = params.no_tools

        data: dict[str, Any] = {
            "query": query,
            "model": model_id,
            "provider": provider,
        }
        if conversation_id:
            data["conversation_id"] = str(conversation_id)
        if system_prompt:
            data["system_prompt"] = str(system_prompt)
        if no_tools:
            data["no_tools"] = bool(no_tools)

        headers = self.headers or {}
        if params.mcp_headers:
            headers["MCP-HEADERS"] = json.dumps(params.mcp_headers)

        response = requests.post(
            self.config.inference_url + "/v1/query",
            headers=self.headers,
            json=data,
            timeout=self.task_gen_timeout(1),
            verify=self.config.verify_ssl,
        )

        if response.status_code == 200:
            data = json.loads(response.text)
            # ChatResponseSerializer requires these fields.
            # lightspeed-stack does not currently return them.
            if "truncated" not in data:
                data["truncated"] = False
            if "referenced_documents" not in data:
                data["referenced_documents"] = []
            return data

        elif response.status_code == 401:
            detail = json.loads(response.text).get("detail", "")
            raise ChatbotUnauthorizedException(detail=detail)
        elif response.status_code == 403:
            detail = json.loads(response.text).get("detail", "")
            raise ChatbotForbiddenException(detail=detail)
        elif response.status_code == 413:
            detail = json.loads(response.text).get("detail", "")
            raise ChatbotPromptTooLongException(detail=detail)
        elif response.status_code == 422:
            detail = json.loads(response.text).get("detail", "")
            raise ChatbotValidationException(detail=detail)
        else:
            detail = json.loads(response.text).get("detail", "")
            raise ChatbotInternalServerException(detail=detail)


@Register(api_type="http")
class HttpStreamingChatBotPipeline(
    HttpChatBotMetaData, ModelPipelineStreamingChatBot[HttpConfiguration]
):

    def __init__(self, config: HttpConfiguration):
        super().__init__(config=config)

    def invoke(self, params: StreamingChatBotParameters) -> StreamingChatBotResponse:
        response = self.get_streaming_http_response(params)

        if response.status_code == 200:
            return response
        else:
            raise ChatbotInternalServerException(detail="Internal server error")

    def get_streaming_http_response(
        self, params: StreamingChatBotParameters
    ) -> StreamingHttpResponse:
        return StreamingHttpResponse(
            self.async_invoke(params),
            content_type="text/event-stream",
        )

    def send_schema1_event(self, ev):
        # Import schema1-related functions/class here to avoid
        # the AppRegistryNotReady exception
        from ansible_ai_connect.ai.api.utils.segment import send_schema1_event

        send_schema1_event(ev)

    async def async_invoke(self, params: StreamingChatBotParameters) -> AsyncGenerator:

        # Configure SSL context based on verify_ssl setting
        ssl_context = self.config.verify_ssl
        connector = aiohttp.TCPConnector(ssl=ssl_context)

        async with aiohttp.ClientSession(raise_for_status=True, connector=connector) as session:
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json,text/event-stream",
            }

            if params.mcp_headers:
                headers["MCP-HEADERS"] = json.dumps(params.mcp_headers)

            query = params.query
            conversation_id = params.conversation_id
            provider = params.provider
            model_id = params.model_id
            system_prompt = params.system_prompt or settings.CHATBOT_DEFAULT_SYSTEM_PROMPT
            media_type = params.media_type
            no_tools = params.no_tools

            data: dict[str, Any] = {
                "query": query,
                "model": model_id,
                "provider": provider,
            }
            if conversation_id:
                data["conversation_id"] = str(conversation_id)
            if system_prompt:
                data["system_prompt"] = str(system_prompt)
            if media_type:
                data["media_type"] = str(media_type)
            if no_tools:
                data["no_tools"] = bool(no_tools)

            async with session.post(
                self.config.inference_url + "/v1/streaming_query",
                json=data,
                headers=headers,
                raise_for_status=False,
            ) as response:
                if response.status == 200:
                    # Import schema1-related functions/class here to avoid
                    # the AppRegistryNotReady exception
                    from ansible_ai_connect.ai.api.telemetry.schema1 import (
                        StreamingChatBotOperationalEvent,
                    )

                    # Initialise Segment Event
                    ev: StreamingChatBotOperationalEvent = copy.copy(params.event)
                    ev.chat_system_prompt = params.system_prompt
                    ev.provider_id = params.provider
                    ev.conversation_id = params.conversation_id
                    ev.modelName = params.model_id
                    ev.no_tools = params.no_tools

                    async for chunk in response.content:
                        try:
                            if chunk:
                                s = chunk.decode("utf-8").strip()
                                if s and s.startswith("data: "):
                                    o = json.loads(s[len("data: ") :])
                                    event = o.get("event")
                                    if event == "error":
                                        default_data = {
                                            "response": "(not provided)",
                                            "cause": "(not provided)",
                                        }
                                        data = o.get("data", default_data)
                                        logger.error(
                                            "An error received in chat streaming content:"
                                            + " response="
                                            + str(data.get("response"))
                                            + ", cause="
                                            + str(data.get("cause"))
                                        )
                                    elif event == "start":
                                        ev.phase = event
                                        default_data = {
                                            "conversation_id": conversation_id,
                                        }
                                        data = o.get("data", default_data)
                                        conversation_id = data.get("conversation_id")
                                        ev.conversation_id = conversation_id
                                        self.send_schema1_event(ev)
                                    elif event == "end":
                                        ev.phase = event
                                        default_data = {
                                            "referenced_documents": [],
                                            "truncated": False,
                                        }
                                        data = o.get("data", default_data)
                                        referenced_documents = []
                                        for doc in data.get("referenced_documents", []):
                                            # Current version of ansible-chatbot-service
                                            # uses incompatible document data structure
                                            # between streaming and non-streaming chats.
                                            # Following is the code to solve that
                                            # incompatibility.
                                            if "doc_title" in doc:
                                                referenced_documents.append(
                                                    {
                                                        "title": doc["doc_title"],
                                                        "docs_url": doc["doc_url"],
                                                    }
                                                )
                                            else:
                                                referenced_documents.append(doc)
                                        truncated = data.get("truncated", False)
                                        ev.conversation_id = conversation_id
                                        ev.chat_referenced_documents = referenced_documents
                                        ev.chat_truncated = truncated
                                        self.send_schema1_event(ev)
                        except JSONDecodeError:
                            pass
                        logger.debug(chunk)
                        yield chunk
                else:
                    logging.error(
                        "Streaming query API returned status code="
                        + str(response.status)
                        + ", reason="
                        + str(response.reason)
                    )
                    error = {
                        "event": "error",
                        "data": {
                            "response": f"Non-200 status code ({response.status}) was received.",
                            "cause": response.reason,
                        },
                    }
                    yield json.dumps(error).encode("utf-8")
                    return
