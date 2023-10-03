import logging

from ai.api.pipelines.common import InternalServerError, Pipeline
from ai.api.pipelines.completion_stages.deserialise import DeserializeStage
from ai.api.pipelines.completion_stages.inference import InferenceStage
from ai.api.pipelines.completion_stages.post_process import PostProcessStage
from ai.api.pipelines.completion_stages.pre_process import PreProcessStage
from ai.api.pipelines.completion_stages.response import ResponseStage
from rest_framework.request import Request
from rest_framework.response import Response

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
            pe.process(completion_context=self.context)
            if self.context.response:
                return self.context.response
        raise InternalServerError(
            "Pipeline terminated abnormally. 'response' not found in context."
        )
