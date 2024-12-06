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

from rest_framework import serializers

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    BaseConfig,
    PipelineConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register


@dataclass
class NopConfiguration(BaseConfig):

    def __init__(self):
        super().__init__("NOP", "NOP", None, False)


@Register(api_type="nop")
class NopPipelineConfiguration(PipelineConfiguration[NopConfiguration]):

    def __init__(self, **kwargs):
        super().__init__(
            "nop",
            NopConfiguration(),
        )


@Register(api_type="nop")
class LlamaCppConfigurationSerializer(serializers.Serializer):
    pass
