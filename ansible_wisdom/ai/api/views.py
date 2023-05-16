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
from users.models import User
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
        request_serializer = CompletionRequestSerializer(data=request.data)
        try:
            request_serializer.is_valid(raise_exception=True)
        except Exception as exc:
            logger.warn(f'failed to validate request:\nException:\n{exc}')
            raise exc
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
            message = (
                'Request contains invalid prompt'
                if isinstance(exc, fmtr.InvalidPromptException)
                else 'Request contains invalid yaml'
            )
            return Response({'message': message}, status=400)
        model_mesh_payload = ModelMeshPayload(
            instances=[
                {
                    "prompt": payload.prompt,
                    "context": payload.context,
                    "userId": str(payload.userId) if payload.userId else None,
                    "suggestionId": str(payload.suggestionId),
                }
            ]
        )
        data = model_mesh_payload.dict()
        logger.debug(f"input to inference for suggestion id {payload.suggestionId}:\n{data}")

        predictions = None
        exception = None
        start_time = time.time()
        try:
            predictions = model_mesh_client.infer(data, model_name=model_name)
        except ModelTimeoutError as exc:
            exception = exc
            logger.warn(
                f"model timed out after {settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT} seconds"
                f" for suggestion {payload.suggestionId}"
            )
            raise ModelTimeoutException
        except Exception as exc:
            exception = exc
            logger.exception(f"error requesting completion for suggestion {payload.suggestionId}")
            raise ServiceUnavailable
        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            ano_predictions = anonymizer.anonymize_struct(predictions)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
                "request": data,
                "response": ano_predictions,
                "suggestionId": str(payload.suggestionId),
            }
            send_segment_event(event, "prediction", request.user)

        logger.debug(
            f"response from inference for " f"suggestion id {payload.suggestionId}:\n{predictions}"
        )
        postprocessed_predictions = None
        try:
            postprocessed_predictions = self.postprocess(
                ano_predictions,
                payload.prompt,
                payload.context,
                request.user,
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
            postprocessed_predictions.update(
                {
                    "modelName": model_name,
                    "suggestionId": payload.suggestionId,
                }
            )
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

    def postprocess(self, recommendation, prompt, context, user, suggestion_id, indent):
        ari_caller = apps.get_app_config("ai").get_ari_caller()
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
                        user,
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

            # adjust indentation as per default ansible-lint configuration
            indented_yaml = fmtr.adjust_indentation(recommendation["predictions"][i])

            # restore original indentation
            indented_yaml = fmtr.restore_indentation(indented_yaml, indent)
            recommendation["predictions"][i] = indented_yaml
            logger.debug(
                f"suggestion id: {suggestion_id}, " f"indented recommendation: \n{indented_yaml}"
            )
            continue
        return recommendation

    def write_to_segment(
        self,
        user,
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
        send_segment_event(event, "postprocess", user)


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
        inline_suggestion_data = {}
        ansible_content_data = {}
        try:
            request_serializer = FeedbackRequestSerializer(data=request.data)
            request_serializer.is_valid(raise_exception=True)
            validated_data = request_serializer.validated_data
            logger.info(f"feedback request payload from client: {validated_data}")
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
            self.write_to_segment(
                request.user, inline_suggestion_data, ansible_content_data, exception, request.data
            )

    def write_to_segment(
        self,
        user: User,
        inline_suggestion_data: InlineSuggestionFeedback,
        ansible_content_data: AnsibleContentFeedback,
        exception: Exception = None,
        request_data=None,
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
            send_segment_event(event, "inlineSuggestionFeedback", user)
        if ansible_content_data:
            event = {
                "content": ansible_content_data.get('content'),
                "documentUri": ansible_content_data.get('documentUri'),
                "trigger": ansible_content_data.get('trigger'),
                "activityId": str(ansible_content_data.get('activityId', '')),
                "exception": exception is not None,
            }
            send_segment_event(event, "ansibleContentFeedback", user)
        if exception and not inline_suggestion_data and not ansible_content_data:
            event_type = (
                "inlineSuggestionFeedback"
                if ("inlineSuggestion" in request_data)
                else "inlineSuggestionFeedback"
            )
            event = {
                "data": request_data,
                "exception": str(exception),
            }
            send_segment_event(event, event_type, user)


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

        suggestion_id = str(serializer.validated_data.get('suggestionId', ''))
        start_time = time.time()
        try:
            encode_duration, search_duration, resp_serializer = self.perform_search(serializer)
        except Exception as exc:
            logger.error(f"Failed to search for attributions\nException:\n{exc}")
            return Response({'message': "Unable to complete the request"}, status=503)
        duration = round((time.time() - start_time) * 1000, 2)

        # Currently the only thing from Attributions that is going to Segment is the
        # inferred sources, which do not seem to need anonymizing.
        self.write_to_segment(
            request.user,
            suggestion_id,
            duration,
            encode_duration,
            search_duration,
            resp_serializer.validated_data,
        )

        return Response(resp_serializer.data, status=rest_framework_status.HTTP_200_OK)

    def perform_search(self, serializer):
        data = ai_search.search(serializer.validated_data['suggestion'])
        resp_serializer = AttributionResponseSerializer(data={'attributions': data['attributions']})
        if not resp_serializer.is_valid():
            logging.error(resp_serializer.errors)
        return data['meta']['encode_duration'], data['meta']['search_duration'], resp_serializer

    def write_to_segment(
        self, user, suggestion_id, duration, encode_duration, search_duration, attribution_data
    ):
        attributions = attribution_data.get('attributions', [])
        event = {
            'suggestionId': suggestion_id,
            'duration': duration,
            'encode_duration': encode_duration,
            'search_duration': search_duration,
            'attributions': attributions,
        }
        send_segment_event(event, "attribution", user)
