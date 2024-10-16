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
from typing import Any, Dict

import requests
from django.conf import settings

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.formatter import get_task_names_from_prompt
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    MetaData,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
)

logger = logging.getLogger(__name__)


class LlamaCppMetaData(MetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        i = settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
        self._timeout = int(i) if i is not None else None

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None


class LlamaCppCompletionsPipeline(LlamaCppMetaData, ModelPipelineCompletions):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def invoke(self):
        raise NotImplementedError

    def infer(self, request, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        model_id = self.get_model_id(request.user, None, model_id)
        self._prediction_url = f"{self._inference_url}/completion"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        logger.info(f"prompt: '{prompt}'")
        logger.info(f"context: '{context}'")

        full_prompt = f"{context}{prompt}\n"
        logger.info(f"full prompt: {full_prompt}")

        params = {
            "prompt": full_prompt,
            "model": model_id,
            "n_predict": 400,
            "temperature": 0.1,
            "stop": [],
            "repeat_last_n": 256,
            "repeat_penalty": 1.18,
            "top_k": 40,
            "top_p": 0.5,
            "tfs_z": 1,
            "typical_p": 1,
            "presence_penalty": 0,
            "frequency_penalty": 0,
            "mirostat": 0,
            "mirostat_tau": 5,
            "mirostat_eta": 0.1,
            "grammar": "",
            "n_probs": 0,
            "image_data": [],
            "cache_prompt": False,
            "stream": False,
            "seed": 0,
        }

        logger.info(f"request: {params}")

        try:
            # Implement multitask here with a loop
            task_count = len(get_task_names_from_prompt(prompt))
            result = self.session.post(
                self._prediction_url,
                headers=self.headers,
                json=params,
                timeout=self.timeout(task_count),
                verify=settings.ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL,
            )
            result.raise_for_status()
            body = json.loads(result.text)
            logger.info(f"response: {body}")
            task = body["content"]
            # Fragile and not always correct; remove when we've created a better tune
            task = task.split("- name:")[0]
            task = task.split("```")[0]
            response = {"predictions": [task], "model_id": body["model"]}

            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


class LlamaCppContentMatchPipeline(LlamaCppMetaData, ModelPipelineContentMatch):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def codematch(self, request, model_input, model_id):
        raise NotImplementedError


class LlamaCppPlaybookGenerationPipeline(LlamaCppMetaData, ModelPipelinePlaybookGeneration):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def generate_playbook(
        self,
        request,
        text: str = "",
        custom_prompt: str = "",
        create_outline: bool = False,
        outline: str = "",
        generation_id: str = "",
        model_id: str = "",
    ) -> tuple[str, str, list]:
        raise NotImplementedError


class LlamaCppPlaybookExplanationPipeline(LlamaCppMetaData, ModelPipelinePlaybookExplanation):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self):
        raise NotImplementedError

    def explain_playbook(
        self,
        request,
        content: str,
        custom_prompt: str = "",
        explanation_id: str = "",
        model_id: str = "",
    ) -> str:
        raise NotImplementedError
