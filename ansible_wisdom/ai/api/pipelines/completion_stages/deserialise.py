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

from ansible_ai_connect.ai.api import formatter as fmtr
from ansible_ai_connect.ai.api.data.data_model import APIPayload
from ansible_ai_connect.ai.api.exceptions import process_error_count
from ansible_ai_connect.ai.api.pipelines.common import PipelineElement
from ansible_ai_connect.ai.api.pipelines.completion_context import CompletionContext
from ansible_ai_connect.ai.api.pipelines.completion_stages.response import (
    CompletionsPromptType,
)
from ansible_ai_connect.ai.api.serializers import CompletionRequestSerializer

logger = logging.getLogger(__name__)


class DeserializeStage(PipelineElement):
    def process(self, context: CompletionContext) -> None:
        request = context.request
        request._request._suggestion_id = request.data.get("suggestionId")

        request_serializer = CompletionRequestSerializer(
            data=request.data, context={"request": request}
        )

        try:
            request_serializer.is_valid(raise_exception=True)
            request._request._suggestion_id = str(request_serializer.validated_data["suggestionId"])
            request._request._ansible_extension_version = str(
                request_serializer.validated_data.get("metadata", {}).get(
                    "ansibleExtensionVersion", None
                )
            )
            context.metadata = request_serializer.validated_data.get("metadata", {})
            prompt = request_serializer.validated_data.get("prompt")
        except Exception as exc:
            process_error_count.labels(stage="completion-request_serialization_validation").inc()
            logger.warning(f"failed to validate request:\nException:\n{exc}")
            prompt, _ = fmtr.extract_prompt_and_context(
                request_serializer.initial_data.get("prompt")
            )
            raise exc
        finally:
            # stash the prompt type for completions event
            request._request._prompt_type = (
                CompletionsPromptType.MULTITASK.value
                if fmtr.is_multi_task_prompt(prompt)
                else CompletionsPromptType.SINGLETASK.value
            )

        payload = APIPayload(**request_serializer.validated_data)
        payload.original_prompt = request.data.get("prompt", "")

        context.payload = payload
