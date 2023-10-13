import logging

from ai.api.data.data_model import APIPayload
from ai.api.pipelines.common import PipelineElement, process_error_count
from ai.api.pipelines.completion_context import CompletionContext
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
        except Exception as exc:
            process_error_count.labels(stage='request_serialization_validation').inc()
            logger.warning(f'failed to validate request:\nException:\n{exc}')
            raise exc

        payload = APIPayload(**request_serializer.validated_data)
        payload.userId = request.user.uuid

        context.payload = payload
