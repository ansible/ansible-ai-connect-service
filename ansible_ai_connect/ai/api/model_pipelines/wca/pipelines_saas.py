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

import json
import logging
from abc import ABCMeta
from typing import TYPE_CHECKING, Optional, cast

import backoff
from django.apps import apps
from django.conf import settings
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from ansible_ai_connect.ai.api.aws.wca_secret_manager import (
    Suffixes,
    WcaSecretManagerError,
)
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaInferenceFailure,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaRequestIdCorrelationFailure,
    WcaTokenFailure,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base import (
    MODEL_MESH_HEALTH_CHECK_TOKENS,
    WCA_REQUEST_ID_HEADER,
    WCABaseCompletionsPipeline,
    WCABaseContentMatchPipeline,
    WCABaseMetaData,
    WCABasePipeline,
    WCABasePlaybookExplanationPipeline,
    WCABasePlaybookGenerationPipeline,
    WcaModelRequestException,
    WcaTokenRequestException,
    ibm_cloud_identity_token_hist,
    wca_codegen_playbook_hist,
    wca_explain_playbook_hist,
)
from ansible_ai_connect.ai.api.model_pipelines.wca.wca_utils import (
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

if TYPE_CHECKING:
    from ansible_ai_connect.users.models import User
else:
    User = None

logger = logging.getLogger(__name__)


class WCASaaSMetaData(WCABaseMetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_token(self, api_key):
        basic = None
        if settings.ANSIBLE_WCA_IDP_LOGIN:
            basic = HTTPBasicAuth(settings.ANSIBLE_WCA_IDP_LOGIN, settings.ANSIBLE_WCA_IDP_PASSWORD)
        # Store token and only fetch a new one if it has expired
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
                verify=settings.ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL,
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

    def get_api_key(self, user, organization_id: Optional[int]) -> str:
        if not organization_id and user.organization:
            # The organization_id parameter should be removed
            organization_id = user.organization.id  # type: ignore[reportAttributeAccessIssue]
        # use the environment API key override if it's set
        if settings.ANSIBLE_AI_MODEL_MESH_API_KEY:
            return settings.ANSIBLE_AI_MODEL_MESH_API_KEY

        if organization_id is None:
            logger.error(
                "User does not have an organization and no ANSIBLE_AI_MODEL_MESH_API_KEY is set"
            )
            raise WcaKeyNotFound

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore
        if (
            settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
            and any(up.is_active for up in user.userplan_set.all())
            and user.organization
            and not user.organization.has_api_key
        ):
            return settings.ANSIBLE_AI_ENABLE_ONE_CLICK_DEFAULT_API_KEY

        try:
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
        user,
        organization_id: Optional[int] = None,
        requested_model_id: Optional[str] = None,
    ) -> str:
        logger.debug(f"requested_model_id={requested_model_id}")
        if not organization_id and user.organization:
            # The organization_id parameter should be removed
            organization_id = user.organization.id  # type: ignore[reportAttributeAccessIssue]
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore
        if (
            settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
            and any(
                up.is_active
                for up in user.userplan_set.all()  # noqa: E501 # pyright: ignore[reportAttributeAccessIssue]
            )
            and user.organization
            and not secret_manager.secret_exists(organization_id, Suffixes.API_KEY)
        ):
            return settings.ANSIBLE_AI_ENABLE_ONE_CLICK_DEFAULT_MODEL_ID

        if requested_model_id:
            # requested_model_id defined: i.e. not None, not "", not {} etc.
            # let them use what they ask for
            return requested_model_id
        elif settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID:
            return settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID
        elif organization_id is None:
            logger.error(
                "User is not linked to an organization and no default WCA model ID is found"
            )
            raise WcaNoDefaultModelId

        try:
            model_id = secret_manager.get_secret(organization_id, Suffixes.MODEL_ID)
            if model_id is not None:
                return model_id["SecretString"]

        except (WcaSecretManagerError, KeyError):
            # if retrieving the Model ID from AWS fails, we log an error
            logger.error(f"error retrieving WCA Model ID for org_id '{organization_id}'")
            raise

        logger.error("Seated user's organization doesn't have default model ID set")
        raise WcaModelIdNotFound(model_id=requested_model_id if requested_model_id else "none")


class WCASaaSPipeline(WCASaaSMetaData, WCABasePipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_request_headers(
        self, api_key: str, identifier: Optional[str]
    ) -> dict[str, Optional[str]]:
        base_headers = self._get_base_headers(api_key)
        return {
            **base_headers,
            WCA_REQUEST_ID_HEADER: str(identifier) if identifier else None,
        }

    def _get_base_headers(self, api_key: str) -> dict[str, str]:
        token = self.get_token(api_key)
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token['access_token']}",
        }


class WCASaaSCompletionsPipeline(WCASaaSPipeline, WCABaseCompletionsPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

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


class WCASaaSContentMatchPipeline(WCASaaSPipeline, WCABaseContentMatchPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_codematch_headers(self, api_key: str) -> dict[str, str]:
        return self._get_base_headers(api_key)

    def self_test(self):
        raise NotImplementedError


class WCASaaSPlaybookGenerationPipeline(WCASaaSPipeline, WCABasePlaybookGenerationPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def self_test(self):
        raise NotImplementedError

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        request = params.request
        text = params.text
        custom_prompt = params.custom_prompt
        create_outline = params.create_outline
        outline = params.outline
        model_id = params.model_id
        generation_id = params.generation_id

        organization_id = request.user.organization.id if request.user.organization else None
        api_key = self.get_api_key(request.user, organization_id)
        model_id = self.get_model_id(request.user, organization_id, model_id)

        headers = self.get_request_headers(api_key, generation_id)
        data = {
            "model_id": model_id,
            "text": text,
            "create_outline": create_outline,
        }
        if outline:
            data["outline"] = outline
        if custom_prompt:
            if not custom_prompt.endswith("\n"):
                custom_prompt = f"{custom_prompt}\n"
            data["custom_prompt"] = custom_prompt

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_codegen_playbook,
        )
        @wca_codegen_playbook_hist.time()
        def post_request():
            return self.session.post(
                f"{self._inference_url}/v1/wca/codegen/ansible/playbook",
                headers=headers,
                json=data,
                verify=settings.ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL,
            )

        result = post_request()

        x_request_id = result.headers.get(WCA_REQUEST_ID_HEADER)
        if generation_id and x_request_id:
            # request/payload suggestion_id is a UUID not a string whereas
            # HTTP headers are strings.
            if x_request_id != str(generation_id):
                raise WcaRequestIdCorrelationFailure(model_id=model_id, x_request_id=x_request_id)

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)

        playbook = response["playbook"]
        outline = response["outline"]
        warnings = response["warnings"] if "warnings" in response else []

        from ansible_ai_connect.ai.apps import AiConfig

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        if ansible_lint_caller := ai_config.get_ansible_lint_caller():
            playbook = ansible_lint_caller.run_linter(playbook)

        return playbook, outline, warnings


class WCASaaSPlaybookExplanationPipeline(WCASaaSPipeline, WCABasePlaybookExplanationPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def self_test(self):
        raise NotImplementedError

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        request = params.request
        content = params.content
        custom_prompt = params.custom_prompt
        model_id = params.model_id
        explanation_id = params.explanation_id

        organization_id = request.user.organization.id if request.user.organization else None
        api_key = self.get_api_key(request.user, organization_id)
        model_id = self.get_model_id(request.user, organization_id, model_id)

        headers = self.get_request_headers(api_key, explanation_id)
        data = {
            "model_id": model_id,
            "playbook": content,
        }
        if custom_prompt:
            if not custom_prompt.endswith("\n"):
                custom_prompt = f"{custom_prompt}\n"
            data["custom_prompt"] = custom_prompt

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_explain_playbook,
        )
        @wca_explain_playbook_hist.time()
        def post_request():
            return self.session.post(
                f"{self._inference_url}/v1/wca/explain/ansible/playbook",
                headers=headers,
                json=data,
                verify=settings.ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL,
            )

        result = post_request()

        x_request_id = result.headers.get(WCA_REQUEST_ID_HEADER)
        if explanation_id and x_request_id:
            # request/payload suggestion_id is a UUID not a string whereas
            # HTTP headers are strings.
            if x_request_id != str(explanation_id):
                raise WcaRequestIdCorrelationFailure(model_id=model_id, x_request_id=x_request_id)

        context = Context(model_id, result, False)
        InferenceResponseChecks().run_checks(context)
        result.raise_for_status()

        response = json.loads(result.text)
        return response["explanation"]
