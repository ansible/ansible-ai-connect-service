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


@dataclass
class LlamaStackConfiguration(BaseConfig):

    def __init__(
        self,
        inference_url: str,
        model_id: str,
        timeout: Optional[int],
        enable_health_check: Optional[bool],
        stream: bool = False,
    ):
        super().__init__(inference_url, model_id, timeout, enable_health_check)
        self.stream = stream

    stream: bool


@Register(api_type="llama-stack")
class LlamaStackPipelineConfiguration(PipelineConfiguration[LlamaStackConfiguration]):

    def __init__(self, **kwargs):
        super().__init__(
            "llama-stack",
            LlamaStackConfiguration(
                inference_url=kwargs["inference_url"],
                model_id=kwargs["model_id"],
                timeout=kwargs["timeout"],
                enable_health_check=kwargs["enable_health_check"],
                stream=kwargs["stream"],
            ),
        )


@Register(api_type="llama-stack")
class LlamaStackConfigurationSerializer(BaseConfigSerializer):
    stream = serializers.BooleanField(required=False, default=False)
