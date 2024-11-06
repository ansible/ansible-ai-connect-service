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

# -- Base
# ANSIBLE_AI_MODEL_MESH_API_URL


@dataclass
class WCADummyConfiguration(BaseConfig):

    def __init__(
        self,
        inference_url: str,
    ):
        super().__init__("dummy", "dummy", None)
        self.inference_url = inference_url

    inference_url: str


@Register(api_type="wca-dummy")
class WCADummyPipelineConfiguration(PipelineConfiguration[WCADummyConfiguration]):

    def __init__(self, **kwargs):
        super().__init__(
            "wca-dummy",
            WCADummyConfiguration(
                inference_url=kwargs["inference_url"],
            ),
        )


@Register(api_type="wca-dummy")
class WCADummyConfigurationSerializer(serializers.Serializer):
    inference_url = serializers.CharField(required=True)
