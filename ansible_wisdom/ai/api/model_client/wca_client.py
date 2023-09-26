import logging

import requests
from django.apps import apps
from django.conf import settings

from ..aws.wca_secret_manager import Suffixes, WcaSecretManagerError
from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class WcaBadRequest(Exception):
    """Bad request to WCA"""


class WCAClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.free_api_key = settings.ANSIBLE_WCA_FREE_API_KEY
        self.free_model_id = settings.ANSIBLE_WCA_FREE_MODEL_ID

    def infer(self, model_input, model_id=None):
        logger.debug(f"Input prompt: {model_input}")
        # path matches ANSIBLE_WCA_INFERENCE_URL="https://api.dataplatform.test.cloud.ibm.com"
        self._prediction_url = f"{self._inference_url}/v1/wca/codegen/ansible"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")
        rh_user_has_seat = model_input.get("instances", [{}])[0].get("rh_user_has_seat", False)
        organization_id = model_input.get("instances", [{}])[0].get("organization_id", None)

        if prompt.endswith('\n') is False:
            prompt = f"{prompt}\n"

        model_id = self.get_model_id(rh_user_has_seat, organization_id, model_id)
        data = {
            "model_id": model_id,
            "prompt": f"{context}{prompt}",
        }

        logger.debug(f"Inference API request payload: {data}")

        try:
            # TODO: store token and only fetch a new one if it has expired
            api_key = self.get_api_key(rh_user_has_seat, organization_id)
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
            response['model_id'] = model_id
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

    def get_api_key(self, rh_user_has_seat, organization_id):
        # use the shared API Key if the user has no seat
        if not rh_user_has_seat or organization_id is None:
            return self.free_api_key

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()

        try:
            api_key = secret_manager.get_secret(organization_id, Suffixes.API_KEY)
            if api_key is not None:
                return api_key["SecretString"]

        except (WcaSecretManagerError, KeyError):
            # if retrieving the API Key from AWS fails, we log an error and return the shared key
            logger.error(f"error retrieving WCA API Key for org_id '{organization_id}'")

        raise WcaSecretManagerError

    def get_model_id(self, rh_user_has_seat, organization_id, requested_model_id):
        if not rh_user_has_seat or organization_id is None:
            if requested_model_id:
                err_message = "User is not entitled to customized model ID"
                logger.error(err_message)
                raise WcaBadRequest(err_message)
            return self.free_model_id

        # from here on, user has a seat
        if requested_model_id:
            # requested_model_id defined: i.e. not None, not "", not {} etc
            # let them use what they ask for
            return requested_model_id

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()

        try:
            model_id = secret_manager.get_secret(organization_id, Suffixes.MODEL_ID)
            if model_id is not None:
                return model_id["SecretString"]
            err_message = "Seated user's organization doesn't have default model ID set"
            logger.error(err_message)
            raise WcaBadRequest(err_message)

        except (WcaSecretManagerError, KeyError):
            # if retrieving from AWS fails
            logger.error(f"error retrieving WCA Model ID for org_id '{organization_id}'")

        raise WcaSecretManagerError
