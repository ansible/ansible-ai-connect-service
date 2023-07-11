import json
import logging
import re
import time
from string import Template

import yaml
from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django.http import QueryDict
from django_prometheus.conf import NAMESPACE
from drf_spectacular.utils import OpenApiResponse, extend_schema
from prometheus_client import Counter, Histogram
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
from ..feature_flags import FeatureFlags
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
    IssueFeedback,
    SentimentFeedback,
    SuggestionQualityFeedback,
)
from .utils.jaeger import distributed_tracing_method, with_distributed_tracing
from .utils.segment import send_segment_event

logger = logging.getLogger(__name__)

feature_flags = FeatureFlags()


completions_hist = Histogram(
    'model_prediction_latency_seconds',
    "Histogram of model prediction processing time",
    namespace=NAMESPACE,
)
completions_return_code = Counter(
    'model_prediction_return_code', 'The return code of model prediction requests', ['code']
)
attribution_encoding_hist = Histogram(
    'model_attribution_encoding_latency_seconds',
    "Histogram of model attribution encoding processing time",
    namespace=NAMESPACE,
)
attribution_search_hist = Histogram(
    'model_attribution_search_latency_seconds',
    "Histogram of model attribution search processing time",
    namespace=NAMESPACE,
)
preprocess_hist = Histogram(
    'preprocessing_latency_seconds',
    "Histogram of pre-processing time",
    namespace=NAMESPACE,
)
postprocess_hist = Histogram(
    'postprocessing_latency_seconds',
    "Histogram of post-processing time",
    namespace=NAMESPACE,
)
process_error_count = Counter(
    'process_error', "Error counts at pre-process/prediction/post-process stages", ['stage']
)


class BaseWisdomAPIException(APIException):
    def __init__(self, *args, **kwargs):
        completions_return_code.labels(code=self.status_code).inc()
        super().__init__(*args, **kwargs)


class PostprocessException(BaseWisdomAPIException):
    status_code = 204
    error_type = 'postprocess_error'


class ModelTimeoutException(BaseWisdomAPIException):
    status_code = 204
    error_type = 'model_timeout'


class ServiceUnavailable(BaseWisdomAPIException):
    status_code = 503
    default_detail = {"message": "An error occurred attempting to complete the request"}


class InternalServerError(BaseWisdomAPIException):
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

    throttle_cache_key_suffix = '_completions'

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
    @with_distributed_tracing(
        name="Request recommendation",
        description="preprocessing, recommendation retreival, postprocessing",
        file=__file__,
        method="post",
    )
    def post(self, request, inner_span_ctx) -> Response:
        # Here `request` is a DRF wrapper around Django's original
        # WSGIRequest object.  It holds the original as
        # `self._request`, and that's the one we need to modify to
        # make this available to the middleware.
        request._request._suggestion_id = request.data.get('suggestionId')

        model_mesh_client = apps.get_app_config("ai").model_mesh_client
        request_serializer = CompletionRequestSerializer(data=request.data)
        try:
            request_serializer.is_valid(raise_exception=True)
            request._request._suggestion_id = str(request_serializer.validated_data['suggestionId'])
        except Exception as exc:
            process_error_count.labels(stage='request_serialization_validation').inc()
            logger.warn(f'failed to validate request:\nException:\n{exc}')
            raise exc
        payload = APIPayload(**request_serializer.validated_data)
        payload.userId = request.user.uuid
        model_name = payload.model_name
        if settings.LAUNCHDARKLY_SDK_KEY:
            model_tuple = feature_flags.get("model_name", request.user, "")
            logger.debug(f"flag model_name has value {model_tuple}")
            match = re.search(r"(.+):(.+):(.+):(.+)", model_tuple)
            if match:
                server, port, model_name, index = match.groups()
                logger.info(f"selecting model '{model_name}@{server}:{port}'")
                model_mesh_client.set_inference_url(f"{server}:{port}")
        original_indent = payload.prompt.find("name")

        try:
            start_time = time.time()
            payload.context, payload.prompt = self.preprocess(
                payload.context, payload.prompt, span_ctx=inner_span_ctx
            )
        except Exception as exc:
            process_error_count.labels(stage='pre-processing').inc()
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
        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            preprocess_hist.observe(duration / 1000)  # millisec to seconds

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
            predictions = model_mesh_client.infer(
                data, model_name=model_name, span_ctx=inner_span_ctx
            )
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
            process_error_count.labels(stage='prediction').inc()
            duration = round((time.time() - start_time) * 1000, 2)
            completions_hist.observe(duration / 1000)  # millisec back to seconds
            value_template = Template("{{ _${variable_name}_ }}")

            distributed_tracing_method(
                'PII removal (anonymizer)',
                'Responsible for removing Personally '
                'Identifiable Information (PII) from ansible task',
                __file__,
                'anonymize_struct',
                inner_span_ctx,
            )
            ano_predictions = anonymizer.anonymize_struct(
                predictions, value_template=value_template
            )
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
            f"response from inference for suggestion id {payload.suggestionId}:\n{predictions}"
        )
        postprocessed_predictions = None
        try:
            start_time = time.time()
            postprocessed_predictions = self.postprocess(
                ano_predictions,
                payload.prompt,
                payload.context,
                request.user,
                payload.suggestionId,
                indent=original_indent,
                span_ctx=inner_span_ctx,
            )
        except Exception:
            process_error_count.labels(stage='post-processing').inc()
            logger.exception(
                f"error postprocessing prediction for suggestion {payload.suggestionId}"
            )
            raise PostprocessException
        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            postprocess_hist.observe(duration / 1000)  # millisec to seconds

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
            process_error_count.labels(stage='response_serialization_validation').inc()
            logger.exception(
                f"error serializing final response for suggestion {payload.suggestionId}"
            )
            raise InternalServerError
        completions_return_code.labels(code=200).inc()

        distributed_tracing_method(
            'Returning Recommendation for VSCode Extension',
            'Creates and returns "Response" Object to be retrieved by VSCode Extension',
            __file__,
            '---',
            inner_span_ctx,
        )
        return Response(postprocessed_predictions, status=200)

    @with_distributed_tracing(
        name="Recommendation Pre-processing",
        description='Parent method responsible for processing context (play configs) '
        'and prompt (task name) to model expectations',
        file=__file__,
        method='preprocess',
    )
    def preprocess(self, context, prompt, span_ctx, inner_span_ctx):
        context, prompt = fmtr.preprocess(context, prompt, span_ctx=inner_span_ctx)

        return context, prompt

    @with_distributed_tracing(
        name="Recommendation Post-processing",
        description='Writes recommendation yaml to segment, formats recommendation',
        file=__file__,
        method='postprocess',
    )
    def postprocess(
        self, recommendation, prompt, context, user, suggestion_id, indent, span_ctx, inner_span_ctx
    ):
        ari_caller = apps.get_app_config("ai").get_ari_caller(span_ctx=inner_span_ctx)
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
                        span_ctx=inner_span_ctx,
                    )
                    if exception:
                        raise exception

            # adjust indentation as per default ansible-lint configuration
            indented_yaml = fmtr.adjust_indentation(recommendation["predictions"][i])

            # restore original indentation
            indented_yaml = fmtr.restore_indentation(indented_yaml, indent)
            recommendation["predictions"][i] = indented_yaml
            logger.debug(
                f"suggestion id: {suggestion_id}, indented recommendation: \n{indented_yaml}"
            )
            continue
        return recommendation

    @with_distributed_tracing(
        name="Write to Segment",
        description='Creates event to be sent to Amplitude/S3 through Segment',
        file=__file__,
        method='write_to_segment',
    )
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
        span_ctx,
        inner_span_ctx,
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

    throttle_cache_key_suffix = '_feedback'

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
        validated_data = {}
        try:
            request_serializer = FeedbackRequestSerializer(data=request.data)
            request_serializer.is_valid(raise_exception=True)
            validated_data = request_serializer.validated_data
            logger.info(f"feedback request payload from client: {validated_data}")
            return Response({"message": "Success"}, status=rest_framework_status.HTTP_200_OK)
        except serializers.ValidationError as exc:
            exception = exc
            return Response({"message": str(exc)}, status=exc.status_code)
        except Exception as exc:
            exception = exc
            logger.exception(f"An exception {exc.__class__} occurred in sending a feedback")
            return Response(
                {"message": "Failed to send feedback"},
                status=rest_framework_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            self.write_to_segment(request.user, validated_data, exception, request.data)

    def write_to_segment(
        self,
        user: User,
        validated_data: dict,
        exception: Exception = None,
        request_data=None,
    ) -> None:
        inline_suggestion_data: InlineSuggestionFeedback = validated_data.get("inlineSuggestion")
        ansible_content_data: AnsibleContentFeedback = validated_data.get("ansibleContent")
        suggestion_quality_data: SuggestionQualityFeedback = validated_data.get(
            "suggestionQualityFeedback"
        )
        sentiment_feedback_data: SentimentFeedback = validated_data.get("sentimentFeedback")
        issue_feedback_data: IssueFeedback = validated_data.get("issueFeedback")
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
        if suggestion_quality_data:
            event = {
                "prompt": suggestion_quality_data.get('prompt'),
                "providedSuggestion": suggestion_quality_data.get('providedSuggestion'),
                "expectedSuggestion": suggestion_quality_data.get('expectedSuggestion'),
                "additionalComment": suggestion_quality_data.get('additionalComment'),
                "exception": exception is not None,
            }
            send_segment_event(event, "suggestionQualityFeedback", user)
        if sentiment_feedback_data:
            event = {
                "value": sentiment_feedback_data.get('value'),
                "feedback": sentiment_feedback_data.get('feedback'),
                "exception": exception is not None,
            }
            send_segment_event(event, "sentimentFeedback", user)
        if issue_feedback_data:
            event = {
                "type": issue_feedback_data.get('type'),
                "title": issue_feedback_data.get('title'),
                "description": issue_feedback_data.get('description'),
                "exception": exception is not None,
            }
            send_segment_event(event, "issueFeedback", user)

        feedback_events = [
            inline_suggestion_data,
            ansible_content_data,
            suggestion_quality_data,
            sentiment_feedback_data,
            issue_feedback_data,
        ]
        if exception and all(not data for data in feedback_events):
            # When an exception is thrown before inline_suggestion_data or ansible_content_data
            # is set, we send request_data to Segment after having anonymized it.
            ano_request_data = anonymizer.anonymize_struct(request_data)
            if "inlineSuggestion" in request_data:
                event_type = "inlineSuggestionFeedback"
            elif "suggestionQualityFeedback" in request_data:
                event_type = "suggestionQualityFeedback"
            elif "sentimentFeedback" in request_data:
                event_type = "sentimentFeedback"
            elif "issueFeedback" in request_data:
                event_type = "issueFeedback"
            else:
                event_type = "ansibleContentFeedback"

            event = {
                "data": ano_request_data,
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

    throttle_cache_key_suffix = '_attributions'

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
            encode_duration, search_duration, resp_serializer = self.perform_search(
                serializer, request.user
            )
        except Exception as exc:
            logger.error(f"Failed to search for attributions\nException:\n{exc}")
            return Response({'message': "Unable to complete the request"}, status=503)
        duration = round((time.time() - start_time) * 1000, 2)
        attribution_encoding_hist.observe(encode_duration / 1000)
        attribution_search_hist.observe(search_duration / 1000)
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

    def perform_search(self, serializer, user: User):
        index = None
        if settings.LAUNCHDARKLY_SDK_KEY:
            model_tuple = feature_flags.get("model_name", user, "")
            logger.debug(f"flag model_name has value {model_tuple}")
            match = re.search(r"(.+):(.+):(.+):(.+)", model_tuple)
            if match:
                *_, index = match.groups()
                logger.info(f"using index '{index}' for content matchin")
        data = ai_search.search(serializer.validated_data['suggestion'], index)
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
