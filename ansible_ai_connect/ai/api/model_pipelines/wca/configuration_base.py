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

from rest_framework import serializers

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
# ANSIBLE_AI_MODEL_MESH_API_KEY
# ANSIBLE_AI_MODEL_MESH_MODEL_ID
# ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
# ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL
# ANSIBLE_WCA_RETRY_COUNT
# WCA_ENABLE_ARI_POSTPROCESS
# ANSIBLE_WCA_HEALTHCHECK_API_KEY
# ANSIBLE_WCA_HEALTHCHECK_MODEL_ID


class WCABaseConfiguration(BaseConfig, metaclass=ABCMeta):

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
    ):
        super().__init__(inference_url, model_id, timeout)
        self.api_key = api_key
        self.verify_ssl = verify_ssl
        self.retry_count = retry_count
        self.enable_ari_postprocessing = enable_ari_postprocessing
        self.health_check_api_key = health_check_api_key
        self.health_check_model_id = health_check_model_id

    api_key: str
    verify_ssl: bool
    retry_count: int
    enable_ari_postprocessing: bool
    health_check_url: str
    health_check_model_id: str


class WCABasePipelineConfiguration(PipelineConfiguration[WCABaseConfiguration], metaclass=ABCMeta):

    def __init__(self, provider: t_model_mesh_api_type, config: WCABaseConfiguration):
        super().__init__(provider=provider, config=config)


class WCABaseConfigurationSerializer(BaseConfigSerializer):
    api_key = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    verify_ssl = serializers.BooleanField(required=False, default=False)
    retry_count = serializers.IntegerField(required=False, default=4)
    enable_ari_postprocessing = serializers.BooleanField(required=False, default=False)
    health_check_api_key = serializers.CharField(required=True)
    health_check_model_id = serializers.CharField(required=True)
