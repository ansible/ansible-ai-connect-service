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

from ansible_ai_connect.ai.api.formatter import get_task_names_from_prompt

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class LlamaCPPClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        model_id = self.get_model_id(None, model_id)
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
            # TODO(rg): implement multitask here with a loop
            task_count = len(get_task_names_from_prompt(prompt))
            result = self.session.post(
                self._prediction_url,
                headers=self.headers,
                json=params,
                timeout=self.timeout(task_count),
            )
            result.raise_for_status()
            body = json.loads(result.text)
            logger.info(f"response: {body}")
            task = body["content"]
            # TODO(rg): fragile and not always correct; remove when we've created a better tune
            task = task.split("- name:")[0]
            task = task.split("```")[0]
            response = {"predictions": [task], "model_id": body["model"]}

            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError
