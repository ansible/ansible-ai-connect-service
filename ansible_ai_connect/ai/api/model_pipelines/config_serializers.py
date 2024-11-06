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
from typing import TypeVar, get_args

from rest_framework import serializers
from rest_framework.serializers import Serializer

from ansible_ai_connect.ai.api.model_pipelines.config_providers import Configuration
from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY
from ansible_ai_connect.main.settings.types import t_model_mesh_api_type

PIPELINE_CONFIG_TYPE = TypeVar("PIPELINE_CONFIG_TYPE")


class BaseConfigSerializer(serializers.Serializer):
    inference_url = serializers.CharField(required=True)
    model_id = serializers.CharField(required=False, allow_null=True, default=None)
    timeout = serializers.IntegerField(required=False, allow_null=True, default=None)


class PipelineConfigurationSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(required=True, choices=get_args(t_model_mesh_api_type))

    def to_internal_value(self, data):
        provider_part = super().to_internal_value(data)
        serializer = REGISTRY[provider_part["provider"]][Serializer](data=data["config"])
        serializer.is_valid(raise_exception=True)

        return {**provider_part, "config": serializer.validated_data}


class ConfigurationSerializer(serializers.Serializer):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from ansible_ai_connect.ai.api.model_pipelines.pipelines import MetaData
        from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY_ENTRY

        pipelines = list(filter(lambda p: issubclass(p, MetaData), REGISTRY_ENTRY.keys()))
        pipeline_fields: dict = {}
        for pipeline in pipelines:
            pipeline_fields[pipeline.__name__] = PipelineConfigurationSerializer(
                required=False, default={"provider": "nop", "config": {}}
            )
        self.pipeline_fields = pipeline_fields

    def get_fields(self):
        return self.pipeline_fields

    def create(self, validated_data):
        return Configuration(**validated_data)
