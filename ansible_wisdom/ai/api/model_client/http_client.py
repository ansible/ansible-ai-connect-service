import json
import logging

import requests
from django.conf import settings

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class HttpClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_name=None):
        model_name = model_name or settings.ANSIBLE_AI_MODEL_NAME
        self._prediction_url = f"{self._inference_url}/predictions/{model_name}"

        try:
            result = self.session.post(
                self._prediction_url, headers=self.headers, json=model_input, timeout=self.timeout
            )
            result.raise_for_status()
            return json.loads(result.text)
        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError
