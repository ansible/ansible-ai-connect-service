import json
import logging

import requests
from ai.api.formatter import get_task_names_from_prompt
from django.conf import settings

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class HttpClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_id=None):
        model_id = model_id or settings.ANSIBLE_AI_MODEL_NAME
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
