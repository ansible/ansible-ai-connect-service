import logging

from ai.api import formatter as fmtr
from ai.api.data.data_model import APIPayload
from ai.api.pipelines.common import PipelineElement, process_error_count
from ai.api.pipelines.completion_context import CompletionContext
from ai.api.pipelines.completion_stages.response import CompletionsPromptType
from ai.api.serializers import CompletionRequestSerializer

logger = logging.getLogger(__name__)


class DeserializeStage(PipelineElement):
    def process(self, context: CompletionContext) -> None:
        request = context.request
        request._request._suggestion_id = request.data.get('suggestionId')

        request_serializer = CompletionRequestSerializer(
            data=request.data, context={'request': request}
        )

        try:
            request_serializer.is_valid(raise_exception=True)
            request._request._suggestion_id = str(request_serializer.validated_data['suggestionId'])
            context.metadata = request_serializer.validated_data.get('metadata', {})
            prompt = request_serializer.validated_data.get("prompt")
        except Exception as exc:
            process_error_count.labels(stage='completion-request_serialization_validation').inc()
            logger.warning(f'failed to validate request:\nException:\n{exc}')
            prompt, _ = fmtr.extract_prompt_and_context(
                request_serializer.initial_data.get('prompt')
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
        payload.userId = request.user.uuid

        context.payload = payload
