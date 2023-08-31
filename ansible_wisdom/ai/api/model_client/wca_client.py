import logging

import requests
from django.apps import apps
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response

from ..aws.wca_secret_manager import Suffixes, WcaSecretManagerError
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
        # path matches ANSIBLE_AI_MODEL_MESH_HOST="https://api.dataplatform.test.cloud.ibm.com"
        self._prediction_url = f"{self._inference_url}/v1/wca/codegen/ansible"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")
        has_seat = model_input.get("instances", [{}])[0].get("has_seat", False)
        organization_id = model_input.get("instances", [{}])[0].get("organization_id", None)

        data = {
            "model_id": model_name,
            "prompt": f"{context}{prompt}\n",
        }

        logger.debug(f"Inference API request payload: {data}")

        try:
            # TODO: store token and only fetch a new one if it has expired
            api_key = self.get_api_key(has_seat, organization_id)
            token = self.get_token(api_key)
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

    def get_token(self, api_key):
        logger.debug("Fetching WCA token")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key}

        result = self.session.post(
            "https://iam.cloud.ibm.com/identity/token",
            headers=headers,
            data=data,
        )
        result.raise_for_status()
        return result.json()

    def get_api_key(self, has_seat, organization_id):
        # use the shared API Key if the user has no seat
        if not has_seat or organization_id is None:
            return self._api_key

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()

        try:
            api_key = secret_manager.get_secret(organization_id, Suffixes.API_KEY)
            if api_key is not None and "SecretString" in api_key:
                return api_key["SecretString"]

        except WcaSecretManagerError:
            # if retrieving the API Key from AWS fails, we log an error and return the shared key
            logger.error(f"error retrieving WCA API Key for org_id {organization_id}")

        return self._api_key
