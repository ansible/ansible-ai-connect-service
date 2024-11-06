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

from ansible_ai_connect.ai.api.model_pipelines.langchain.configuration import (
    LangchainBasePipelineConfiguration,
    LangchainConfiguration,
    LangchainConfigurationSerializer,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register

# -- Base
# ANSIBLE_AI_MODEL_MESH_API_URL
# ANSIBLE_AI_MODEL_MESH_MODEL_ID
# ANSIBLE_AI_MODEL_MESH_API_TIMEOUT

# -- BAM
# ANSIBLE_AI_MODEL_MESH_API_KEY
# ANSIBLE_AI_MODEL_MESH_API_VERIFY_SSL


@dataclass
class BAMConfiguration(LangchainConfiguration):

    def __init__(
        self,
        inference_url: str,
        model_id: str,
        timeout: Optional[int],
        api_key: str,
        verify_ssl: bool,
    ):
        super().__init__(
            inference_url,
            model_id,
            timeout,
        )
        self.api_key = api_key
        self.verify_ssl = verify_ssl

    api_key: str
    verify_ssl: bool


@Register(api_type="bam")
class BAMPipelineConfiguration(LangchainBasePipelineConfiguration):

    def __init__(self, **kwargs):
        super().__init__(
            "bam",
            BAMConfiguration(
                inference_url=kwargs["inference_url"],
                model_id=kwargs["model_id"],
                timeout=kwargs["timeout"],
                api_key=kwargs["api_key"],
                verify_ssl=kwargs["verify_ssl"],
            ),
        )


@Register(api_type="bam")
class BAMConfigurationSerializer(LangchainConfigurationSerializer):
    api_key = serializers.CharField(required=True)
    verify_ssl = serializers.BooleanField(required=False, default=False)
