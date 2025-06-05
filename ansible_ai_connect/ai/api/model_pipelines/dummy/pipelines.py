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
import secrets
import time

import requests

from ansible_ai_connect.ai.api.model_pipelines.dummy.configuration import (
    DummyConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    DUMMY_EXPLANATION,
    DUMMY_PLAYBOOK,
    DUMMY_PLAYBOOK_OUTLINE,
    DUMMY_ROLE_EXPLANATION,
    DUMMY_ROLE_FILES,
    DUMMY_ROLE_OUTLINE,
    CompletionsParameters,
    CompletionsResponse,
    MetaData,
    ModelPipelineCompletions,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleExplanationParameters,
    RoleExplanationResponse,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)

logger = logging.getLogger(__name__)


@Register(api_type="dummy")
class DummyMetaData(MetaData[DummyConfiguration]):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}


@Register(api_type="dummy")
class DummyCompletionsPipeline(DummyMetaData, ModelPipelineCompletions[DummyConfiguration]):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        logger.debug("!!!! ModelPipelineCompletions.provider == 'dummy' !!!!")
        logger.debug("!!!! Mocking Model response !!!!")
        if self.config.latency_use_jitter:
            jitter: float = secrets.randbelow(1000) * 0.001
        else:
            jitter: float = 0.001
        time.sleep(self.config.latency_max_msec * jitter)
        response_body = json.loads(self.config.body)
        response_body["model_id"] = "_"
        return response_body

    def infer_from_parameters(self, model_id, context, prompt, suggestion_id=None, headers=None):
        raise NotImplementedError

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


@Register(api_type="dummy")
class DummyPlaybookGenerationPipeline(
    DummyMetaData, ModelPipelinePlaybookGeneration[DummyConfiguration]
):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        create_outline = params.create_outline
        return DUMMY_PLAYBOOK, DUMMY_PLAYBOOK_OUTLINE.strip() if create_outline else "", []

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


@Register(api_type="dummy")
class DummyRoleGenerationPipeline(DummyMetaData, ModelPipelineRoleGeneration[DummyConfiguration]):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        create_outline = params.create_outline
        return (
            "install_nginx",
            DUMMY_ROLE_FILES,
            DUMMY_ROLE_OUTLINE.strip() if create_outline else "",
            [],
        )

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


@Register(api_type="dummy")
class DummyPlaybookExplanationPipeline(
    DummyMetaData, ModelPipelinePlaybookExplanation[DummyConfiguration]
):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        return DUMMY_EXPLANATION

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


@Register(api_type="dummy")
class DummyRoleExplanationPipeline(DummyMetaData, ModelPipelineRoleExplanation[DummyConfiguration]):

    def __init__(self, config: DummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleExplanationParameters) -> RoleExplanationResponse:
        return DUMMY_ROLE_EXPLANATION

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
