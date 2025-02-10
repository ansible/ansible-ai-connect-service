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
from typing import TYPE_CHECKING, Generic, Optional, cast

import backoff
from django.apps import apps
from django.conf import settings
from requests.auth import HTTPBasicAuth
from requests.exceptions import HTTPError

from ansible_ai_connect.ai.api.aws.wca_secret_manager import (
    Suffixes,
    WcaSecretManagerError,
)
from ansible_ai_connect.ai.api.exceptions import FeatureNotAvailable
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaInferenceFailure,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaRequestIdCorrelationFailure,
    WcaTokenFailure,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PIPELINE_PARAMETERS,
    PIPELINE_RETURN,
    CompletionsParameters,
    CompletionsResponse,
    ContentMatchParameters,
    ContentMatchResponse,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleExplanationParameters,
    RoleExplanationResponse,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_saas import (
    WCASaaSConfiguration,
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
    WCABaseRoleExplanationPipeline,
    WCABaseRoleGenerationPipeline,
    WcaModelRequestException,
    WcaTokenRequestException,
    ibm_cloud_identity_token_hist,
    wca_codegen_role_hist,
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


@Register(api_type="wca")
class WCASaaSMetaData(WCABaseMetaData[WCASaaSConfiguration]):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

    def get_token(self, api_key):
        basic = None
        if self.config.idp_login:
            basic = HTTPBasicAuth(self.config.idp_login, self.config.idp_password)
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
                f"{self.config.idp_url}/token",
                headers=headers,
                data=data,
                auth=basic,
                verify=self.config.verify_ssl,
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
        if self.config.api_key:
            return self.config.api_key

        if organization_id is None:
            logger.error(
                "User does not have an organization and WCASaaSConfiguration.api_key is not set"
            )
            raise WcaKeyNotFound

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()  # type: ignore
        if (
            settings.ANSIBLE_AI_ENABLE_ONE_CLICK_TRIAL
            and any(up.is_active for up in user.userplan_set.all())
            and user.organization
            and not user.organization.has_api_key
        ):
            return self.config.one_click_default_api_key

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
            return self.config.one_click_default_model_id

        if requested_model_id:
            # requested_model_id defined: i.e. not None, not "", not {} etc.
            # let them use what they ask for
            return requested_model_id
        elif self.config.model_id:
            return self.config.model_id
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


class WCASaaSPipeline(
    WCASaaSMetaData,
    WCABasePipeline[WCASaaSConfiguration, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    Generic[PIPELINE_PARAMETERS, PIPELINE_RETURN],
    metaclass=ABCMeta,
):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

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


@Register(api_type="wca")
class WCASaaSCompletionsPipeline(
    WCASaaSPipeline[CompletionsParameters, CompletionsResponse],
    WCABaseCompletionsPipeline[WCASaaSConfiguration],
):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

    def self_test(self) -> HealthCheckSummary:
        wca_api_key = self.config.health_check_api_key
        wca_model_id = self.config.health_check_model_id
        summary: HealthCheckSummary = HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "wca",
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


@Register(api_type="wca")
class WCASaaSContentMatchPipeline(
    WCASaaSPipeline[ContentMatchParameters, ContentMatchResponse],
    WCABaseContentMatchPipeline[WCASaaSConfiguration],
):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

    def get_codematch_headers(self, api_key: str) -> dict[str, str]:
        return self._get_base_headers(api_key)

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


@Register(api_type="wca")
class WCASaaSPlaybookGenerationPipeline(
    WCASaaSPipeline[PlaybookGenerationParameters, PlaybookGenerationResponse],
    WCABasePlaybookGenerationPipeline[WCASaaSConfiguration],
):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        if settings.ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT:
            return super().invoke(params)
        else:
            raise FeatureNotAvailable

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


@Register(api_type="wca")
class WCASaaSRoleGenerationPipeline(
    WCASaaSPipeline[RoleGenerationParameters, RoleGenerationResponse],
    WCABaseRoleGenerationPipeline[WCASaaSConfiguration],
):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

    # This should be moved to the base WCA class when it becomes available on-prem
    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        request = params.request
        text = params.text
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

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_tries=self.retries + 1,
            giveup=self.fatal_exception,
            on_backoff=self.on_backoff_codegen_role,
        )
        @wca_codegen_role_hist.time()
        def post_request():
            return self.session.post(
                f"{self.config.inference_url}/v1/wca/codegen/ansible/roles",
                headers=headers,
                json=data,
                verify=self.config.verify_ssl,
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

        name = response["name"]
        files = response["files"]
        outline = response["outline"]
        warnings = response["warnings"] if "warnings" in response else []

        from ansible_ai_connect.ai.apps import AiConfig

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        if ansible_lint_caller := ai_config.get_ansible_lint_caller():
            for file in files:
                file["content"] = ansible_lint_caller.run_linter(file["content"])

        return name, files, outline, warnings

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


@Register(api_type="wca")
class WCASaaSRoleExplanationPipeline(
    WCASaaSPipeline[RoleExplanationParameters, RoleExplanationResponse],
    WCABaseRoleExplanationPipeline[WCASaaSConfiguration],
):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleExplanationParameters) -> RoleExplanationResponse:
        raise NotImplementedError

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError


@Register(api_type="wca")
class WCASaaSPlaybookExplanationPipeline(
    WCASaaSPipeline[PlaybookExplanationParameters, PlaybookExplanationResponse],
    WCABasePlaybookExplanationPipeline[WCASaaSConfiguration],
):

    def __init__(self, config: WCASaaSConfiguration):
        super().__init__(config=config)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        if settings.ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT:
            return super().invoke(params)
        else:
            raise FeatureNotAvailable

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError
