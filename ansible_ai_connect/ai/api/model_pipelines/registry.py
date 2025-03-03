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
from typing import get_args

from rest_framework.serializers import Serializer

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    PipelineConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    MetaData,
    ModelPipelineChatBot,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    ModelPipelineStreamingChatBot,
)
from ansible_ai_connect.main.settings.types import t_model_mesh_api_type

logger = logging.getLogger(__name__)

REGISTRY_ENTRY = dict.fromkeys(
    [
        MetaData,
        ModelPipelineCompletions,
        ModelPipelineContentMatch,
        ModelPipelinePlaybookGeneration,
        ModelPipelineRoleGeneration,
        ModelPipelinePlaybookExplanation,
        ModelPipelineRoleExplanation,
        ModelPipelineChatBot,
        ModelPipelineStreamingChatBot,
        PipelineConfiguration,
        Serializer,
    ]
)
REGISTRY = {
    model_mesh_api_type: deepcopy(REGISTRY_ENTRY)
    for model_mesh_api_type in get_args(t_model_mesh_api_type)
}


class Register:
    def __init__(self, api_type: t_model_mesh_api_type):
        self.api_type = api_type

    def __call__(self, cls):
        for pipe in REGISTRY_ENTRY.keys():
            # All pipes are subclasses of MetaData, checking it at the end
            if not (pipe == MetaData) and issubclass(cls, pipe):
                REGISTRY[self.api_type][pipe] = cls
                return cls
        if issubclass(cls, MetaData):
            REGISTRY[self.api_type][MetaData] = cls
        elif issubclass(cls, PipelineConfiguration):
            REGISTRY[self.api_type][PipelineConfiguration] = cls
        elif issubclass(cls, Serializer):
            REGISTRY[self.api_type][Serializer] = cls
        return cls


def set_defaults():

    def set_defaults_for_api_type(pipeline_provider):

        def v_or_default(k, v):
            defaults = REGISTRY["nop"]
            if v is None:
                logger.warning(
                    f"'{k.alias()}' is not available for provider '{pipeline_provider}',"
                    " failing back to 'nop'"
                )
                return defaults[k]
            return v

        return {k: v_or_default(k, v) for k, v in REGISTRY[pipeline_provider].items()}

    for model_mesh_api_type in get_args(t_model_mesh_api_type):
        REGISTRY[model_mesh_api_type] = set_defaults_for_api_type(model_mesh_api_type)
