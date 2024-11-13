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
class NopMetaData(MetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)


@Register(api_type="nop")
class NopCompletionsPipeline(NopMetaData, ModelPipelineCompletions):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        raise NotImplementedError

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


@Register(api_type="nop")
class NopContentMatchPipeline(NopMetaData, ModelPipelineContentMatch):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: ContentMatchParameters) -> ContentMatchResponse:
        raise NotImplementedError


@Register(api_type="nop")
class NopPlaybookGenerationPipeline(NopMetaData, ModelPipelinePlaybookGeneration):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        raise NotImplementedError


@Register(api_type="nop")
class NopRoleGenerationPipeline(NopMetaData, ModelPipelineRoleGeneration):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        raise NotImplementedError


@Register(api_type="nop")
class NopPlaybookExplanationPipeline(NopMetaData, ModelPipelinePlaybookExplanation):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        raise NotImplementedError
