import json
import logging

import backoff
import requests
from ai.api.formatter import get_task_names_from_prompt
from ai.api.model_client.wca_utils import (
    ContentMatchContext,
    ContentMatchResponseChecks,
    InferenceContext,
    InferenceResponseChecks,
)
from django.apps import apps
from django.conf import settings
from requests.exceptions import HTTPError

from ..aws.wca_secret_manager import Suffixes, WcaSecretManagerError
from .base import ModelMeshClient
from .exceptions import (
    ModelTimeoutError,
    WcaBadRequest,
    WcaCodeMatchFailure,
    WcaInferenceFailure,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaTokenFailure,
)

logger = logging.getLogger(__name__)


class WCAClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.free_api_key = settings.ANSIBLE_WCA_FREE_API_KEY
        self.free_model_id = settings.ANSIBLE_WCA_FREE_MODEL_ID
        self.retries = settings.ANSIBLE_WCA_RETRY_COUNT

    @staticmethod
    def fatal_exception(exc):
        """Determine if an exception is fatal or not"""
        if isinstance(exc, requests.RequestException):
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            # retry on server errors and client errors
            # with 429 status code (rate limited),
            # don't retry on other client errors
            return status_code and (400 <= status_code < 500) and status_code != 429
        else:
            # retry on all other errors (e.g. network)
            return False

    def infer(self, model_input, model_id=None):
        logger.debug(f"Input prompt: {model_input}")

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")
        rh_user_has_seat = model_input.get("instances", [{}])[0].get("rh_user_has_seat", False)
        organization_id = model_input.get("instances", [{}])[0].get("organization_id", None)

        # WCA codegen endpoint requires prompt to end with \n
        if prompt.endswith('\n') is False:
            prompt = f"{prompt}\n"

        try:
            api_key = self.get_api_key(rh_user_has_seat, organization_id)
            model_id = self.get_model_id(rh_user_has_seat, organization_id, model_id)
            result = self.infer_from_parameters(api_key, model_id, context, prompt)

            response = result.json()
            response['model_id'] = model_id
            logger.debug(f"Inference API response: {response}")
            return response

        except requests.exceptions.Timeout:
            raise ModelTimeoutError(model_id=model_id)

    def infer_from_parameters(self, api_key, model_id, context, prompt):
        data = {
            "model_id": model_id,
            "prompt": f"{context}{prompt}",
        }
        logger.debug(f"Inference API request payload: {json.dumps(data)}")

        # TODO: store token and only fetch a new one if it has expired
        token = self.get_token(api_key)
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        }
        task_count = len(get_task_names_from_prompt(prompt))
        # path matches ANSIBLE_WCA_INFERENCE_URL="https://api.dataplatform.test.cloud.ibm.com"
        prediction_url = f"{self._inference_url}/v1/wca/codegen/ansible"

        @backoff.on_exception(
            backoff.expo, Exception, max_tries=self.retries + 1, giveup=self.fatal_exception
        )
        def post_request():
            return self.session.post(
                prediction_url,
                headers=headers,
                json=data,
                timeout=self.timeout(task_count),
            )

        try:
            response = post_request()
            context = InferenceContext(model_id, response, task_count > 1)
            InferenceResponseChecks().run_checks(context)
            response.raise_for_status()

        except HTTPError as e:
            logger.error(f"WCA inference failed due to {e}.")
            raise WcaInferenceFailure(model_id=model_id)

        return response

    def get_token(self, api_key):
        logger.debug("Fetching WCA token")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key}

        @backoff.on_exception(
            backoff.expo, Exception, max_tries=self.retries + 1, giveup=self.fatal_exception
        )
        def post_request():
            return self.session.post(
                "https://iam.cloud.ibm.com/identity/token",
                headers=headers,
                data=data,
            )

        try:
            response = post_request()
            response.raise_for_status()

        except HTTPError as e:
            logger.error(f"Failed to retrieve a WCA Token due to {e}.")
            raise WcaTokenFailure()

        return response.json()

    def get_api_key(self, rh_user_has_seat, organization_id):
        # use the shared API Key if the user has no seat
        if not rh_user_has_seat or organization_id is None:
            return self.free_api_key

        try:
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            api_key = secret_manager.get_secret(organization_id, Suffixes.API_KEY)
            if api_key is not None:
                return api_key["SecretString"]

        except (WcaSecretManagerError, KeyError):
            # if retrieving the API Key from AWS fails, we log an error
            logger.error(f"error retrieving WCA API Key for org_id '{organization_id}'")
            raise

        logger.error("Seated user's organization doesn't have default API Key set")
        raise WcaKeyNotFound

    def get_model_id(self, rh_user_has_seat, organization_id, requested_model_id):
        if not rh_user_has_seat or organization_id is None:
            if requested_model_id:
                err_message = "User is not entitled to customized model ID"
                logger.info(err_message)
                raise WcaBadRequest(model_id=requested_model_id)
            return self.free_model_id

        # from here on, user has a seat
        if requested_model_id:
            # requested_model_id defined: i.e. not None, not "", not {} etc.
            # let them use what they ask for
            return requested_model_id

        try:
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            model_id = secret_manager.get_secret(organization_id, Suffixes.MODEL_ID)
            if model_id is not None:
                return model_id["SecretString"]

        except (WcaSecretManagerError, KeyError):
            # if retrieving the Model ID from AWS fails, we log an error
            logger.error(f"error retrieving WCA Model ID for org_id '{organization_id}'")
            raise

        logger.error("Seated user's organization doesn't have default model ID set")
        raise WcaModelIdNotFound(model_id=requested_model_id)

    def codematch(self, model_input, model_id=None):
        logger.debug(f"Input prompt: {model_input}")
        self._search_url = f"{self._inference_url}/v1/wca/codematch/ansible"

        suggestions = model_input.get("suggestions", "")
        rh_user_has_seat = model_input.get("rh_user_has_seat", False)
        organization_id = model_input.get("organization_id", None)

        model_id = self.get_model_id(rh_user_has_seat, organization_id, model_id)
        data = {
            "model_id": model_id,
            "input": suggestions,
        }

        logger.debug(f"Codematch API request payload: {data}")

        try:
            # TODO: store token and only fetch a new one if it has expired
            api_key = self.get_api_key(rh_user_has_seat, organization_id)
            token = self.get_token(api_key)
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token['access_token']}",
            }

            suggestion_count = len(suggestions)

            @backoff.on_exception(
                backoff.expo, Exception, max_tries=self.retries + 1, giveup=self.fatal_exception
            )
            def post_request():
                return self.session.post(
                    self._search_url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout(suggestion_count),
                )

            result = post_request()
            context = ContentMatchContext(model_id, result, suggestion_count > 1)
            ContentMatchResponseChecks().run_checks(context)
            result.raise_for_status()

            response = result.json()
            logger.debug(f"Codematch API response: {response}")
            return response

        except HTTPError:
            raise WcaCodeMatchFailure(model_id=model_id)

        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError(model_id=model_id)
