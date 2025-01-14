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
from typing import Optional

from rest_framework import serializers

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    BaseConfig,
    PipelineConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import Register

# ANSIBLE_AI_MODEL_MESH_API_URL
# DUMMY_MODEL_RESPONSE_LATENCY_USE_JITTER
# DUMMY_MODEL_RESPONSE_MAX_LATENCY_MSEC
# DUMMY_MODEL_RESPONSE_BODY

DEFAULT_BODY = (
    '{"predictions":'
    '["ansible.builtin.apt:\\n  name: nginx\\n  update_cache: true\\n  state: present\\n"]}'
)


class DummyConfiguration(BaseConfig):

    def __init__(
        self,
        enable_health_check: Optional[bool],
        latency_use_jitter: bool,
        latency_max_msec: int,
        body: str,
    ):
        super().__init__("dummy", "dummy", None, enable_health_check)
        self.latency_use_jitter = latency_use_jitter
        self.latency_max_msec = latency_max_msec
        self.body = body


@Register(api_type="dummy")
class DummyPipelineConfiguration(PipelineConfiguration[DummyConfiguration]):

    def __init__(self, **kwargs):
        super().__init__(
            "dummy",
            DummyConfiguration(
                enable_health_check=kwargs["enable_health_check"],
                latency_use_jitter=kwargs["latency_use_jitter"],
                latency_max_msec=kwargs["latency_max_msec"],
                body=kwargs["body"],
            ),
        )


@Register(api_type="dummy")
class DummyConfigurationSerializer(serializers.Serializer):
    enable_health_check = serializers.BooleanField(required=False, default=False)
    latency_use_jitter = serializers.BooleanField(required=False, default=False)
    latency_max_msec = serializers.IntegerField(required=False, default=3000)
    body = serializers.CharField(
        required=False, allow_null=True, allow_blank=True, default=DEFAULT_BODY
    )
