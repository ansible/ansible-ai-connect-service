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

from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    MetaData,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleGeneration,
)
from ansible_ai_connect.main.settings.base import t_model_mesh_api_type

logger = logging.getLogger(__name__)

EMPTY_PIPE = {
    MetaData: None,
    ModelPipelineCompletions: None,
    ModelPipelineContentMatch: None,
    ModelPipelinePlaybookGeneration: None,
    ModelPipelineRoleGeneration: None,
    ModelPipelinePlaybookExplanation: None,
}
PIPELINES = {}
for model_mesh_api_type in get_args(t_model_mesh_api_type):
    PIPELINES[model_mesh_api_type] = deepcopy(EMPTY_PIPE)


class Register:
    def __init__(self, api_type: t_model_mesh_api_type):
        self.api_type = api_type

    def __call__(self, cls):
        for pipe in EMPTY_PIPE.keys():
            # All pipes are sub classes of MetaData, checking it at the end
            if not (pipe == MetaData) and issubclass(cls, pipe):
                PIPELINES[self.api_type][pipe] = cls
                return cls
        if issubclass(cls, MetaData):
            PIPELINES[self.api_type][MetaData] = cls
        return cls
