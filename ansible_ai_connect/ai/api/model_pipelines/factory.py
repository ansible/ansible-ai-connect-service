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

import logging
from copy import deepcopy
from typing import Type

from django.conf import settings

from ansible_ai_connect.ai.api.model_pipelines.config_loader import load_config
from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    PipelineConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.config_providers import Configuration
from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import NopMetaData
from ansible_ai_connect.ai.api.model_pipelines.registry import REGISTRY, REGISTRY_ENTRY
from ansible_ai_connect.ai.api.model_pipelines.types import PIPELINE_TYPE

logger = logging.getLogger(__name__)


class ModelPipelineFactory:

    cache = {}

    def __init__(self):
        self.cache = deepcopy(REGISTRY_ENTRY)
        if not settings.DEBUG_FORCE_PIPELINE_RELOAD:
            self.pipelines_config: Configuration = load_config()

    def get_pipeline(self, pipeline_type: Type[PIPELINE_TYPE]) -> PIPELINE_TYPE:
        if settings.DEBUG_FORCE_PIPELINE_RELOAD:
            self.pipelines_config: Configuration = load_config()
        # We currently cache the pipeline implementation as we don't support
        # the use of different providers for different requests and each resides
        # in the same process space as ansible-ai-connect-service. This could
        # change when (if) we move to a fully distributed deployment model.
        if self.cache[pipeline_type]:
            return self.cache[pipeline_type]

        try:
            # Get the configuration for the requested pipeline
            pipeline_config: PipelineConfiguration = self.pipelines_config[pipeline_type.__name__]

            # Get the pipeline class for the configured provider
            pipelines = REGISTRY[pipeline_config.provider]
            pipeline = pipelines[pipeline_type]

            # Ensure NOP instances are created with NOP configuration
            if issubclass(pipeline, NopMetaData):
                logger.info(f"Using NOP implementation for '{pipeline_type.__name__}'.")
                pipelines = REGISTRY["nop"]
                pipeline_config = pipelines[PipelineConfiguration]()

            # Construct an instance of the pipeline class with the applicable configuration
            self.cache[pipeline_type] = pipeline(pipeline_config.config)

        except KeyError:
            pass

        return self.cache[pipeline_type]
