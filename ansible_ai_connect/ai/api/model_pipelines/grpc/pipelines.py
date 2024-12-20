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
from typing import Any, Dict

import grpc
import requests
from health_check.exceptions import ServiceUnavailable

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.formatter import get_task_names_from_prompt
from ansible_ai_connect.ai.api.model_pipelines.grpc.configuration import (
    GrpcConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.grpc.grpc_pb import (
    ansiblerequest_pb2,
    wisdomextservice_pb2_grpc,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    MetaData,
    ModelPipelineCompletions,
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


@Register(api_type="grpc")
class GrpcMetaData(MetaData[GrpcConfiguration]):

    def __init__(self, config: GrpcConfiguration):
        super().__init__(config=config)
        i = self.config.timeout
        self._timeout = int(i) if i is not None else None

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None


@Register(api_type="grpc")
class GrpcCompletionsPipeline(GrpcMetaData, ModelPipelineCompletions[GrpcConfiguration]):

    def __init__(self, config: GrpcConfiguration):
        super().__init__(config=config)
        self._inference_stub = self.get_inference_stub()

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        request = params.request
        model_id = params.model_id
        model_input = params.model_input
        model_id = self.get_model_id(request.user, None, model_id)
        logger.debug(f"Input prompt: {model_input}")
        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")
        logger.debug(f"Input prompt: {prompt}")
        logger.debug(f"Input context: {context}")

        try:
            task_count = len(get_task_names_from_prompt(prompt))
            response = self._inference_stub.AnsiblePredict(
                request=ansiblerequest_pb2.AnsibleRequest(  # type: ignore
                    prompt=prompt, context=context
                ),
                metadata=[("mm-vmodel-id", model_id)],
                timeout=self.timeout(task_count),
            )

            logger.debug(f"inference response: {response}")
            logger.debug(f"inference response: {response.text}")
            result: Dict[str, Any] = {"predictions": [response.text], "model_id": model_id}
            return result
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:  # type: ignore
                raise ModelTimeoutError
            else:
                logger.error(f"gRPC client error: {exc.details()}")  # type: ignore
                raise

    def get_inference_stub(self) -> wisdomextservice_pb2_grpc.WisdomExtServiceStub:
        channel = grpc.insecure_channel(self.config.inference_url)
        stub = wisdomextservice_pb2_grpc.WisdomExtServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def set_inference_url(self, inference_url):
        self.config.inference_url = inference_url
        self._inference_stub = self.get_inference_stub()

    def self_test(self) -> HealthCheckSummary:
        url = f"{self.config.health_check_url}/oauth/healthz"
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "grpc",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
        try:
            res = requests.get(url)
            res.raise_for_status()
        except Exception as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(ServiceUnavailable(ERROR_MESSAGE), e),
            )
        return summary

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError
