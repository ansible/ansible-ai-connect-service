import logging
import time

from ai.api.model_client.exceptions import (
    WcaBadRequest,
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
)
from ai.api.pipelines.common import (
    InternalServerError,
    ModelTimeoutException,
    ServiceUnavailable,
    WcaBadRequestException,
    WcaEmptyResponseException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    process_error_count,
)
from ai.api.pipelines.completions import CompletionsPipeline
from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from drf_spectacular.utils import OpenApiResponse, extend_schema
from prometheus_client import Histogram
from rest_framework import serializers
from rest_framework import status as rest_framework_status
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import User

from .. import search as ai_search
from ..feature_flags import FeatureFlags, WisdomFlags
from .data.data_model import ContentMatchPayloadData, ContentMatchResponseDto
from .model_client.exceptions import ModelTimeoutError
from .permissions import AcceptedTermsPermission
from .serializers import (
    AnsibleContentFeedback,
    AttributionRequestSerializer,
    AttributionResponseSerializer,
    CompletionRequestSerializer,
    CompletionResponseSerializer,
    ContentMatchRequestSerializer,
    ContentMatchResponseSerializer,
    FeedbackRequestSerializer,
    InlineSuggestionFeedback,
    IssueFeedback,
    SentimentFeedback,
    SuggestionQualityFeedback,
)
from .utils.segment import send_segment_event

logger = logging.getLogger(__name__)

feature_flags = FeatureFlags()

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
    def post(self, request) -> Response:
        pipeline = CompletionsPipeline(request)
        return pipeline.execute()


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
    throttle_cache_multiplier = 6.0

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
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        request_data = request_serializer.validated_data
        suggestion_id = str(request_data.get('suggestionId', ''))

        start_time = time.time()
        try:
            encode_duration, search_duration, response_serializer = self.perform_search(
                request_serializer, request.user
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
            response_serializer.validated_data,
        )

        return Response(response_serializer.data, status=rest_framework_status.HTTP_200_OK)

    def perform_search(self, serializer, user: User):
        index = None
        if settings.LAUNCHDARKLY_SDK_KEY:
            model_tuple = feature_flags.get(WisdomFlags.MODEL_NAME, user, "")
            logger.debug(f"flag model_name has value {model_tuple}")
            model_parts = model_tuple.split(':')
            if len(model_parts) == 4:
                *_, index = model_parts
                logger.info(f"using index '{index}' for content matching")

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


class ContentMatches(GenericAPIView):
    """
    Returns content matches that were the highest likelihood sources for a given code suggestion.
    """

    serializer_class = ContentMatchRequestSerializer

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']

    throttle_cache_key_suffix = '_contentmatches'

    @extend_schema(
        request=ContentMatchRequestSerializer,
        responses={
            200: ContentMatchResponseSerializer,
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Code suggestion attributions",
    )
    def post(self, request) -> Response:
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        request_data = request_serializer.validated_data
        suggestion_id = str(request_data.get('suggestionId', ''))
        model_id = str(request_data.get('model', ''))

        if request.user.rh_user_has_seat:
            try:
                response_serializer = self.perform_content_matching(
                    model_id, suggestion_id, request.user, request_data
                )
                return Response(response_serializer.data, status=rest_framework_status.HTTP_200_OK)
            except Exception:
                logger.exception(f"error requesting content matches for suggestion {suggestion_id}")
                raise ServiceUnavailable
        else:
            return Response(
                {"message": "Not implemented"},
                status=rest_framework_status.HTTP_501_NOT_IMPLEMENTED,
            )

    def perform_content_matching(
        self,
        model_id: str,
        suggestion_id: str,
        user: User,
        request_data,
    ):
        wca_client = apps.get_app_config("ai").wca_client
        user_id = user.uuid
        content_match_data: ContentMatchPayloadData = {
            "suggestions": request_data.get('suggestions', ''),
            "user_id": str(user_id) if user_id else None,
            "rh_user_has_seat": user.rh_user_has_seat,
            "organization_id": user.org_id,
            "suggestionId": suggestion_id,
        }
        logger.debug(f"input to inference for suggestion id {suggestion_id}:\n{content_match_data}")

        try:
            start_time = time.time()

            client_response = wca_client.codematch(content_match_data, model_id)

            duration = round((time.time() - start_time) * 1000, 2)

            response_data = {"contentmatches": []}

            for response_item in client_response:
                content_match_dto = ContentMatchResponseDto(**response_item)
                response_data["contentmatches"].append(content_match_dto.content_matches)

                attribution_encoding_hist.observe(content_match_dto.encode_duration / 1000)
                attribution_search_hist.observe(content_match_dto.search_duration / 1000)

                self._write_to_segment(
                    user,
                    suggestion_id,
                    duration,
                    content_match_dto.encode_duration,
                    content_match_dto.search_duration,
                    content_match_dto.content_matches,
                )

            try:
                response_serializer = ContentMatchResponseSerializer(data=response_data)
                response_serializer.is_valid(raise_exception=True)
            except Exception:
                process_error_count.labels(stage='response_serialization_validation').inc()
                logger.exception(f"error serializing final response for suggestion {suggestion_id}")
                raise InternalServerError
        except ModelTimeoutError:
            logger.warn(
                f"model timed out after {settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT} seconds"
                f" for suggestion {suggestion_id}"
            )
            raise ModelTimeoutException

        except WcaBadRequest as e:
            logger.error(e)
            logger.exception(f"bad request for content matching suggestion {suggestion_id}")
            raise WcaBadRequestException

        except WcaInvalidModelId as e:
            logger.error(e)
            logger.exception(
                f"WCA Model ID is invalid for content matching suggestion {suggestion_id}"
            )
            raise WcaInvalidModelIdException

        except WcaKeyNotFound as e:
            logger.error(e)
            logger.exception(
                f"A WCA Api Key was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaKeyNotFoundException

        except WcaModelIdNotFound as e:
            logger.error(e)
            logger.exception(
                f"A WCA Model ID was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaModelIdNotFoundException

        except WcaEmptyResponse as e:
            logger.error(e)
            logger.exception(
                f"WCA returned an empty response for content matching suggestion {suggestion_id}"
            )
            raise WcaEmptyResponseException
        return response_serializer

    def _write_to_segment(
        self, user, suggestion_id, duration, encode_duration, search_duration, data
    ):
        contentmatch = data.get('contentmatch', [])
        event = {
            'suggestionId': suggestion_id,
            'duration': duration,
            'encode_duration': encode_duration,
            'search_duration': search_duration,
            'contentmatch': contentmatch,
        }
        send_segment_event(event, "contentmatch", user)
