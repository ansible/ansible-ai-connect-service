import json
import logging
import os

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

        token = self.getToken()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        }

        logger.debug(f"inference API payload: {data}")

        try:
            result = self.session.post(
                self._prediction_url, headers=headers, json=data, timeout=self.timeout
            )
            result.raise_for_status()
            response = json.loads(result.text)
            logger.debug(f"inference API response: {response}")
            return response
        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError

    def getToken(self):
        logger.debug("fetching WCA token")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": self._api_key}

        try:
            result = self.session.post(
                "https://iam.cloud.ibm.com/identity/token",
                headers=headers,
                data=data,
            )
            return json.loads(result.text)
        except Exception as e:
            logger.error(f"error occurred {e}")
