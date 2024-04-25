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

from rest_framework.request import Request
from rest_framework.response import Response

from ansible_wisdom.ai.api.exceptions import InternalServerError
from ansible_wisdom.ai.api.pipelines.common import Pipeline
from ansible_wisdom.ai.api.pipelines.completion_stages.deserialise import (
    DeserializeStage,
)
from ansible_wisdom.ai.api.pipelines.completion_stages.inference import InferenceStage
from ansible_wisdom.ai.api.pipelines.completion_stages.post_process import (
    PostProcessStage,
)
from ansible_wisdom.ai.api.pipelines.completion_stages.pre_process import (
    PreProcessStage,
)
from ansible_wisdom.ai.api.pipelines.completion_stages.response import ResponseStage

from .completion_context import CompletionContext

logger = logging.getLogger(__name__)


class CompletionsPipeline(Pipeline[Response, CompletionContext]):
    def __init__(self, request: Request):
        self.context = CompletionContext(request=request)
        super().__init__(
            [
                DeserializeStage(),
                PreProcessStage(),
                InferenceStage(),
                PostProcessStage(),
                ResponseStage(),
            ],
            self.context,
        )

    def execute(self) -> Response:
        for pe in self.pipeline:
            pe.process(context=self.context)
            if self.context.response:
                return self.context.response
        raise InternalServerError(
            "Pipeline terminated abnormally. 'response' not found in context."
        )
