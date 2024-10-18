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
from abc import ABCMeta
from typing import TYPE_CHECKING, Optional

from ansible_ai_connect.ai.api.model_pipelines.exceptions import WcaTokenFailure
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    ContentMatchParameters,
    ContentMatchResponse,
    MetaData,
    ModelPipeline,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register

if TYPE_CHECKING:
    from ansible_ai_connect.users.models import User
else:
    User = None

logger = logging.getLogger(__name__)


@Register(api_type="wca-dummy")
class WCADummyMetaData(MetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_model_id(
        self,
        user: User,
        organization_id: Optional[int] = None,
        requested_model_id: Optional[str] = None,
    ) -> str:
        return requested_model_id or ""

    def get_token(self, api_key) -> str:
        if api_key != "valid":
            raise WcaTokenFailure("I'm a fake WCA client and the only api_key I accept is 'valid'")
        return ""


@Register(api_type="wca-dummy")
class WCADummyPipeline(ModelPipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)


@Register(api_type="wca-dummy")
class WCADummyCompletionsPipeline(WCADummyPipeline, ModelPipelineCompletions):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        return {
            "model_id": "mocked_wca_client",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }

    def infer_from_parameters(self, *args, **kwargs):
        return ""


@Register(api_type="wca-dummy")
class WCADummyContentMatchPipeline(WCADummyPipeline, ModelPipelineContentMatch):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: ContentMatchParameters) -> ContentMatchResponse:
        raise NotImplementedError


@Register(api_type="wca-dummy")
class WCADummyPlaybookGenerationPipeline(WCADummyPipeline, ModelPipelinePlaybookGeneration):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        raise NotImplementedError


@Register(api_type="wca-dummy")
class WCADummyPlaybookExplanationPipeline(WCADummyPipeline, ModelPipelinePlaybookExplanation):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        raise NotImplementedError
