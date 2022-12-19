import json
import logging

import requests
from rest_framework.response import Response

from .base import ModelMeshClient

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
logger = logging.getLogger(__name__)


class HttpClient(ModelMeshClient):
    def __init__(self, inference_url, management_url):
        super().__init__(inference_url=inference_url, management_url=management_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_name="wisdom") -> Response:
        self._prediction_url = f"{self._inference_url}/predictions/{model_name}"
        result = self.session.post(self._prediction_url, headers=self.headers, json=model_input)
        return Response(json.loads(result.text), status=result.status_code)
