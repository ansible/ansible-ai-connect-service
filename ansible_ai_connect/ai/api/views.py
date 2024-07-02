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
import time
from string import Template

from ansible_anonymizer import anonymizer
from django.apps import apps
from django.conf import settings
from django_prometheus.conf import NAMESPACE
from drf_spectacular.utils import OpenApiResponse, extend_schema
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from prometheus_client import Histogram
from rest_framework import permissions
from rest_framework import status as rest_framework_status
from rest_framework.response import Response
from rest_framework.views import APIView

import ansible_ai_connect.ai.api.telemetry.schema1 as schema1
from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.exceptions import (
    FeedbackInternalServerException,
    InternalServerError,
    ModelTimeoutException,
    WcaBadRequestException,
    WcaCloudflareRejectionException,
    WcaEmptyResponseException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    WcaNoDefaultModelIdException,
    WcaSuggestionIdCorrelationFailureException,
    WcaUserTrialExpiredException,
    process_error_count,
)
from ansible_ai_connect.ai.api.model_client.exceptions import (
    WcaBadRequest,
    WcaCloudflareRejection,
    WcaEmptyResponse,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaSuggestionIdCorrelationFailure,
    WcaUserTrialExpired,
)
from ansible_ai_connect.ai.api.pipelines.completions import CompletionsPipeline
from ansible_ai_connect.users.models import User

from ..feature_flags import FeatureFlags
from .data.data_model import ContentMatchPayloadData, ContentMatchResponseDto
from .model_client.exceptions import ModelTimeoutError
from .permissions import (
    AcceptedTermsPermission,
    BlockUserWithoutSeat,
    BlockUserWithoutSeatAndWCAReadyOrg,
    BlockUserWithSeatButWCANotReady,
    IsAAPLicensed,
)
from .serializers import (
    CompletionRequestSerializer,
    CompletionResponseSerializer,
    ContentMatchRequestSerializer,
    ContentMatchResponseSerializer,
    ExplanationRequestSerializer,
    ExplanationResponseSerializer,
    FeedbackRequestSerializer,
    GenerationRequestSerializer,
    GenerationResponseSerializer,
    InlineSuggestionFeedback,
    PlaybookGenerationAction,
    SentimentFeedback,
)
from .utils.analytics_telemetry_model import (
    AnalyticsPlaybookGenerationWizard,
    AnalyticsProductFeedback,
    AnalyticsRecommendationAction,
    AnalyticsTelemetryEvents,
)
from .utils.segment_analytics_telemetry import send_segment_analytics_event

logger = logging.getLogger(__name__)

feature_flags = FeatureFlags()

contentmatch_encoding_hist = Histogram(
    "model_contentmatch_encoding_latency_seconds",
    "Histogram of model contentmatch encoding processing time",
    namespace=NAMESPACE,
)
contentmatch_search_hist = Histogram(
    "model_contentmatch_search_latency_seconds",
    "Histogram of model contentmatch search processing time",
    namespace=NAMESPACE,
)

PERMISSIONS_MAP = {
    "onprem": [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsAAPLicensed,
    ],
    "upstream": [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
    ],
    "saas": [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
        BlockUserWithoutSeat,
        BlockUserWithoutSeatAndWCAReadyOrg,
        BlockUserWithSeatButWCANotReady,
    ],
}


class OurAPIView(APIView):
    exception = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.request = request
        request_serializer = self.serializer_class(data=request.data, context={"request": request})
        request_serializer.is_valid(raise_exception=True)
        self.validated_data = request_serializer.validated_data
        if self.schema1_event_class:
            self.schema1_event = self.schema1_event_class.init(request.user, self.validated_data)

    def _get_model_name(self, org_id: str) -> str:
        try:
            model_mesh_client = apps.get_app_config("ai").model_mesh_client
            model_name = model_mesh_client.get_model_id(
                org_id, self.validated_data.get("model", "")
            )
            return model_name
        except (WcaNoDefaultModelId, WcaModelIdNotFound, WcaSecretManagerError):
            return ""

    def handle_exception(self, exc):
        self.exception = exc

        # Mapping between the internal exceptions and the API exceptions (with a message and a code)
        mapping = [
            (WcaInvalidModelId, WcaInvalidModelIdException),
            (WcaBadRequest, WcaBadRequestException),
            (WcaKeyNotFound, WcaKeyNotFoundException),
            (WcaModelIdNotFound, WcaModelIdNotFoundException),
            (WcaNoDefaultModelId, WcaNoDefaultModelIdException),
            (WcaEmptyResponse, WcaEmptyResponseException),
            (WcaCloudflareRejection, WcaCloudflareRejectionException),
            (WcaUserTrialExpired, WcaUserTrialExpiredException),
        ]

        for original_class, new_class in mapping:
            if isinstance(exc, original_class):
                exc = new_class(cause=exc)
                break
        response = super().handle_exception(exc)
        return response

    def get_ids(self):
        allowed = ["explanationId", "generationId", "suggestionId"]
        # Return the ids we want to include in the exception messages
        ret = {}
        for k, v in self.validated_data.items():
            if k in allowed and v:
                ret[k] = v
            elif isinstance(v, dict):
                for subk, subv in v.items():
                    if subk in allowed and subv:
                        ret[subk] = subv
        return ret

    def dispatch(self, request, *args, **kwargs):
        start_time = time.time()
        self.exception = False
        self.schema1_event = None
        response = super().dispatch(request, *args, **kwargs)

        if self.schema1_event:
            if hasattr(self.schema1_event, "duration"):
                duration = round((time.time() - start_time) * 1000, 2)
                self.schema1_event.duration = duration
            self.schema1_event.modelName = self._get_model_name(request.user.org_id)
            self.schema1_event.set_exception(self.exception)
            # NOTE: We need to wait to store the request because keys like
            # request._request._prompt_type are stored in the request object
            # during the processing of the request.
            self.schema1_event.set_request(request)  # Read the note above
            # before moving the line ^

            # NOTE: We also want to include the final response in the event, we do that
            # we need to jump back and do it from within a final middleware that wrap
            # everything.
            import ansible_ai_connect.main.middleware

            ansible_ai_connect.main.middleware.global_schema1_event = self.schema1_event

        return response


class Completions(OurAPIView):
    """
    Returns inline code suggestions based on a given Ansible editor context.
    """

    serializer_class = CompletionRequestSerializer
    schema1_event_class = schema1.CompletionEvent

    permission_classes = PERMISSIONS_MAP.get(settings.DEPLOYMENT_MODE)

    required_scopes = ["read", "write"]

    throttle_cache_key_suffix = "_completions"

    @extend_schema(
        request=CompletionRequestSerializer,
        responses={
            200: CompletionResponseSerializer,
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            429: OpenApiResponse(description="Request was throttled"),
            503: OpenApiResponse(description="Service Unavailable"),
        },
        summary="Inline code suggestions",
    )
    def post(self, request) -> Response:
        pipeline = CompletionsPipeline(request)
        return pipeline.execute()


class Feedback(OurAPIView):
    """
    Feedback API for the AI service
    """

    serializer_class = FeedbackRequestSerializer
    schema1_event_class = schema1.BaseFeedbackEvent

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
    ]
    required_scopes = ["read", "write"]

    throttle_cache_key_suffix = "_feedback"
    throttle_cache_multiplier = 6.0

    @extend_schema(
        request=FeedbackRequestSerializer,
        responses={
            200: OpenApiResponse(description="Success"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
        },
        summary="Feedback API for the AI service",
    )
    def post(self, request) -> Response:
        validated_data = {}
        try:
            logger.info(f"feedback request payload from client: {self.validated_data}")
            return Response({"message": "Success"}, status=rest_framework_status.HTTP_200_OK)
        except Exception as exc:
            self.exception = exc
            logger.exception(f"An exception {exc.__class__} occurred in sending a feedback")
            raise FeedbackInternalServerException()
        finally:
            self.send_schema2(request.user, validated_data, request.data)

    def send_schema2(
        self,
        user: User,
        validated_data: dict,
        request_data=None,
    ) -> None:
        inline_suggestion_data: InlineSuggestionFeedback = validated_data.get("inlineSuggestion")
        sentiment_feedback_data: SentimentFeedback = validated_data.get("sentimentFeedback")
        playbook_generation_action_data: PlaybookGenerationAction = validated_data.get(
            "playbookGenerationAction"
        )

        ansible_extension_version = validated_data.get("metadata", {}).get(
            "ansibleExtensionVersion", None
        )
        model_name = ""
        try:
            org_id = getattr(user, "org_id", None)
            model_mesh_client = apps.get_app_config("ai").model_mesh_client
            model_name = model_mesh_client.get_model_id(
                org_id, str(validated_data.get("model", ""))
            )
        except (WcaNoDefaultModelId, WcaModelIdNotFound, WcaSecretManagerError):
            logger.debug(
                f"Failed to retrieve Model Name for Feedback.\n "
                f"Org ID: {user.org_id}, "
                f"User has seat: {user.rh_user_has_seat}, "
                f"has subscription: {user.rh_org_has_subscription}.\n"
            )

        if inline_suggestion_data:
            send_segment_analytics_event(
                AnalyticsTelemetryEvents.RECOMMENDATION_ACTION,
                lambda: AnalyticsRecommendationAction(
                    action=inline_suggestion_data.get("action"),
                    suggestion_id=inline_suggestion_data.get("suggestionId", ""),
                    rh_user_org_id=org_id,
                ),
                user,
                ansible_extension_version,
            )
        if sentiment_feedback_data:
            send_segment_analytics_event(
                AnalyticsTelemetryEvents.PRODUCT_FEEDBACK,
                lambda: AnalyticsProductFeedback(
                    value=sentiment_feedback_data.get("value"),
                    rh_user_org_id=org_id,
                    model_name=model_name,
                ),
                user,
                ansible_extension_version,
            )
        if playbook_generation_action_data:
            if (
                False
                and playbook_generation_action_data["from_page"] > 1
                and playbook_generation_action_data["action"] in [1, 3]
            ):
                send_segment_analytics_event(
                    AnalyticsTelemetryEvents.PLAYBOOK_GENERATION_ACTION,
                    lambda: AnalyticsPlaybookGenerationWizard(
                        action=playbook_generation_action_data["action"],
                        model_name=model_name,
                        rh_user_org_id=org_id,
                        wizard_id=str(playbook_generation_action_data.get("wizardId", "")),
                    ),
                    user,
                    ansible_extension_version,
                )


class ContentMatches(OurAPIView):
    """
    Returns content matches that were the highest likelihood sources for a given code suggestion.
    """

    serializer_class = ContentMatchRequestSerializer
    schema1_event_class = schema1.ContentMatchEvent

    permission_classes = (
        [
            permissions.IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            IsAAPLicensed,
        ]
        if settings.DEPLOYMENT_MODE == "onprem"
        else [
            permissions.IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            AcceptedTermsPermission,
            BlockUserWithoutSeat,
        ]
    )

    required_scopes = ["read", "write"]

    throttle_cache_key_suffix = "_contentmatches"

    @extend_schema(
        request=ContentMatchRequestSerializer,
        responses={
            200: ContentMatchResponseSerializer,
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            429: OpenApiResponse(description="Request was throttled"),
            503: OpenApiResponse(description="Service Unavailable"),
        },
        summary="Code suggestion attributions",
    )
    def post(self, request) -> Response:
        suggestion_id = str(self.validated_data.get("suggestionId", ""))
        model_id = str(self.validated_data.get("model", ""))

        try:
            response_serializer = self.perform_content_matching(
                model_id, suggestion_id, request.user
            )
            return Response(response_serializer.data, status=rest_framework_status.HTTP_200_OK)
        except Exception:
            logger.exception("Error requesting content matches")
            raise

    def perform_content_matching(
        self,
        model_id: str,
        suggestion_id: str,
        user: User,
    ):
        model_mesh_client = apps.get_app_config("ai").model_mesh_client
        user_id = user.uuid
        content_match_data: ContentMatchPayloadData = {
            "suggestions": self.validated_data.get("suggestions", []),
            "user_id": str(user_id) if user_id else None,
            "rh_user_has_seat": user.rh_user_has_seat,
            "organization_id": user.org_id,
            "suggestionId": suggestion_id,
        }
        logger.debug(
            f"input to content matches for suggestion id {suggestion_id}:\n{content_match_data}"
        )

        response_serializer = None
        metadata = []

        try:
            model_id, client_response = model_mesh_client.codematch(content_match_data, model_id)

            response_data = {"contentmatches": []}

            for response_item in client_response:
                content_match_dto = ContentMatchResponseDto(**response_item)
                response_data["contentmatches"].append(content_match_dto.content_matches)
                metadata.append(content_match_dto.meta)

                contentmatch_encoding_hist.observe(content_match_dto.encode_duration / 1000)
                contentmatch_search_hist.observe(content_match_dto.search_duration / 1000)

            # TODO: See if we can isolate the lines
            self.schema1_event.request = self.validated_data
            # NOTE: in the original payload response was a copy of the answer
            # however, for the other events, it's a structure that hold things
            # like the status_code
            # self.schema1_event.response = response_data
            self.schema1_event.metadata = metadata

            try:
                response_serializer = ContentMatchResponseSerializer(data=response_data)
                response_serializer.is_valid(raise_exception=True)
            except Exception:
                process_error_count.labels(
                    stage="contentmatch-response_serialization_validation"
                ).inc()
                logger.exception(f"error serializing final response for suggestion {suggestion_id}")
                raise InternalServerError

        except ModelTimeoutError as exc:
            self.exception = exc
            logger.warn(
                f"model timed out after {settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT} seconds"
                f" for suggestion {suggestion_id}"
            )
            raise ModelTimeoutException(cause=exc)

        except WcaBadRequest as exc:
            self.exception = exc
            logger.exception(f"bad request for content matching suggestion {suggestion_id}")
            raise WcaBadRequestException(cause=exc)

        except WcaInvalidModelId as exc:
            self.exception = exc
            logger.exception(
                f"WCA Model ID is invalid for content matching suggestion {suggestion_id}"
            )
            raise WcaInvalidModelIdException(cause=exc)

        except WcaKeyNotFound as exc:
            self.exception = exc
            logger.exception(
                f"A WCA Api Key was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaKeyNotFoundException(cause=exc)

        except WcaModelIdNotFound as exc:
            self.exception = exc
            logger.exception(
                f"A WCA Model ID was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaModelIdNotFoundException(cause=exc)

        except WcaNoDefaultModelId as exc:
            self.exception = exc
            logger.exception(
                "A default WCA Model ID was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaNoDefaultModelIdException(cause=exc)

        except WcaSuggestionIdCorrelationFailure as exc:
            self.exception = exc
            logger.exception(
                f"WCA Request/Response SuggestionId correlation failed "
                f"for suggestion {suggestion_id}"
            )
            raise WcaSuggestionIdCorrelationFailureException(cause=exc)

        except WcaEmptyResponse as exc:
            self.exception = exc
            logger.exception(
                f"WCA returned an empty response for content matching suggestion {suggestion_id}"
            )
            raise WcaEmptyResponseException(cause=exc)

        except WcaCloudflareRejection as exc:
            self.exception = exc
            logger.exception(f"Cloudflare rejected the request for {suggestion_id}")
            raise WcaCloudflareRejectionException(cause=exc)

        except WcaUserTrialExpired as exc:
            # NOTE: exception should be removed
            self.exception = exc
            logger.exception(f"User trial expired, when requesting suggestion {suggestion_id}")
            raise WcaUserTrialExpiredException(cause=exc)

        except Exception as exc:
            self.exception = exc
            logger.exception(f"Error requesting content matches for suggestion {suggestion_id}")
            raise

        return response_serializer


class Explanation(OurAPIView):
    """
    Returns a text that explains a playbook.
    """

    serializer_class = ExplanationRequestSerializer
    schema1_event_class = schema1.ExplainPlaybookEvent
    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
        BlockUserWithoutSeat,
        BlockUserWithoutSeatAndWCAReadyOrg,
        BlockUserWithSeatButWCANotReady,
    ]
    required_scopes = ["read", "write"]

    throttle_cache_key_suffix = "_explanation"

    @extend_schema(
        request=ExplanationRequestSerializer,
        responses={
            200: ExplanationResponseSerializer,
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            429: OpenApiResponse(description="Request was throttled"),
            503: OpenApiResponse(description="Service Unavailable"),
        },
        summary="Inline code suggestions",
    )
    def post(self, request) -> Response:
        explanation_id = str(self.validated_data.get("explanationId", ""))
        playbook = self.validated_data.get("content")

        llm = apps.get_app_config("ai").model_mesh_client
        explanation = llm.explain_playbook(request, playbook)

        # Anonymize response
        # Anonymized in the View to be consistent with where Completions are anonymized
        anonymized_explanation = anonymizer.anonymize_struct(
            explanation, value_template=Template("{{ _${variable_name}_ }}")
        )

        answer = {
            "content": anonymized_explanation,
            "format": "markdown",
            "explanationId": explanation_id,
        }

        return Response(
            answer,
            status=rest_framework_status.HTTP_200_OK,
        )


class Generation(OurAPIView):
    """
    Returns a playbook based on a text input.
    """

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    serializer_class = GenerationRequestSerializer
    schema1_event_class = schema1.CodegenPlaybookEvent
    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        AcceptedTermsPermission,
        BlockUserWithoutSeat,
        BlockUserWithoutSeatAndWCAReadyOrg,
        BlockUserWithSeatButWCANotReady,
    ]
    required_scopes = ["read", "write"]

    throttle_cache_key_suffix = "_generation"

    @extend_schema(
        request=GenerationRequestSerializer,
        responses={
            200: GenerationResponseSerializer,
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            429: OpenApiResponse(description="Request was throttled"),
            503: OpenApiResponse(description="Service Unavailable"),
        },
        summary="Inline code suggestions",
    )
    def post(self, request) -> Response:
        generation_id = str(self.validated_data.get("generationId", ""))
        create_outline = self.validated_data["createOutline"]
        outline = str(self.validated_data.get("outline", ""))
        text = self.validated_data["text"]

        llm = apps.get_app_config("ai").model_mesh_client
        playbook, outline = llm.generate_playbook(request, text, create_outline, outline)

        # Anonymize responses
        # Anonymized in the View to be consistent with where Completions are anonymized
        anonymized_playbook = anonymizer.anonymize_struct(
            playbook, value_template=Template("{{ _${variable_name}_ }}")
        )
        anonymized_outline = anonymizer.anonymize_struct(
            outline, value_template=Template("{{ _${variable_name}_ }}")
        )

        answer = {
            "playbook": anonymized_playbook,
            "outline": anonymized_outline,
            "format": "plaintext",
            "generationId": generation_id,
        }

        return Response(
            answer,
            status=rest_framework_status.HTTP_200_OK,
        )
