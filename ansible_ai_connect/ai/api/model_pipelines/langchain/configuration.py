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
from abc import ABCMeta
from typing import Optional

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    BaseConfig,
    PipelineConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.config_serializers import (
    BaseConfigSerializer,
)
from ansible_ai_connect.main.settings.types import t_model_mesh_api_type

# -- Base
# ANSIBLE_AI_MODEL_MESH_API_URL
# ANSIBLE_AI_MODEL_MESH_MODEL_ID
# ANSIBLE_AI_MODEL_MESH_API_TIMEOUT


class LangchainConfiguration(BaseConfig):

    def __init__(
        self,
        inference_url: str,
        model_id: str,
        timeout: Optional[int],
    ):
        super().__init__(inference_url, model_id, timeout)


class LangchainBasePipelineConfiguration(
    PipelineConfiguration[LangchainConfiguration], metaclass=ABCMeta
):

    def __init__(self, provider: t_model_mesh_api_type, config: LangchainConfiguration):
        super().__init__(provider=provider, config=config)


class LangchainConfigurationSerializer(BaseConfigSerializer):
    pass
