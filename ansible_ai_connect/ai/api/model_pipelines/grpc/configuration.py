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

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    BaseConfig,
    PipelineConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.config_serializers import (
    BaseConfigSerializer,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register

# ANSIBLE_AI_MODEL_MESH_API_URL
# ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
# ANSIBLE_GRPC_HEALTHCHECK_URL


@dataclass
class GrpcConfiguration(BaseConfig):

    def __init__(
        self,
        inference_url: str,
        model_id: str,
        timeout: Optional[int],
        health_check_url: str,
    ):
        super().__init__(inference_url, model_id, timeout)
        self.health_check_url = health_check_url

    health_check_url: str


@Register(api_type="grpc")
class GrpcPipelineConfiguration(PipelineConfiguration[GrpcConfiguration]):

    def __init__(self, **kwargs):
        super().__init__(
            "grpc",
            GrpcConfiguration(
                inference_url=kwargs["inference_url"],
                model_id=kwargs["model_id"],
                timeout=kwargs["timeout"],
                health_check_url=kwargs["health_check_url"],
            ),
        )


@Register(api_type="grpc")
class GrpcConfigurationSerializer(BaseConfigSerializer):
    health_check_url = serializers.CharField(required=True)
