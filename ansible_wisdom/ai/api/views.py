# Create your views here.
import logging

from django.apps import apps
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .data.data_model import APIPayload, ModelMeshPayload
from .serializers import CompletionRequestSerializer, CompletionResponseSerializer

logger = logging.getLogger(__name__)


class CompletionsUserRateThrottle(UserRateThrottle):
    rate = settings.COMPLETION_USER_RATE_THROTTLE


class Completions(APIView):
    """
    Returns inline code suggestions based on a given Ansible editor context.
    """

    throttle_classes = [CompletionsUserRateThrottle]

    @extend_schema(
        request=CompletionRequestSerializer,
        responses={
            200: CompletionResponseSerializer,
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
        },
        summary="Inline code suggestions",
    )
    def post(self, request) -> Response:
        model_mesh_client = apps.get_app_config("ai").model_mesh_client
        logger.debug(f"request payload from client: {request.data}")
        request_serializer = CompletionRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        payload = APIPayload(**request_serializer.validated_data)
        model_name = payload.model_name
        model_mesh_payload = ModelMeshPayload(
            instances=[
                {
                    "prompt": payload.prompt,
                    "context": payload.context,
                    "userId": str(payload.userId) if payload.userId else None,
                    "suggestionId": str(payload.suggestionId) if payload.suggestionId else None,
                }
            ]
        )
        data = model_mesh_payload.dict()
        logger.debug(
            f"input to inference for user id {payload.userId} "
            f"and suggestion id {payload.suggestionId}:\n{data}"
        )
        response = model_mesh_client.infer(data, model_name=model_name)
        response_serializer = CompletionResponseSerializer(data=response.data)
        response_serializer.is_valid(raise_exception=True)
        logger.debug(
            f"response from inference for user id {payload.userId} "
            f"and suggestion id {payload.suggestionId}:\n{response.data}"
        )
        return response
