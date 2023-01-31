import json
import logging
import time

import yaml
from django.apps import apps
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAdminUser
from rest_framework.renderers import JSONRenderer, TemplateHTMLRenderer
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from segment import analytics
from yaml.error import MarkedYAMLError

from ..models import AIModel
from .data.data_model import APIPayload, ModelMeshPayload
from .serializers import (
    AICompletionSerializer,
    AIModelSerializer,
    CompletionRequestSerializer,
    CompletionResponseSerializer,
)

logger = logging.getLogger(__name__)


class CompletionsUserRateThrottle(UserRateThrottle):
    rate = settings.COMPLETION_USER_RATE_THROTTLE


class Completions(APIView):
    """
    Returns inline code suggestions based on a given Ansible editor context.
    """

    # OAUTH: remove the conditional
    if settings.OAUTH2_ENABLE:
        from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope
        from rest_framework import permissions

        permission_classes = [permissions.IsAuthenticated, TokenHasReadWriteScope]
    throttle_classes = [CompletionsUserRateThrottle]
    renderer_classes = [JSONRenderer, TemplateHTMLRenderer]
    template_name = "completions.html"

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
        """model_actual = request.query_params.get(
            "model", request.data.get("model_name", None)
        )"""
        model_mesh_client = self.initialize_model_mesh_client(request.query_parameters.get("model"))
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
        logger.debug(f"input to inference for suggestion id {payload.suggestionId}:\n{data}")
        response = model_mesh_client.infer(data, model_name=model_name)
        response_serializer = CompletionResponseSerializer(data=response.data)
        response_serializer.is_valid(raise_exception=True)
        logger.debug(
            f"response from inference for "
            f"suggestion id {payload.suggestionId}:\n{response.data}"
        )
        response.data = self.postprocess(
            response.data, payload.prompt, payload.context, payload.userId, payload.suggestionId
        )
        logger.debug(
            f"response from postprocess for "
            f"suggestion id {payload.suggestionId}:\n{response.data}"
        )
        if request.accepted_renderer.media_type == "text/html":
            return Response(
                {
                    "serializer": AICompletionSerializer(
                        {
                            "prompt": payload.prompt,
                            "context": payload.context,
                            "model_name": model_actual,
                            "response_data": response.data,
                        }
                    )
                }
            )
        return response

    def initialize_model_mesh_client(self, modelSelector=None):
        if modelSelector is not None:
            model_actual = AIModel.objects.filter(name=modelSelector)
            if model_actual.exists():
                model_actual = model_actual[0]
                model_api_type = model_actual.model_mesh_api_type
                model_inference_url = model_actual.inference_url
                model_management_url = model_actual.management_url
            else:
                raise ValueError(f"Invalid model name: {modelSelector}")
        else:
            model_api_type = settings.ANSIBLE_AI_MODEL_MESH_API_TYPE
            model_inference_url = settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL
            model_management_url = settings.ANSIBLE_AI_MODEL_MESH_MANAGEMENT_URL
        if model_api_type == AIModel.ModelMeshType.GRPC:
            model_client = GrpcClient
        elif model_api_type == AIModel.ModelMeshType.HTTP:
            model_client = HttpClient
        else:
            raise ValueError(f"Invalid model mesh client type: {model_api_type}")
        return model_client(
            inference_url=model_inference_url,
            management_url=model_management_url,
        )

    def postprocess(self, recommendation, prompt, context, user_id, suggestion_id):
        ari_caller = apps.get_app_config("ai").ari_caller

        if ari_caller:
            for i, recommendation_yaml in enumerate(recommendation["predictions"]):
                start_time = time.time()
                recommendation_problem = None
                # check if the recommendation_yaml is a valid YAML
                try:
                    _ = yaml.safe_load(recommendation_yaml)
                except Exception as exc:
                    logger.exception(
                        f'the recommendation_yaml is not a valid YAML: ' f'\n{recommendation_yaml}'
                    )
                    recommendation_problem = exc

                exception = None
                postprocessed_yaml = None
                postprocess_detail = None
                try:
                    # if the recommentation is not a valid yaml, record it as an exception
                    if recommendation_problem:
                        exception = recommendation_problem
                    else:
                        # otherwise, do postprocess here
                        logger.debug(
                            f"suggestion id: {suggestion_id}, "
                            f"original recommendation: \n{recommendation_yaml}"
                        )
                        postprocessed_yaml, postprocess_detail = ari_caller.postprocess(
                            recommendation_yaml, prompt, context
                        )
                        logger.debug(
                            f"suggestion id: {suggestion_id}, "
                            f"post-processed recommendation: \n{postprocessed_yaml}"
                        )
                        logger.debug(
                            f"suggestion id: {suggestion_id}, "
                            f"post-process detail: {json.dumps(postprocess_detail)}"
                        )
                        recommendation["predictions"][i] = postprocessed_yaml
                except Exception as exc:
                    exception = exc
                    # return the original recommendation if we failed to postprocess
                    logger.exception(
                        f'failed to postprocess recommendation with prompt {prompt} '
                        f'context {context} and model recommendation {recommendation}'
                    )
                finally:
                    self.write_to_segment(
                        user_id,
                        suggestion_id,
                        recommendation_yaml,
                        postprocessed_yaml,
                        postprocess_detail,
                        exception,
                        start_time,
                    )
                    continue
        else:
            logger.warn('skipped post processing because ari was not initialized')

        return recommendation

    def write_to_segment(
        self,
        user_id,
        suggestion_id,
        recommendation_yaml,
        postprocessed_yaml,
        postprocess_detail,
        exception,
        start_time,
    ):
        if settings.SEGMENT_WRITE_KEY:
            duration = round((time.time() - start_time) * 1000, 2)
            problem = exception.problem if isinstance(exception, MarkedYAMLError) else None
            event = {
                "exception": exception is not None,
                "problem": problem,
                "duration": duration,
                "recommendation": recommendation_yaml,
                "postprocessed": postprocessed_yaml,
                "detail": postprocess_detail,
                "suggestionId": str(suggestion_id) if suggestion_id else None,
            }

            analytics.write_key = settings.SEGMENT_WRITE_KEY
            analytics.debug = settings.DEBUG
            # analytics.send = False  # for code development only

            analytics.track(
                str(user_id) if user_id else 'unknown',
                "wisdomServicePostprocessingEvent",
                event,
            )

    def get(self, request) -> Response:
        serializer = AICompletionSerializer()
        return Response({"serializer": serializer})
        # model_mesh_client = self.initialize_model_mesh_client(
        #     request.query_parameters.get("model"))
        # model_name = request.query_parameters.get("model_name")
        # response = model_mesh_client.status(model_name=model_name)
        # return response


class AIModelList(ListCreateAPIView):
    queryset = AIModel.objects.all()
    serializer_class = AIModelSerializer
    permissions_classes = [IsAdminUser]
