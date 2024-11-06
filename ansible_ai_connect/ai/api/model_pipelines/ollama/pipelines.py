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

from langchain_community.llms import Ollama

from ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines import (
    LangchainCompletionsPipeline,
    LangchainMetaData,
    LangchainPlaybookExplanationPipeline,
    LangchainPlaybookGenerationPipeline,
    LangchainRoleGenerationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.ollama.configuration import (
    OllamaConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register

logger = logging.getLogger(__name__)


@Register(api_type="ollama")
class OllamaMetaData(LangchainMetaData[OllamaConfiguration]):

    def __init__(self, config: OllamaConfiguration):
        super().__init__(config=config)


@Register(api_type="ollama")
class OllamaCompletionsPipeline(LangchainCompletionsPipeline[OllamaConfiguration]):

    def __init__(self, config: OllamaConfiguration):
        super().__init__(config=config)

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self.config.inference_url,
            model=model_id,
        )


@Register(api_type="ollama")
class OllamaPlaybookGenerationPipeline(LangchainPlaybookGenerationPipeline[OllamaConfiguration]):

    def __init__(self, config: OllamaConfiguration):
        super().__init__(config=config)

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self.config.inference_url,
            model=model_id,
        )


@Register(api_type="ollama")
class OllamaRoleGenerationPipeline(LangchainRoleGenerationPipeline[OllamaConfiguration]):

    def __init__(self, config: OllamaConfiguration):
        super().__init__(config=config)

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self.config.inference_url,
            model=model_id,
        )


@Register(api_type="ollama")
class OllamaPlaybookExplanationPipeline(LangchainPlaybookExplanationPipeline[OllamaConfiguration]):

    def __init__(self, config: OllamaConfiguration):
        super().__init__(config=config)

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self.config.inference_url,
            model=model_id,
        )
