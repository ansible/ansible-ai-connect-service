import logging

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class WCAClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self._api_key = settings.ANSIBLE_AI_MODEL_MESH_API_KEY

    def infer(self, model_input, model_name="wisdom"):
        logger.debug(f"Input prompt: {model_input}")
        self._prediction_url = f"{self._inference_url}/analytics/notebooks/codegen/gencode/"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        data = {
            "model_id": model_name,
            "prompt": f"{context}{prompt}\n",
        }

        logger.debug(f"Inference API request payload: {data}")

        try:
            # TODO: store token and only fetch a new one if it has expired
            token = self.get_token()
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token['access_token']}",
            }

            result = self.session.post(
                self._prediction_url, headers=headers, json=data, timeout=self.timeout
            )
            result.raise_for_status()
            response = result.json()
            logger.debug(f"Inference API response: {response}")
            return response
        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError

    def get_token(self):
        logger.debug("Fetching WCA token")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self._api_key}

        result = self.session.post(
            "https://iam.cloud.ibm.com/identity/token",
            headers=headers,
            data=data,
        )
        result.raise_for_status()
        return result.json()
