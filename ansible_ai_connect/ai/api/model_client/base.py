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

from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Dict, Optional

from django.conf import settings

from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)

if TYPE_CHECKING:
    from ansible_ai_connect.users.models import User
else:
    User = None


class ModelMeshClient:
    def __init__(self, inference_url):
        self._inference_url = inference_url
        i = settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
        self._timeout = int(i) if i is not None else None

    @abstractmethod
    def infer(self, request, model_input, model_id: str = "", suggestion_id=None) -> Dict[str, Any]:
        pass

    def codematch(self, request, model_input, model_id):
        raise NotImplementedError

    def set_inference_url(self, inference_url):
        self._inference_url = inference_url

    def get_model_id(
        self,
        user: User,
        organization_id: Optional[int] = None,
        requested_model_id: str = "",
    ) -> str:
        return requested_model_id or settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None

    def get_chat_model(self, model_id):
        raise NotImplementedError

    def generate_playbook(
        self,
        request,
        text: str = "",
        custom_prompt: str = "",
        create_outline: bool = False,
        outline: str = "",
        generation_id: str = "",
        model_id: str = "",
    ) -> tuple[str, str, list]:
        raise NotImplementedError

    def explain_playbook(
        self,
        request,
        content: str,
        custom_prompt: str = "",
        explanation_id: str = "",
        model_id: str = "",
    ) -> str:
        raise NotImplementedError

    def self_test(self) -> HealthCheckSummary:
        """
        Check the health of the model service.
        """
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: settings.ANSIBLE_AI_MODEL_MESH_API_TYPE,
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )

    def supports_ari_postprocessing(self) -> bool:
        return settings.ENABLE_ARI_POSTPROCESS
