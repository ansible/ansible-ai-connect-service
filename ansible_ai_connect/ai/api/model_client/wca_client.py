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

import base64
import json
import logging
from abc import abstractmethod
from typing import Any, Dict, Optional

import backoff
import requests
from django.apps import apps
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from health_check.exceptions import ServiceUnavailable
from prometheus_client import Counter, Histogram
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from ansible_ai_connect.ai.api.exceptions import FeatureNotAvailable
from ansible_ai_connect.ai.api.formatter import (
    get_task_names_from_prompt,
    strip_task_preamble_from_multi_task_prompt,
    unify_prompt_ending,
)
from ansible_ai_connect.ai.api.model_client.wca_utils import (
    ContentMatchResponseChecks,
    Context,
    InferenceResponseChecks,
    TokenContext,
    TokenResponseChecks,
)
from ansible_ai_connect.healthcheck.backends import (
    ERROR_MESSAGE,
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
    HealthCheckSummaryException,
)

from ..aws.wca_secret_manager import Suffixes, WcaSecretManagerError
from .base import ModelMeshClient
from .exceptions import (
    ModelTimeoutError,
    WcaCodeMatchFailure,
    WcaInferenceFailure,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaSuggestionIdCorrelationFailure,
    WcaTokenFailure,
    WcaUsernameNotFound,
)

MODEL_MESH_HEALTH_CHECK_TOKENS = "tokens"

WCA_REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger(__name__)

wca_codegen_hist = Histogram(
    "wca_codegen_latency_seconds",
    "Histogram of WCA codegen API processing time",
    namespace=NAMESPACE,
)
wca_codematch_hist = Histogram(
    "wca_codematch_latency_seconds",
    "Histogram of WCA codematch API processing time",
    namespace=NAMESPACE,
)
ibm_cloud_identity_token_hist = Histogram(
    "wca_ibm_identity_token_latency_seconds",
    "Histogram of IBM Cloud identity token API processing time",
    namespace=NAMESPACE,
)
wca_codegen_retry_counter = Counter(
    "wca_codegen_retries",
    "Counter of WCA codegen API invocation retries",
    namespace=NAMESPACE,
)
wca_codematch_retry_counter = Counter(
    "wca_codematch_retries",
    "Counter of WCA codematch API invocation retries",
    namespace=NAMESPACE,
)
ibm_cloud_identity_token_retry_counter = Counter(
    "ibm_cloud_identity_token_retries",
    "Counter of IBM Cloud identity token API invocation retries",
    namespace=NAMESPACE,
)


class WcaTokenRequestException(ServiceUnavailable):
    """There was an error trying to get a WCA token."""


class WcaModelRequestException(ServiceUnavailable):
    """There was an error trying to invoke a WCA Model."""


class DummyWCAClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def infer_from_parameters(self, *args, **kwargs):
        return ""

    def get_model_id(
        self,
        organization_id: Optional[int] = None,
        requested_model_id: str = "",
    ) -> str:
        return requested_model_id or ""

    def get_token(self, api_key):
        if api_key != "valid":
            raise WcaTokenFailure("I'm a fake WCA client and the only api_key I accept is 'valid'")
        return ""

    def infer(self, request, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        return {
            "model_id": "mocked_wca_client",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }


class BaseWCAClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.retries = settings.ANSIBLE_WCA_RETRY_COUNT

    @staticmethod
    def fatal_exception(exc) -> bool:
        """Determine if an exception is fatal or not"""
        if isinstance(exc, requests.RequestException):
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            # retry on server errors and client errors
            # with 429 status code (rate limited),
            # don't retry on other client errors
            return bool(status_code and (400 <= status_code < 500) and status_code != 429)
        else:
            # retry on all other errors (e.g. network)
            return False

    @staticmethod
    def on_backoff_inference(details):
        wca_codegen_retry_counter.inc()

    @staticmethod
    def on_backoff_codematch(details):
        wca_codematch_retry_counter.inc()

    @staticmethod
    def on_backoff_ibm_cloud_identity_token(details):
        ibm_cloud_identity_token_retry_counter.inc()

    def infer(self, request, model_input, model_id: str = "", suggestion_id=None) -> Dict[str, Any]:
        logger.debug(f"Input prompt: {model_input}")

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        organization_id = request.user.org_id
        # WCA codegen fails if a multitask prompt includes the task preamble
        # https://github.com/rh-ibm-synergy/wca-feedback/issues/34
        prompt = strip_task_preamble_from_multi_task_prompt(prompt)

        prompt = unify_prompt_ending(prompt)

        try:
            api_key = self.get_api_key(organization_id)
            model_id = self.get_model_id(organization_id, model_id)
            result = self.infer_from_parameters(api_key, model_id, context, prompt, suggestion_id)

            response = result.json()
            response["model_id"] = model_id
            logger.debug(f"Inference API response: {response}")
            return response

        except requests.exceptions.Timeout:
            raise ModelTimeoutError(model_id=model_id)

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        data = {
            "model_id": model_id,
            "prompt": f"{context}{prompt}",
        }
        logger.debug(f"Inference API request payload: {json.dumps(data)}")

        headers = self.get_inference_headers(api_key, suggestion_id)
        task_count = len(get_task_names_from_prompt(prompt))
        # path matches ANSIBLE_WCA_INFERENCE_URL="https://api.dataplatform.test.cloud.ibm.com"
        prediction_url = f"{self._inference_url}/v1/wca/codegen/ansible"

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_inference,
        )
        @wca_codegen_hist.time()
        def post_request():
            logger.info(
                f"request to wca. headers: {headers}\n  url: {prediction_url}\n  data: {data}"
            )
            return self.session.post(
                prediction_url,
                headers=headers,
                json=data,
                timeout=self.timeout(task_count),
            )

        try:
            response = post_request()

            x_request_id = response.headers.get(WCA_REQUEST_ID_HEADER)
            if suggestion_id and x_request_id:
                # request/payload suggestion_id is a UUID not a string whereas
                # HTTP headers are strings.
                if x_request_id != str(suggestion_id):
                    raise WcaSuggestionIdCorrelationFailure(
                        model_id=model_id, x_request_id=x_request_id
                    )

            context = Context(model_id, response, task_count > 1)
            InferenceResponseChecks().run_checks(context)
            response.raise_for_status()

        except HTTPError as e:
            logger.error(f"WCA inference failed for suggestion {suggestion_id} due to {e}.")
            raise WcaInferenceFailure(model_id=model_id)

        return response

    @abstractmethod
    def get_api_key(self, organization_id: Optional[int]) -> str:
        raise NotImplementedError

    def codematch(self, model_input, model_id: str = ""):
        logger.debug(f"Input prompt: {model_input}")
        self._search_url = f"{self._inference_url}/v1/wca/codematch/ansible"

        suggestions = model_input.get("suggestions", "")
        organization_id = model_input.get("organization_id", None)

        model_id = self.get_model_id(organization_id, model_id)

        data = {
            "model_id": model_id,
            "input": suggestions,
        }

        logger.debug(f"Codematch API request payload: {data}")

        try:
            api_key = self.get_api_key(organization_id)
            headers = self.get_codematch_headers(api_key)
            suggestion_count = len(suggestions)

            @backoff.on_exception(
                backoff.expo,
                Exception,
                max_tries=self.retries + 1,
                giveup=self.fatal_exception,
                on_backoff=self.on_backoff_codematch,
            )
            @wca_codematch_hist.time()
            def post_request():
                return self.session.post(
                    self._search_url,
                    headers=headers,
                    json=data,
                    timeout=self.timeout(suggestion_count),
                )

            result = post_request()
            context = Context(model_id, result, suggestion_count > 1)
            ContentMatchResponseChecks().run_checks(context)
            result.raise_for_status()

            response = result.json()
            logger.debug(f"Codematch API response: {response}")

            return model_id, response

        except HTTPError:
            raise WcaCodeMatchFailure(model_id=model_id)

        except requests.exceptions.ReadTimeout:
            raise ModelTimeoutError(model_id=model_id)

    @abstractmethod
    def get_inference_headers(
        self, api_key: str, suggestion_id: Optional[str]
    ) -> dict[str, Optional[str]]:
        raise NotImplementedError

    @abstractmethod
    def get_codematch_headers(self, api_key: str) -> dict[str, str]:
        raise NotImplementedError

    def supports_ari_postprocessing(self) -> bool:
        return settings.ENABLE_ARI_POSTPROCESS and settings.WCA_ENABLE_ARI_POSTPROCESS


class WCAClient(BaseWCAClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_token(self, api_key):
        basic = None
        if settings.ANSIBLE_WCA_IDP_LOGIN:
            basic = HTTPBasicAuth(settings.ANSIBLE_WCA_IDP_LOGIN, settings.ANSIBLE_WCA_IDP_PASSWORD)
        # TODO: store token and only fetch a new one if it has expired
        # https://cloud.ibm.com/docs/account?topic=account-iamtoken_from_apikey
        logger.debug("Fetching WCA token")
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey", "apikey": api_key}

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_ibm_cloud_identity_token,
        )
        @ibm_cloud_identity_token_hist.time()
        def post_request():
            return self.session.post(
                f"{settings.ANSIBLE_WCA_IDP_URL}/token",
                headers=headers,
                data=data,
                auth=basic,
            )

        try:
            response = post_request()
            context = TokenContext(response)
            TokenResponseChecks().run_checks(context)
            response.raise_for_status()

        except HTTPError as e:
            logger.error(f"Failed to retrieve a WCA Token due to {e}.")
            raise WcaTokenFailure()

        return response.json()

    def get_api_key(self, organization_id: Optional[int]) -> str:
        # use the environment API key override if it's set
        if settings.ANSIBLE_AI_MODEL_MESH_API_KEY:
            return settings.ANSIBLE_AI_MODEL_MESH_API_KEY

        if organization_id is None:
            logger.error(
                "User does not have an organization and no ANSIBLE_AI_MODEL_MESH_API_KEY is set"
            )
            raise WcaKeyNotFound

        try:
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore
            api_key = secret_manager.get_secret(organization_id, Suffixes.API_KEY)
            if api_key is not None:
                return api_key["SecretString"]

        except (WcaSecretManagerError, KeyError):
            # if retrieving the API Key from AWS fails, we log an error
            logger.error(f"error retrieving WCA API Key for org_id '{organization_id}'")
            raise

        logger.error("Seated user's organization doesn't have default API Key set")
        raise WcaKeyNotFound

    def get_model_id(
        self,
        organization_id: Optional[int] = None,
        requested_model_id: str = "",
    ) -> str:
        if requested_model_id:
            # requested_model_id defined: i.e. not None, not "", not {} etc.
            # let them use what they ask for
            return requested_model_id
        elif settings.ANSIBLE_AI_MODEL_MESH_MODEL_NAME:
            return settings.ANSIBLE_AI_MODEL_MESH_MODEL_NAME
        elif organization_id is None:
            logger.error(
                "User is not linked to an organization and no default WCA model ID is found"
            )
            raise WcaNoDefaultModelId

        try:
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore
            model_id = secret_manager.get_secret(organization_id, Suffixes.MODEL_ID)
            if model_id is not None:
                return model_id["SecretString"]

        except (WcaSecretManagerError, KeyError):
            # if retrieving the Model ID from AWS fails, we log an error
            logger.error(f"error retrieving WCA Model ID for org_id '{organization_id}'")
            raise

        logger.error("Seated user's organization doesn't have default model ID set")
        raise WcaModelIdNotFound(model_id=requested_model_id)

    def get_inference_headers(
        self, api_key: str, suggestion_id: Optional[str]
    ) -> dict[str, Optional[str]]:
        base_headers = self._get_base_headers(api_key)
        return {
            **base_headers,
            WCA_REQUEST_ID_HEADER: str(suggestion_id) if suggestion_id else None,
        }

    def get_codematch_headers(self, api_key: str) -> dict[str, str]:
        return self._get_base_headers(api_key)

    def _get_base_headers(self, api_key: str) -> dict[str, str]:
        token = self.get_token(api_key)
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        }

    def self_test(self) -> HealthCheckSummary:
        wca_api_key = settings.ANSIBLE_WCA_HEALTHCHECK_API_KEY
        wca_model_id = settings.ANSIBLE_WCA_HEALTHCHECK_MODEL_ID
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: settings.ANSIBLE_AI_MODEL_MESH_API_TYPE,
                MODEL_MESH_HEALTH_CHECK_TOKENS: "ok",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
        try:
            self.infer_from_parameters(
                wca_api_key,
                wca_model_id,
                "",
                "- name: install ffmpeg on Red Hat Enterprise Linux",
            )
        except WcaInferenceFailure as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(WcaModelRequestException(ERROR_MESSAGE), e),
            )
        except Exception as e:
            logger.exception(str(e))
            # For any other failure we assume the whole WCA service is unavailable.
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_TOKENS,
                HealthCheckSummaryException(WcaTokenRequestException(ERROR_MESSAGE), e),
            )
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(WcaModelRequestException(ERROR_MESSAGE), e),
            )

        return summary

    def generate_playbook(
        self, request, text: str = "", create_outline: bool = False, outline: str = ""
    ) -> tuple[str, str]:
        organization_id = request.user.organization.id if request.user.organization else None
        api_key = self.get_api_key(organization_id)
        model_id = self.get_model_id(organization_id)

        headers = self._get_base_headers(api_key)
        data = {
            "model_id": model_id,
            "text": text,
            "create_outline": create_outline,
        }
        if outline:
            data["outline"] = outline

        result = self.session.post(
            f"{self._inference_url}/v1/wca/codegen/ansible/playbook",
            headers=headers,
            json=data,
        )

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)

        playbook = response["playbook"]
        outline = response["outline"]

        if ansible_lint_caller := apps.get_app_config("ai").get_ansible_lint_caller():
            playbook = ansible_lint_caller.run_linter(playbook)

        return playbook, outline

    def explain_playbook(self, request, content: str) -> str:
        organization_id = request.user.organization.id if request.user.organization else None
        api_key = self.get_api_key(organization_id)
        model_id = self.get_model_id(organization_id)

        headers = self._get_base_headers(api_key)
        data = {
            "model_id": model_id,
            "playbook": content,
        }
        result = self.session.post(
            f"{self._inference_url}/v1/wca/explain/ansible/playbook",
            headers=headers,
            json=data,
        )

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)
        return response["explanation"]


class WCAOnPremClient(BaseWCAClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        if not settings.ANSIBLE_WCA_USERNAME:
            raise WcaUsernameNotFound
        if not settings.ANSIBLE_AI_MODEL_MESH_API_KEY:
            raise WcaKeyNotFound
        # ANSIBLE_AI_MODEL_MESH_MODEL_NAME cannot be validated until runtime. The
        # User may provide an override value if the Environment Variable is not set.

    def get_api_key(self, organization_id: Optional[int]) -> str:
        logger.info(
            f"API_KEY using settings.ANSIBLE_AI_MODEL_MESH_API_KEY: \
                {settings.ANSIBLE_AI_MODEL_MESH_API_KEY}"
        )
        return settings.ANSIBLE_AI_MODEL_MESH_API_KEY

    def get_model_id(
        self,
        organization_id: Optional[int] = None,
        requested_model_id: str = "",
    ) -> str:
        if requested_model_id:
            # requested_model_id defined: let them use what they ask for
            logger.info(f"model-id requested: {requested_model_id}")
            return requested_model_id

        if settings.ANSIBLE_AI_MODEL_MESH_MODEL_NAME:
            logger.info(f"model-id pre-set: {settings.ANSIBLE_AI_MODEL_MESH_MODEL_NAME}")
            return settings.ANSIBLE_AI_MODEL_MESH_MODEL_NAME

        raise WcaModelIdNotFound()

    def get_inference_headers(
        self, api_key: str, suggestion_id: Optional[str]
    ) -> dict[str, Optional[str]]:
        base_headers = self._get_base_headers(api_key)
        return {
            **base_headers,
            WCA_REQUEST_ID_HEADER: str(suggestion_id) if suggestion_id else None,
        }

    def get_codematch_headers(self, api_key: str) -> dict[str, str]:
        return self._get_base_headers(api_key)

    def _get_base_headers(self, api_key: str) -> dict[str, str]:
        # https://www.ibm.com/docs/en/cloud-paks/cp-data/4.8.x?topic=apis-generating-api-auth-token
        username = settings.ANSIBLE_WCA_USERNAME
        logger.info(f"generating token using {api_key}:{username}")
        token = base64.b64encode(bytes(f"{username}:{api_key}", "ascii")).decode("ascii")
        logger.info(f"token generated: {token}")
        return {
            "Authorization": f"ZenApiKey {token}",
        }

    def self_test(self) -> HealthCheckSummary:
        wca_api_key = settings.ANSIBLE_WCA_HEALTHCHECK_API_KEY
        wca_model_id = settings.ANSIBLE_WCA_HEALTHCHECK_MODEL_ID
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: settings.ANSIBLE_AI_MODEL_MESH_API_TYPE,
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
        try:
            self.infer_from_parameters(
                wca_api_key,
                wca_model_id,
                "",
                "- name: install ffmpeg on Red Hat Enterprise Linux",
            )
        except Exception as e:
            logger.exception(str(e))
            summary.add_exception(
                MODEL_MESH_HEALTH_CHECK_MODELS,
                HealthCheckSummaryException(WcaModelRequestException(ERROR_MESSAGE), e),
            )

        return summary

    def generate_playbook(
        self, request, text: str = "", create_outline: bool = False, outline: str = ""
    ) -> tuple[str, str]:
        raise FeatureNotAvailable

    def explain_playbook(self, request, content: str) -> str:
        raise FeatureNotAvailable
