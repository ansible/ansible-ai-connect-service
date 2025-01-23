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
from typing import Dict

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    PipelineConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import get_registry_entry


class Configuration(Dict):

    def __init__(self, **kwargs):
        super().__init__(kwargs)

        for k, v in self.items():
            pipeline_config = v["config"]
            pipeline_provider = v["provider"]
            registry_entry = get_registry_entry(pipeline_provider)
            config_class = registry_entry[PipelineConfiguration]
            config_instance = config_class(**pipeline_config)
            self[k] = config_instance
