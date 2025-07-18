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

import logging
from typing import TYPE_CHECKING, Optional, cast

from django.apps import apps

from ansible_ai_connect.ai.api.model_pipelines.exceptions import WcaTokenFailure
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    DUMMY_ROLE_FILES,
    DUMMY_ROLE_OUTLINE,
    CompletionsParameters,
    CompletionsResponse,
    MetaData,
    ModelPipelineCompletions,
    ModelPipelineRoleGeneration,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_dummy import (
    WCADummyConfiguration,
)
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)

if TYPE_CHECKING:
    from ansible_ai_connect.users.models import User
else:
    User = None

logger = logging.getLogger(__name__)


@Register(api_type="wca-dummy")
class WCADummyMetaData(MetaData[WCADummyConfiguration]):

    def __init__(self, config: WCADummyConfiguration):
        super().__init__(config=config)

    def get_model_id(
        self,
        user: User,
        requested_model_id: Optional[str] = None,
    ) -> str:
        return requested_model_id or ""

    def get_token(self, api_key) -> str:
        if api_key != "valid":
            raise WcaTokenFailure("I'm a fake WCA client and the only api_key I accept is 'valid'")
        return ""


@Register(api_type="wca-dummy")
class WCADummyCompletionsPipeline(
    WCADummyMetaData, ModelPipelineCompletions[WCADummyConfiguration]
):

    def __init__(self, config: WCADummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        return {
            "model_id": "mocked_wca_client",
            "predictions": ["      ansible.builtin.apt:\n        name: apache2"],
        }

    def infer_from_parameters(self, *args, **kwargs):
        return ""

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "wca-dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


@Register(api_type="wca-dummy")
class WCADummyRoleGenerationPipeline(
    WCADummyMetaData, ModelPipelineRoleGeneration[WCADummyConfiguration]
):

    def __init__(self, config: WCADummyConfiguration):
        super().__init__(config=config)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        create_outline = params.create_outline

        files = DUMMY_ROLE_FILES

        from ansible_ai_connect.ai.apps import AiConfig

        ai_config = cast(AiConfig, apps.get_app_config("ai"))
        if ansible_lint_caller := ai_config.get_ansible_lint_caller():
            print(ansible_lint_caller)
            print(ansible_lint_caller.run_linter("test"))
            print(files)
            for file in files:
                if file["file_type"] != "task":
                    continue
                file["content"] = ansible_lint_caller.run_linter(file["content"])
            print(files)

        return (
            "install_nginx",
            files,
            DUMMY_ROLE_OUTLINE.strip() if create_outline else "",
            [],
        )

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "wca-dummy",
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )
