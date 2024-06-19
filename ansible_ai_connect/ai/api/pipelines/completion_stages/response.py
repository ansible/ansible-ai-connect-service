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
from enum import Enum

from rest_framework.response import Response

from ansible_ai_connect.ai.api.exceptions import (
    InternalServerError,
    completions_return_code,
    process_error_count,
)
from ansible_ai_connect.ai.api.pipelines.common import PipelineElement
from ansible_ai_connect.ai.api.pipelines.completion_context import CompletionContext
from ansible_ai_connect.ai.api.serializers import CompletionResponseSerializer

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
                "suggestionId": payload.suggestionId,
            }
            if model_from_prediction := predictions.get("model_id"):
                response_data["model"] = model_from_prediction

            response_serializer = CompletionResponseSerializer(data=response_data)
            response_serializer.is_valid(raise_exception=True)
        except Exception:
            process_error_count.labels(stage="completion-response_serialization_validation").inc()
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
        # https://github.com/ansible/ansible-ai-connect-service/blob/0e083a83fab57e6567197697bad60d306c6e06eb/ansible_ai_connect/ai/api/pipelines/completion_stages/response.py#L64
        response.tasks = tasks_results

        context.response = response
