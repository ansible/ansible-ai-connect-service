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

from ansible_wisdom.ai.api.formatter import get_task_names_from_prompt

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class HttpClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        model_id = self.get_model_id(None, model_id)
        self._prediction_url = f"{self._inference_url}/predictions/{model_id}"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")

        try:
            task_count = len(get_task_names_from_prompt(prompt))
            result = self.session.post(
                self._prediction_url,
                headers=self.headers,
                json=model_input,
                timeout=self.timeout(task_count),
            )
            result.raise_for_status()
            response = json.loads(result.text)
            response['model_id'] = model_id
            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError
