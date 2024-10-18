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

from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    MetaData,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
)
from ansible_ai_connect.main.settings.base import t_model_mesh_api_type

logger = logging.getLogger(__name__)

PIPELINES = {
    "grpc": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "http": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "dummy": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "wca": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "wca-onprem": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "wca-dummy": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "ollama": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "llamacpp": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
    "bam": {
        MetaData: None,
        ModelPipelineCompletions: None,
        ModelPipelineContentMatch: None,
        ModelPipelinePlaybookGeneration: None,
        ModelPipelinePlaybookExplanation: None,
    },
}


class Register:
    def __init__(self, api_type: t_model_mesh_api_type):
        self.api_type = api_type

    def __call__(self, cls):
        if issubclass(cls, ModelPipelineCompletions):
            PIPELINES[self.api_type][ModelPipelineCompletions] = cls
        elif issubclass(cls, ModelPipelineContentMatch):
            PIPELINES[self.api_type][ModelPipelineContentMatch] = cls
        elif issubclass(cls, ModelPipelinePlaybookGeneration):
            PIPELINES[self.api_type][ModelPipelinePlaybookGeneration] = cls
        elif issubclass(cls, ModelPipelinePlaybookExplanation):
            PIPELINES[self.api_type][ModelPipelinePlaybookExplanation] = cls
        elif issubclass(cls, MetaData):
            PIPELINES[self.api_type][MetaData] = cls
        return cls
