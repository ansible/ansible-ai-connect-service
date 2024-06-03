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
from django.conf import settings
from health_check.exceptions import ServiceUnavailable

from ansible_ai_connect.ai.api.formatter import get_task_names_from_prompt
from ansible_ai_connect.healthcheck.backends import (
    ERROR_MESSAGE,
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
    HealthCheckSummaryException,
)

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError
from .grpc_pb import ansiblerequest_pb2, wisdomextservice_pb2_grpc

logger = logging.getLogger(__name__)


class GrpcClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self._inference_stub = self.get_inference_stub()

    def get_inference_stub(self) -> wisdomextservice_pb2_grpc.WisdomExtServiceStub:
        logger.debug("Inference URL: " + self._inference_url)
        channel = grpc.insecure_channel(self._inference_url)
        stub = wisdomextservice_pb2_grpc.WisdomExtServiceStub(channel)
        logger.debug("Inference Stub: " + str(stub))
        return stub

    def set_inference_url(self, inference_url):
        super().set_inference_url(inference_url=inference_url)
        self._inference_stub = self.get_inference_stub()

    def infer(self, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        model_id = self.get_model_id(None, model_id)
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
            result: Dict[str, Any] = {"predictions": [response.text], 'model_id': model_id}
            return result
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.DEADLINE_EXCEEDED:  # type: ignore
                raise ModelTimeoutError
            else:
                logger.error(f"gRPC client error: {exc.details()}")  # type: ignore
                raise

    def self_test(self) -> HealthCheckSummary:
        url = (
            f'{settings.ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PROTOCOL}://'
            f'{settings.ANSIBLE_AI_MODEL_MESH_HOST}:'
            f'{settings.ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PORT}/oauth/healthz'
        )
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: settings.ANSIBLE_AI_MODEL_MESH_API_TYPE,
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
        try:
            # As of today (2023-03-27) SSL Certificate Verification fails with
            # the gRPC model server in the Staging environment.  The verify
            # option in the following line is just TEMPORARY and will be removed
            # as soon as the certificate is replaced with a valid one.
            verify = False
            res = requests.get(url, verify=verify)
            res.raise_for_status()
        except Exception as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(ServiceUnavailable(ERROR_MESSAGE), e),
            )
        return summary
