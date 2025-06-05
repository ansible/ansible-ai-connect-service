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
from ansible_ai_connect.ai.api.exceptions import FeatureNotAvailable
from ansible_ai_connect.ai.api.model_pipelines.nop.configuration import NopConfiguration
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ChatBotParameters,
    ChatBotResponse,
    CompletionsParameters,
    CompletionsResponse,
    ContentMatchParameters,
    ContentMatchResponse,
    MetaData,
    ModelPipelineChatBot,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    ModelPipelineStreamingChatBot,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleExplanationParameters,
    RoleExplanationResponse,
    RoleGenerationParameters,
    RoleGenerationResponse,
    StreamingChatBotParameters,
    StreamingChatBotResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)


@Register(api_type="nop")
class NopMetaData(MetaData[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)


@Register(api_type="nop")
class NopCompletionsPipeline(NopMetaData, ModelPipelineCompletions[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        raise FeatureNotAvailable

    def infer_from_parameters(self, model_id, context, prompt, suggestion_id=None, headers=None):
        raise NotImplementedError

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="nop")
class NopContentMatchPipeline(NopMetaData, ModelPipelineContentMatch[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: ContentMatchParameters) -> ContentMatchResponse:
        raise FeatureNotAvailable

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="nop")
class NopPlaybookGenerationPipeline(NopMetaData, ModelPipelinePlaybookGeneration[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        raise FeatureNotAvailable

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="nop")
class NopRoleGenerationPipeline(NopMetaData, ModelPipelineRoleGeneration[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        raise FeatureNotAvailable

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="nop")
class NopPlaybookExplanationPipeline(
    NopMetaData, ModelPipelinePlaybookExplanation[NopConfiguration]
):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        raise FeatureNotAvailable

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="nop")
class NopRoleExplanationPipeline(NopMetaData, ModelPipelineRoleExplanation[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleExplanationParameters) -> RoleExplanationResponse:
        raise FeatureNotAvailable

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="nop")
class NopChatBotPipeline(NopMetaData, ModelPipelineChatBot[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: ChatBotParameters) -> ChatBotResponse:
        raise FeatureNotAvailable

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="nop")
class NopStreamingChatBotPipeline(NopMetaData, ModelPipelineStreamingChatBot[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: StreamingChatBotParameters) -> StreamingChatBotResponse:
        raise FeatureNotAvailable

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "nop",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )
