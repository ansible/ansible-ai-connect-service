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
# ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL
# ENABLE_HEALTHCHECK_XXX


class MCPServersSerializer(serializers.Serializer):
    name = serializers.CharField(required=True)
    type = serializers.CharField(required=True)


@dataclass
class HttpConfiguration(BaseConfig):

    def __init__(
        self,
        inference_url: str,
        model_id: str,
        timeout: Optional[int],
        enable_health_check: Optional[bool],
        verify_ssl: bool,
        stream: bool = False,
        mcp_servers: Optional[list[dict[str, str]]] = None,
        ca_cert_file: Optional[str] = None,
    ):
        super().__init__(inference_url, model_id, timeout, enable_health_check)
        self.verify_ssl = verify_ssl
        self.stream = stream
        self.mcp_servers = mcp_servers or []
        self.ca_cert_file = ca_cert_file

    verify_ssl: bool
    stream: bool
    mcp_servers: Optional[list[dict[str, str]]] = None
    ca_cert_file: Optional[str] = None


@Register(api_type="http")
class HttpPipelineConfiguration(PipelineConfiguration[HttpConfiguration]):

    def __init__(self, **kwargs):
        super().__init__(
            "http",
            HttpConfiguration(
                inference_url=kwargs["inference_url"],
                model_id=kwargs["model_id"],
                timeout=kwargs["timeout"],
                enable_health_check=kwargs["enable_health_check"],
                verify_ssl=kwargs["verify_ssl"],
                stream=kwargs["stream"],
                mcp_servers=kwargs["mcp_servers"],
                ca_cert_file=kwargs.get("ca_cert_file"),
            ),
        )


@Register(api_type="http")
class HttpConfigurationSerializer(BaseConfigSerializer):
    verify_ssl = serializers.BooleanField(required=False, default=True)
    stream = serializers.BooleanField(required=False, default=False)
    ca_cert_file = serializers.CharField(required=False, default=None)
    mcp_servers = serializers.ListSerializer(
        child=MCPServersSerializer(), allow_empty=True, required=False, default=None
    )
