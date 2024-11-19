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

import requests
from health_check.exceptions import ServiceUnavailable

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.formatter import get_task_names_from_prompt
from ansible_ai_connect.ai.api.model_pipelines.http.configuration import (
    HttpConfiguration,
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


@Register(api_type="http")
class HttpMetaData(MetaData[HttpConfiguration]):

    def __init__(self, config: HttpConfiguration):
        super().__init__(config=config)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}
        i = self.config.timeout
        self._timeout = int(i) if i is not None else None

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None


@Register(api_type="http")
class HttpCompletionsPipeline(HttpMetaData, ModelPipelineCompletions[HttpConfiguration]):

    def __init__(self, config: HttpConfiguration):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        request = params.request
        model_id = params.model_id
        model_input = params.model_input
        model_id = self.get_model_id(request.user, None, model_id)
        self._prediction_url = f"{self.config.inference_url}/predictions/{model_id}"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")

        try:
            task_count = len(get_task_names_from_prompt(prompt))
            result = self.session.post(
                self._prediction_url,
                headers=self.headers,
                json=model_input,
                timeout=self.timeout(task_count),
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
            res = requests.get(url, verify=True)
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
