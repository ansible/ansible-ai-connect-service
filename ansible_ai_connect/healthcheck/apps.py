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

from django.apps import AppConfig
from health_check.plugins import plugin_dir


class HealthCheckAppConfig(AppConfig):
    name = "ansible_ai_connect.healthcheck"

    def ready(self):
        from ansible_ai_connect.ai.api.model_pipelines.pipelines import ModelPipeline
        from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY_ENTRY

        from .backends import (
            AuthorizationHealthCheck,
            AWSSecretManagerHealthCheck,
            ModelPipelineHealthCheck,
        )

        plugin_dir.register(AWSSecretManagerHealthCheck)
        plugin_dir.register(AuthorizationHealthCheck)
        for pipeline in REGISTRY_ENTRY.keys():
            if issubclass(pipeline, ModelPipeline):
                plugin_dir.register(ModelPipelineHealthCheck, pipeline_type=pipeline)
