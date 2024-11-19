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
from abc import ABCMeta
from typing import Generic, Optional, TypeVar

from ansible_ai_connect.main.settings.types import t_model_mesh_api_type


class BaseConfig(metaclass=ABCMeta):
    def __init__(
        self,
        inference_url: str,
        model_id: str,
        timeout: Optional[int],
    ):
        self.inference_url = inference_url
        self.model_id = model_id
        self.timeout = timeout

    inference_url: str
    model_id: str
    timeout: Optional[int]


PIPELINE_CONFIGURATION = TypeVar("PIPELINE_CONFIGURATION", bound=BaseConfig)


class PipelineConfiguration(Generic[PIPELINE_CONFIGURATION], metaclass=ABCMeta):

    def __init__(self, provider: t_model_mesh_api_type, config: PIPELINE_CONFIGURATION):
        self.provider = provider
        self.config = config

    provider: t_model_mesh_api_type
    config: PIPELINE_CONFIGURATION
