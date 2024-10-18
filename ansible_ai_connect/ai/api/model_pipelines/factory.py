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
from typing import Type

from django.conf import settings

from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PIPELINE_TYPE,
    MetaData,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
)
from ansible_ai_connect.ai.api.model_pipelines.registry import PIPELINES

logger = logging.getLogger(__name__)


class ModelPipelineFactory:

    cache = {}

    def __init__(self):
        self.cache = {
            MetaData: None,
            ModelPipelineCompletions: None,
            ModelPipelineContentMatch: None,
            ModelPipelinePlaybookGeneration: None,
            ModelPipelinePlaybookExplanation: None,
        }

    def get_pipeline(self, pipeline: Type[PIPELINE_TYPE]) -> PIPELINE_TYPE:
        if not settings.ANSIBLE_AI_MODEL_MESH_API_TYPE:
            raise ValueError(
                f"Invalid ANSIBLE_AI_MODEL_MESH_API_TYPE: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        # We currently cache the pipeline implementation as we don't support
        # the use of different providers for different requests and each resides
        # in the same process space as ansible-ai-connect-service. This could
        # change when (if) we move to a fully distributed deployment model.
        if self.cache[pipeline]:
            return self.cache[pipeline]

        try:
            pipelines = PIPELINES[settings.ANSIBLE_AI_MODEL_MESH_API_TYPE]
            self.cache[pipeline] = pipelines[pipeline](
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL
            )
        except KeyError:
            pass

        if self.cache[pipeline] is None:
            logger.exception(
                f"Pipeline for '{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}, "
                f"'{pipeline.__name__}' not found."
            )
            raise ValueError(f"Invalid Pipeline type: {pipeline}")

        return self.cache[pipeline]
