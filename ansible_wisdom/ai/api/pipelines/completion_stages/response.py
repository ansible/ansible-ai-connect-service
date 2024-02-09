import logging
from enum import Enum

from rest_framework.response import Response

from ansible_wisdom.ai.api.pipelines.common import (
    InternalServerError,
    PipelineElement,
    completions_return_code,
    process_error_count,
)
from ansible_wisdom.ai.api.pipelines.completion_context import CompletionContext
from ansible_wisdom.ai.api.serializers import CompletionResponseSerializer

logger = logging.getLogger(__name__)


class CompletionsPromptType(str, Enum):
    MULTITASK = "MULTITASK"
    SINGLETASK = "SINGLETASK"


class ResponseStage(PipelineElement):
    def process(self, context: CompletionContext) -> None:
        payload = context.payload
        predictions = context.predictions
        post_processed_predictions = context.post_processed_predictions
        tasks_results = context.task_results
        try:
            response_data = {
                "predictions": post_processed_predictions["predictions"],
                "model": predictions['model_id'],
                "suggestionId": payload.suggestionId,
            }
            response_serializer = CompletionResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)
        except Exception:
            process_error_count.labels(stage='completion-response_serialization_validation').inc()
            logger.exception(
                f"error serializing final response for suggestion {payload.suggestionId}"
            )
            raise InternalServerError
        completions_return_code.labels(code=200).inc()
        response = Response(response_data, status=200)

        # add fields for telemetry only, not response data
        # Note: Currently we return an array of predictions, but there's only ever one.
        # The tasks array added to the completion event is representative of the first (only)
        # entry in the predictions array
        response.tasks = tasks_results

        context.response = response
