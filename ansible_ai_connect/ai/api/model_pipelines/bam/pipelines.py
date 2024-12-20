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
from typing import Any, Callable, List, Optional, Union

import requests
from django.conf import settings
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.messages import BaseMessage

from ansible_ai_connect.ai.api.model_pipelines.bam.configuration import BAMConfiguration
from ansible_ai_connect.ai.api.model_pipelines.langchain.pipelines import (
    LangchainCompletionsPipeline,
    LangchainMetaData,
    LangchainPlaybookExplanationPipeline,
    LangchainPlaybookGenerationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register

logger = logging.getLogger(__name__)


class ChatBAM(SimpleChatModel):
    api_key: str
    model_id: str
    prediction_url: str
    timeout: Callable[[int], Union[int, None]]

    @property
    def _llm_type(self) -> str:
        return "BAM"

    def _call(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        if stop is not None:
            raise ValueError("stop kwargs are not permitted.")

        bam_messages = list(
            map(lambda x: {"role": x.additional_kwargs["role"], "content": x.content}, messages)
        )
        session = requests.Session()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        params = {
            "model_id": self.model_id,
            "messages": bam_messages,
            "parameters": {
                "temperature": 0.1,
                "decoding_method": "greedy",
                "repetition_penalty": 1.05,
                "min_new_tokens": 1,
                "max_new_tokens": 2048,
            },
        }

        logger.info(f"request: {params}")

        result = session.post(
            self.prediction_url,
            headers=headers,
            json=params,
            timeout=self.timeout(1),
            verify=settings.ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL,
        )
        result.raise_for_status()
        body = json.loads(result.text)
        logger.info(f"response: {body}")
        response = body.get("results", [{}])[0].get("generated_text", "")
        return response


@Register(api_type="bam")
class BAMMetaData(LangchainMetaData[BAMConfiguration]):

    def __init__(self, config: BAMConfiguration):
        super().__init__(config=config)


@Register(api_type="bam")
class BAMCompletionsPipeline(LangchainCompletionsPipeline[BAMConfiguration]):

    def __init__(self, config: BAMConfiguration):
        super().__init__(config=config)

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError

    def get_chat_model(self, model_id):
        return ChatBAM(
            api_key=self.config.api_key,
            model_id=model_id,
            prediction_url=f"{self.config.inference_url}/v2/text/chat?version=2024-01-10",
            timeout=self.timeout,
        )


@Register(api_type="bam")
class BAMPlaybookGenerationPipeline(LangchainPlaybookGenerationPipeline[BAMConfiguration]):

    def __init__(self, config: BAMConfiguration):
        super().__init__(config=config)

    def get_chat_model(self, model_id):
        return ChatBAM(
            api_key=self.config.api_key,
            model_id=model_id,
            prediction_url=f"{self.config.inference_url}/v2/text/chat?version=2024-01-10",
            timeout=self.timeout,
        )


@Register(api_type="bam")
class BAMPlaybookExplanationPipeline(LangchainPlaybookExplanationPipeline[BAMConfiguration]):

    def __init__(self, config: BAMConfiguration):
        super().__init__(config=config)

    def get_chat_model(self, model_id):
        return ChatBAM(
            api_key=self.config.api_key,
            model_id=model_id,
            prediction_url=f"{self.config.inference_url}/v2/text/chat?version=2024-01-10",
            timeout=self.timeout,
        )
