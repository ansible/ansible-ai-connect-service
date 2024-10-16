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

from langchain.llms import Ollama

from ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines import (
    LangchainCompletionsPipeline,
    LangchainContentMatchPipeline,
    LangchainMetaData,
    LangchainPlaybookExplanationPipeline,
    LangchainPlaybookGenerationPipeline,
)

logger = logging.getLogger(__name__)


class OllamaMetaData(LangchainMetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)


class OllamaCompletionsPipeline(LangchainCompletionsPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self._inference_url,
            model=model_id,
        )


class OllamaContentMatchPipeline(LangchainContentMatchPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def codematch(self, request, model_input, model_id):
        raise NotImplementedError

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self._inference_url,
            model=model_id,
        )


class OllamaPlaybookGenerationPipeline(LangchainPlaybookGenerationPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self._inference_url,
            model=model_id,
        )


class OllamaPlaybookExplanationPipeline(LangchainPlaybookExplanationPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def get_chat_model(self, model_id):
        return Ollama(
            base_url=self._inference_url,
            model=model_id,
        )
