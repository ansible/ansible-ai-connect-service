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
from ansible_ai_connect.ai.api.model_pipelines.nop.configuration import NopConfiguration
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    ContentMatchParameters,
    ContentMatchResponse,
    MetaData,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register


@Register(api_type="nop")
class NopMetaData(MetaData[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)


@Register(api_type="nop")
class NopCompletionsPipeline(NopMetaData, ModelPipelineCompletions[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        raise NotImplementedError

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError

    def self_test(self):
        raise NotImplementedError


@Register(api_type="nop")
class NopContentMatchPipeline(NopMetaData, ModelPipelineContentMatch[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: ContentMatchParameters) -> ContentMatchResponse:
        raise NotImplementedError

    def self_test(self):
        raise NotImplementedError


@Register(api_type="nop")
class NopPlaybookGenerationPipeline(NopMetaData, ModelPipelinePlaybookGeneration[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        raise NotImplementedError

    def self_test(self):
        raise NotImplementedError


@Register(api_type="nop")
class NopRoleGenerationPipeline(NopMetaData, ModelPipelineRoleGeneration[NopConfiguration]):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        raise NotImplementedError

    def self_test(self):
        raise NotImplementedError


@Register(api_type="nop")
class NopPlaybookExplanationPipeline(
    NopMetaData, ModelPipelinePlaybookExplanation[NopConfiguration]
):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        raise NotImplementedError

    def self_test(self):
        raise NotImplementedError
