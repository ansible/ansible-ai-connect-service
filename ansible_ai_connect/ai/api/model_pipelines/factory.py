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

from ansible_ai_connect.ai.api.model_pipelines.pipelines import PIPELINE_TYPE
from ansible_ai_connect.ai.api.model_pipelines.registry import EMPTY_PIPE, PIPELINES

logger = logging.getLogger(__name__)


class ModelPipelineFactory:

    cache = {}

    def __init__(self):
        self.cache = deepcopy(EMPTY_PIPE)

    def get_pipeline(self, pipeline_type: Type[PIPELINE_TYPE]) -> PIPELINE_TYPE:
        if not settings.ANSIBLE_AI_MODEL_MESH_API_TYPE:
            raise ValueError(
                f"Invalid ANSIBLE_AI_MODEL_MESH_API_TYPE: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        # We currently cache the pipeline implementation as we don't support
        # the use of different providers for different requests and each resides
        # in the same process space as ansible-ai-connect-service. This could
        # change when (if) we move to a fully distributed deployment model.
        if self.cache[pipeline_type]:
            return self.cache[pipeline_type]

        try:
            pipelines = PIPELINES[settings.ANSIBLE_AI_MODEL_MESH_API_TYPE]
            pipeline = pipelines[pipeline_type]
            # No explicit implementation defined; fallback to NOP
            if pipeline is None:
                pipelines = PIPELINES["nop"]
                pipeline = pipelines[pipeline_type]
                logger.info(
                    f"Pipeline for '{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}', "
                    f"'{pipeline_type.__name__}' not found. Defaulting to NOP implementation."
                )

            self.cache[pipeline_type] = pipeline(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL
            )
        except KeyError:
            pass

        return self.cache[pipeline_type]
