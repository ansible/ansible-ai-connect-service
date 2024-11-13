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
import logging
from abc import ABCMeta
from typing import TYPE_CHECKING, Optional

from django.conf import settings

from ansible_ai_connect.ai.api.exceptions import FeatureNotAvailable
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaUsernameNotFound,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_base import (
    WCA_REQUEST_ID_HEADER,
    WCABaseCompletionsPipeline,
    WCABaseContentMatchPipeline,
    WCABaseMetaData,
    WCABasePipeline,
    WCABasePlaybookExplanationPipeline,
    WCABasePlaybookGenerationPipeline,
    WCABaseRoleGenerationPipeline,
    WcaModelRequestException,
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


@Register(api_type="wca-onprem")
class WCAOnPremMetaData(WCABaseMetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_api_key(self, user, organization_id: Optional[int]) -> str:
        return settings.ANSIBLE_AI_MODEL_MESH_API_KEY

    def get_model_id(
        self,
        user,
        organization_id: Optional[int] = None,
        requested_model_id: Optional[str] = None,
    ) -> str:
        if requested_model_id:
            # requested_model_id defined: let them use what they ask for
            return requested_model_id

        if settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID:
            return settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID

        raise WcaModelIdNotFound()


class WCAOnPremPipeline(WCAOnPremMetaData, WCABasePipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        if not settings.ANSIBLE_WCA_USERNAME:
            raise WcaUsernameNotFound
        if not settings.ANSIBLE_AI_MODEL_MESH_API_KEY:
            raise WcaKeyNotFound
        # ANSIBLE_AI_MODEL_MESH_MODEL_ID cannot be validated until runtime. The
        # User may provide an override value if the Environment Variable is not set.

    def get_request_headers(
        self, api_key: str, identifier: Optional[str]
    ) -> dict[str, Optional[str]]:
        base_headers = self._get_base_headers(api_key)
        return {
            **base_headers,
            WCA_REQUEST_ID_HEADER: str(identifier) if identifier else None,
        }

    def _get_base_headers(self, api_key: str) -> dict[str, str]:
        # https://www.ibm.com/docs/en/cloud-paks/cp-data/4.8.x?topic=apis-generating-api-auth-token
        username = settings.ANSIBLE_WCA_USERNAME
        token = base64.b64encode(bytes(f"{username}:{api_key}", "ascii")).decode("ascii")
        return {
            "Authorization": f"ZenApiKey {token}",
        }


@Register(api_type="wca-onprem")
class WCAOnPremCompletionsPipeline(WCAOnPremPipeline, WCABaseCompletionsPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

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


@Register(api_type="wca-onprem")
class WCAOnPremContentMatchPipeline(WCAOnPremPipeline, WCABaseContentMatchPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def get_codematch_headers(self, api_key: str) -> dict[str, str]:
        return self._get_base_headers(api_key)

    def self_test(self):
        raise NotImplementedError


@Register(api_type="wca-onprem")
class WCAOnPremPlaybookGenerationPipeline(WCAOnPremPipeline, WCABasePlaybookGenerationPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        if settings.ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT:
            return super().invoke(params)
        else:
            raise FeatureNotAvailable

    def self_test(self):
        raise NotImplementedError


@Register(api_type="wca-onprem")
class WCAOnPremRoleGenerationPipeline(WCAOnPremPipeline, WCABaseRoleGenerationPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def self_test(self):
        raise NotImplementedError


@Register(api_type="wca-onprem")
class WCAOnPremPlaybookExplanationPipeline(WCAOnPremPipeline, WCABasePlaybookExplanationPipeline):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        if settings.ANSIBLE_AI_ENABLE_PLAYBOOK_ENDPOINT:
            return super().invoke(params)
        else:
            raise FeatureNotAvailable

    def self_test(self):
        raise NotImplementedError
