import json
import logging

import requests
from rest_framework import status
from rest_framework.response import Response

from tools.jaeger import tracer

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class HttpClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_name="wisdom"):
        with tracer.start_span('Model Server (HTTP Client)') as span:
            span.set_attribute('Class', __class__.__name__)
            span.set_attribute('file', __file__)
            span.set_attribute('Method', 'infer')
            span.set_attribute(
                'Description',
                'initializes prediction url and retrieves recommendation '
                'information (text, status codes, etc.)',
            )

        self._prediction_url = f"{self._inference_url}/predictions/{model_name}"

        # print("prediction url: \n", self._prediction_url)

        try:
            result = self.session.post(
                self._prediction_url, headers=self.headers, json=model_input, timeout=self.timeout
            )

            result.raise_for_status()  # displays error message for a given result.status_code
            return json.loads(result.text)
        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError
