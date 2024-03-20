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
