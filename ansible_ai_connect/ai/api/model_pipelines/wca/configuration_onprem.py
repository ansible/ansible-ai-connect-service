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
from dataclasses import dataclass
from typing import Optional

from rest_framework import serializers

from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.ai.api.model_pipelines.wca.configuration_base import (
    WCABaseConfiguration,
    WCABaseConfigurationSerializer,
    WCABasePipelineConfiguration,
)

# -- Base
# ANSIBLE_AI_MODEL_MESH_API_URL
# ANSIBLE_AI_MODEL_MESH_API_KEY
# ANSIBLE_AI_MODEL_MESH_MODEL_ID
# ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
# ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL
# ANSIBLE_WCA_RETRY_COUNT
# WCA_ENABLE_ARI_POSTPROCESS
# ANSIBLE_WCA_HEALTHCHECK_API_KEY
# ANSIBLE_WCA_HEALTHCHECK_MODEL_ID

# -- onprem
# ANSIBLE_WCA_USERNAME


@dataclass
class WCAOnPremConfiguration(WCABaseConfiguration):

    def __init__(
        self,
        inference_url: str,
        api_key: str,
        model_id: str,
        timeout: Optional[int],
        verify_ssl: bool,
        retry_count: int,
        enable_ari_postprocessing: bool,
        health_check_api_key: str,
        health_check_model_id: str,
        username: str,
    ):
        super().__init__(
            inference_url,
            api_key,
            model_id,
            timeout,
            verify_ssl,
            retry_count,
            enable_ari_postprocessing,
            health_check_api_key,
            health_check_model_id,
        )
        self.username = username

    username: str


@Register(api_type="wca-onprem")
class WCAOnPremPipelineConfiguration(WCABasePipelineConfiguration):

    def __init__(self, **kwargs):
        super().__init__(
            "wca-onprem",
            WCAOnPremConfiguration(
                inference_url=kwargs["inference_url"],
                api_key=kwargs["api_key"],
                model_id=kwargs["model_id"],
                timeout=kwargs["timeout"],
                verify_ssl=kwargs["verify_ssl"],
                retry_count=kwargs["retry_count"],
                enable_ari_postprocessing=kwargs["enable_ari_postprocessing"],
                health_check_api_key=kwargs["health_check_api_key"],
                health_check_model_id=kwargs["health_check_model_id"],
                username=kwargs["username"],
            ),
        )


@Register(api_type="wca-onprem")
class WCAOnPremConfigurationSerializer(WCABaseConfigurationSerializer):
    username = serializers.CharField(required=True)
