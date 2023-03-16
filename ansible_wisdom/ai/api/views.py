import json
import logging
import time

import yaml
from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django.http import QueryDict
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework import status as rest_framework_status
from rest_framework.exceptions import APIException
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView
from yaml.error import MarkedYAMLError

from .. import search as ai_search
from . import formatter as fmtr
from .data.data_model import APIPayload, ModelMeshPayload
from .model_client.exceptions import ModelTimeoutError
from .permissions import AcceptedTermsPermission
from .serializers import (
    AnsibleContentFeedback,
    AttributionRequestSerializer,
    AttributionResponseSerializer,
    CompletionRequestSerializer,
    CompletionResponseSerializer,
    FeedbackRequestSerializer,
    InlineSuggestionFeedback,
)
from .utils.segment import send_segment_event

logger = logging.getLogger(__name__)


class CompletionsUserRateThrottle(UserRateThrottle):
    rate = settings.COMPLETION_USER_RATE_THROTTLE


class PostprocessException(APIException):
    status_code = 204
    error_type = 'postprocess_error'


class ModelTimeoutException(APIException):
    status_code = 204
    error_type = 'model_timeout'


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = {"message": "An error occurred attempting to complete the request"}


class InternalServerError(APIException):
    status_code = 500
    default_detail = {"message": "An error occurred attempting to complete the request"}


def anonymize_request_data(data):
    if isinstance(data, QueryDict):
        # See: https://github.com/ansible/ansible-wisdom-service/pull/201#issuecomment-1483015431  # noqa: E501
        new_data = data.copy()
        new_data.update(anonymizer.anonymize_struct(data.dict()))
    else:
        new_data = anonymizer.anonymize_struct(data)
    return new_data


class Completions(APIView):
    """
    Returns inline code suggestions based on a given Ansible editor context.
    """

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']

    throttle_classes = [CompletionsUserRateThrottle]

    @extend_schema(
        request=CompletionRequestSerializer,
        responses={
            200: CompletionResponseSerializer,
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Inline code suggestions",
    )
    def post(self, request) -> Response:
        model_mesh_client = apps.get_app_config("ai").model_mesh_client
        data = anonymize_request_data(request.data)
        request_serializer = CompletionRequestSerializer(data=data)
        request_serializer.is_valid(raise_exception=True)
        payload = APIPayload(**request_serializer.validated_data)
        payload.userId = request.user.uuid
        model_name = payload.model_name
        original_indent = payload.prompt.find("name")

        try:
            payload.context, payload.prompt = self.preprocess(payload.context, payload.prompt)
        except Exception as exc:
            # return the original prompt, context
            logger.error(
                f'failed to preprocess:\n{payload.context}{payload.prompt}\nException:\n{exc}'
            )
            return Response({'message': 'Request contains invalid yaml'}, status=400)
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

        try:
            predictions = model_mesh_client.infer(data, model_name=model_name)
        except ModelTimeoutError:
            raise ModelTimeoutException
        except Exception:
            logger.exception(f"error requesting completion for suggestion {payload.suggestionId}")
            raise ServiceUnavailable

        logger.debug(
            f"response from inference for " f"suggestion id {payload.suggestionId}:\n{predictions}"
        )
        postprocessed_predictions = None
        try:
            postprocessed_predictions = self.postprocess(
                predictions,
                payload.prompt,
                payload.context,
                payload.userId,
                payload.suggestionId,
                indent=original_indent,
            )
        except Exception:
            logger.exception(
                f"error postprocessing prediction for suggestion {payload.suggestionId}"
            )
            raise PostprocessException

        logger.debug(
            f"response from postprocess for "
            f"suggestion id {payload.suggestionId}:\n{postprocessed_predictions}"
        )
        try:
            response_serializer = CompletionResponseSerializer(data=postprocessed_predictions)
            response_serializer.is_valid(raise_exception=True)
        except Exception:
            logger.exception(
                f"error serializing final response for suggestion {payload.suggestionId}"
            )
            raise InternalServerError
        return Response(postprocessed_predictions, status=200)

    def preprocess(self, context, prompt):
        context, prompt = fmtr.preprocess(context, prompt)

        return context, prompt

    def postprocess(self, recommendation, prompt, context, user_id, suggestion_id, indent):
        ari_caller = apps.get_app_config("ai").ari_caller
        if not ari_caller:
            logger.warn('skipped ari post processing because ari was not initialized')

        for i, recommendation_yaml in enumerate(recommendation["predictions"]):
            if ari_caller:
                start_time = time.time()
                truncated_yaml = None
                recommendation_problem = None
                # check if the recommendation_yaml is a valid YAML
                try:
                    _ = yaml.safe_load(recommendation_yaml)
                except Exception as exc:
                    # the recommendation YAML can have a broken line at the bottom
                    # because the token size of the wisdom model is limited.
                    # so we try truncating the last line of the recommendation here.
                    truncated, truncated_yaml = truncate_recommendation_yaml(recommendation_yaml)
                    if truncated:
                        try:
                            _ = yaml.safe_load(truncated_yaml)
                        except Exception as exc:
                            recommendation_problem = exc
                    else:
                        recommendation_problem = exc
                    if recommendation_problem:
                        logger.error(
                            f'recommendation_yaml is not a valid YAML: '
                            f'\n{recommendation_yaml}'
                            f'\nException:\n{recommendation_problem}'
                        )

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
                        if truncated_yaml:
                            logger.debug(
                                f"suggestion id: {suggestion_id}, "
                                f"truncated recommendation: \n{truncated_yaml}"
                            )
                            recommendation_yaml = truncated_yaml
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
                        truncated_yaml,
                        postprocessed_yaml,
                        postprocess_detail,
                        exception,
                        start_time,
                    )
                    if exception:
                        raise exception
            # restore original indentation
            indented_yaml = fmtr.restore_indentation(recommendation["predictions"][i], indent)
            recommendation["predictions"][i] = indented_yaml
            logger.debug(
                f"suggestion id: {suggestion_id}, " f"indented recommendation: \n{indented_yaml}"
            )
            continue
        return recommendation

    def write_to_segment(
        self,
        user_id,
        suggestion_id,
        recommendation_yaml,
        truncated_yaml,
        postprocessed_yaml,
        postprocess_detail,
        exception,
        start_time,
    ):
        duration = round((time.time() - start_time) * 1000, 2)
        problem = exception.problem if isinstance(exception, MarkedYAMLError) else None
        event = {
            "exception": exception is not None,
            "problem": problem,
            "duration": duration,
            "recommendation": recommendation_yaml,
            "truncated": truncated_yaml,
            "postprocessed": postprocessed_yaml,
            "detail": postprocess_detail,
            "suggestionId": str(suggestion_id) if suggestion_id else None,
        }
        send_segment_event(event, "wisdomServicePostprocessingEvent", user_id)


class Feedback(APIView):
    """
    Feedback API for the AI service
    """

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']

    @extend_schema(
        request=FeedbackRequestSerializer,
        responses={
            200: OpenApiResponse(description='Success'),
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
        },
        summary="Feedback API for the AI service",
    )
    def post(self, request) -> Response:
        exception = None
        user_id = str(request.user.uuid)
        inline_suggestion_data = {}
        ansible_content_data = {}
        data = anonymize_request_data(request.data)
        logger.info(f"feedback request payload from client: {data}")
        try:
            request_serializer = FeedbackRequestSerializer(data=data)
            request_serializer.is_valid(raise_exception=True)
            validated_data = request_serializer.validated_data
            inline_suggestion_data = validated_data.get("inlineSuggestion")
            ansible_content_data = validated_data.get("ansibleContent")
            return Response({"message": "Success"}, status=rest_framework_status.HTTP_200_OK)
        except serializers.ValidationError as exc:
            exception = exc
            return Response({"message": str(exc)}, status=exc.status_code)
        except Exception as exc:
            exception = exc
            return Response(
                {"message": "Failed to send feedback"},
                status=rest_framework_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            self.write_to_segment(user_id, inline_suggestion_data, ansible_content_data, exception)

    def write_to_segment(
        self,
        user_id: str,
        inline_suggestion_data: InlineSuggestionFeedback,
        ansible_content_data: AnsibleContentFeedback,
        exception: Exception = None,
    ) -> None:
        if inline_suggestion_data:
            event = {
                "latency": inline_suggestion_data.get('latency'),
                "userActionTime": inline_suggestion_data.get('userActionTime'),
                "action": inline_suggestion_data.get('action'),
                "suggestionId": str(inline_suggestion_data.get('suggestionId', '')),
                "activityId": str(inline_suggestion_data.get('activityId', '')),
                "exception": exception is not None,
            }
            send_segment_event(event, "wisdomServiceInlineSuggestionFeedbackEvent", user_id)
        if ansible_content_data:
            event = {
                "content": ansible_content_data.get('content'),
                "documentUri": ansible_content_data.get('documentUri'),
                "trigger": ansible_content_data.get('trigger'),
                "activityId": str(ansible_content_data.get('activityId', '')),
                "exception": exception is not None,
            }
            send_segment_event(event, "wisdomServiceAnsibleContentFedbackEvent", user_id)


def truncate_recommendation_yaml(recommendation_yaml: str) -> tuple[bool, str]:
    lines = recommendation_yaml.splitlines()
    lines = [line for line in lines if line.strip() != ""]

    # process the input only when it has multiple lines
    if len(lines) < 2:
        return False, recommendation_yaml

    # if the last line can be parsed as YAML successfully,
    # we do not need to try truncating.
    last_line = lines[-1]
    is_last_line_valid = False
    try:
        _ = yaml.safe_load(last_line)
        is_last_line_valid = True
    except Exception:
        pass
    if is_last_line_valid:
        return False, recommendation_yaml

    truncated_yaml = "\n".join(lines[:-1])
    return True, truncated_yaml


class Attributions(GenericAPIView):
    """
    Returns attributions that were the highest likelihood sources for a given code suggestion.
    """

    serializer_class = AttributionRequestSerializer

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']

    throttle_classes = [CompletionsUserRateThrottle]

    @extend_schema(
        request=AttributionRequestSerializer,
        responses={
            200: AttributionResponseSerializer,
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Code suggestion attributions",
    )
    def post(self, request) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = str(request.user.uuid)
        suggestion_id = str(serializer.validated_data.get('suggestionId', ''))
        start_time = time.time()
        try:
            resp_serializer = self.perform_search(serializer)
        except Exception as exc:
            logger.error(f"Failed to search for attributions\nException:\n{exc}")
            return Response({'message': "Unable to complete the request"}, status=503)
        duration = round((time.time() - start_time) * 1000, 2)

        self.write_to_segment(user_id, suggestion_id, duration, resp_serializer.validated_data)

        return Response(resp_serializer.data, status=rest_framework_status.HTTP_200_OK)

    def perform_search(self, serializer):
        data = ai_search.search(serializer.validated_data['suggestion'])
        resp_serializer = AttributionResponseSerializer(data=data)
        if not resp_serializer.is_valid():
            logging.error(resp_serializer.errors)
        return resp_serializer

    def write_to_segment(self, user_id, suggestion_id, duration, attribution_data):
        for attribution in attribution_data.get('attributions', []):
            event = {'suggestionId': suggestion_id, 'duration': duration, **attribution}
            send_segment_event(event, "wisdomServiceAttributionEvent", user_id)
