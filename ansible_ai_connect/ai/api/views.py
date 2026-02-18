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

import copy
import logging
import time
import traceback
from string import Template

from ansible_anonymizer import anonymizer
from ansible_base.lib.utils.schema import extend_schema_if_available
from django.apps import apps
from django.conf import settings
from django.http import StreamingHttpResponse
from django_prometheus.conf import NAMESPACE
from drf_spectacular.utils import OpenApiResponse, extend_schema
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from prometheus_client import Histogram
from rest_framework import permissions, serializers
from rest_framework import status as rest_framework_status
from rest_framework.generics import GenericAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.exceptions import (
    BaseWisdomAPIException,
    ChatbotInvalidResponseException,
    ChatbotNotEnabledException,
    FeedbackInternalServerException,
    FeedbackValidationException,
    InternalServerError,
    ModelTimeoutException,
    ServiceUnavailable,
    WcaBadRequestException,
    WcaCloudflareRejectionException,
    WcaEmptyResponseException,
    WcaHAPFilterRejectionException,
    WcaInstanceDeletedException,
    WcaInvalidModelIdException,
    WcaKeyNotFoundException,
    WcaModelIdNotFoundException,
    WcaNoDefaultModelIdException,
    WcaRequestIdCorrelationFailureException,
    WcaUserTrialExpiredException,
    process_error_count,
)
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaBadRequest,
    WcaCloudflareRejection,
    WcaEmptyResponse,
    WcaHAPFilterRejection,
    WcaInstanceDeleted,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
    WcaRequestIdCorrelationFailure,
    WcaUserTrialExpired,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    ChatBotParameters,
    ContentMatchParameters,
    MetaData,
    ModelPipelineChatBot,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
    ModelPipelineRoleGeneration,
    ModelPipelineStreamingChatBot,
    PlaybookExplanationParameters,
    PlaybookGenerationParameters,
    RoleExplanationParameters,
    RoleGenerationParameters,
    StreamingChatBotParameters,
)
from ansible_ai_connect.ai.api.pipelines.completions import CompletionsPipeline
from ansible_ai_connect.ai.api.telemetry import schema1
from ansible_ai_connect.ai.api.telemetry.schema2 import (
    AnalyticsPlaybookGenerationWizard,
    AnalyticsProductFeedback,
    AnalyticsRecommendationAction,
    AnalyticsRoleGenerationWizard,
    AnalyticsTelemetryEvents,
)
from ansible_ai_connect.ai.api.utils.segment import send_schema1_event
from ansible_ai_connect.ai.api.utils.segment_analytics_telemetry import (
    send_segment_analytics_event,
)
from ansible_ai_connect.users.models import User

from ...main.permissions import IsAAPUser, IsRHInternalUser, IsTestUser
from ...users.throttling import EndpointRateThrottle
from ..feature_flags import FeatureFlags
from .data.data_model import ContentMatchPayloadData, ContentMatchResponseDto
from .model_pipelines.exceptions import ModelTimeoutError
from .model_pipelines.http.configuration import HttpConfiguration
from .permissions import (
    BlockUserWithoutSeat,
    BlockUserWithoutSeatAndWCAReadyOrg,
    BlockUserWithSeatButWCANotReady,
    BlockWCANotReadyButTrialAvailable,
    IsOrganisationLightspeedSubscriber,
)
from .serializers import (
    ChatFeedback,
    ChatRequestSerializer,
    ChatResponseSerializer,
    CompletionRequestSerializer,
    CompletionResponseSerializer,
    ContentMatchRequestSerializer,
    ContentMatchResponseSerializer,
    ExplanationRequestSerializer,
    ExplanationResponseSerializer,
    ExplanationRoleRequestSerializer,
    FeedbackRequestSerializer,
    GenerationPlaybookRequestSerializer,
    GenerationPlaybookResponseSerializer,
    GenerationRoleRequestSerializer,
    GenerationRoleResponseSerializer,
    InlineSuggestionFeedback,
    IssueFeedback,
    PlaybookExplanationFeedback,
    PlaybookGenerationAction,
    RoleGenerationAction,
    SentimentFeedback,
    StreamingChatRequestSerializer,
    SuggestionQualityFeedback,
)
from .telemetry.schema1 import ChatBotFeedbackEvent, ChatBotResponseDocsReferences
from .utils.segment import send_segment_event

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
    ],
    "upstream": [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
    ],
    "saas": [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        BlockUserWithoutSeat,
        BlockWCANotReadyButTrialAvailable,
        BlockUserWithoutSeatAndWCAReadyOrg,
        BlockUserWithSeatButWCANotReady,
    ],
}


class AACSAPIView(APIView):
    def __init__(self):
        super().__init__()
        self.event = None
        self.req_model_id = None
        self.exception = None
        self.validated_data = {}

    def initialize_request(self, request, *args, **kwargs):
        # Call super first to ensure request object is correctly
        # initialised before instantiating event
        initialised_request = super().initialize_request(request, *args, **kwargs)
        self.event: schema1.Schema1Event = self.schema1_event()
        self.event.set_request(initialised_request)

        return initialised_request

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if hasattr(request, "data"):
            self.load_parameters(request)

    def load_parameters(self, request) -> Response:
        if hasattr(self, "request_serializer_class"):
            request_serializer = self.request_serializer_class(data=request.data)
            request_serializer.is_valid(raise_exception=True)
            self.validated_data = request_serializer.validated_data
            if req_model_id := self.validated_data.get("model") or self.validated_data.get(
                "model_id"
            ):
                self.req_model_id = req_model_id

    def handle_exception(self, exc):
        self.exception = exc

        # Mapping between the internal exceptions and the API exceptions (with a message and a code)
        mapping = [
            (WcaBadRequest, WcaBadRequestException),
            (WcaCloudflareRejection, WcaCloudflareRejectionException),
            (WcaEmptyResponse, WcaEmptyResponseException),
            (WcaHAPFilterRejection, WcaHAPFilterRejectionException),
            (WcaInstanceDeleted, WcaInstanceDeletedException),
            (WcaInvalidModelId, WcaInvalidModelIdException),
            (WcaKeyNotFound, WcaKeyNotFoundException),
            (WcaModelIdNotFound, WcaModelIdNotFoundException),
            (WcaNoDefaultModelId, WcaNoDefaultModelIdException),
            (WcaRequestIdCorrelationFailure, WcaRequestIdCorrelationFailureException),
            (WcaUserTrialExpired, WcaUserTrialExpiredException),
        ]

        for original_class, new_class in mapping:
            if isinstance(exc, original_class):
                exc = new_class(cause=exc)
                break
        logger.error(f"{type(exc)}: {traceback.format_exception(exc)}")
        response = super().handle_exception(exc)
        self.event.set_exception(exc)
        return response

    @staticmethod
    def get_model_name(request, req_model_id):
        if not request.user.is_authenticated:
            return

        model_meta_data: MetaData = apps.get_app_config("ai").get_model_pipeline(MetaData)

        try:
            return model_meta_data.get_model_id(request.user, req_model_id)
        except (WcaNoDefaultModelId, WcaModelIdNotFound, WcaSecretManagerError):
            pass

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        self.event.modelName = self.event.modelName or self.get_model_name(
            request, self.req_model_id
        )
        self.event.set_response(response)
        send_schema1_event(self.event)
        return response

    @staticmethod
    def get_auth_header() -> str | None:
        if settings.CHATBOT_API_KEY is not None:
            return f"Bearer {settings.CHATBOT_API_KEY}"
        return None

    @staticmethod
    def get_mcp_headers(request: Request, config: HttpConfiguration) -> dict:
        mcp_headers = {}
        jwt_header_name = "X-DAB-JW-TOKEN"
        token = request.headers.get(jwt_header_name, None)
        user = request.user
        if token and user.is_authenticated and user.aap_user:
            for mcp_server in config.mcp_servers:
                if mcp_server["type"] in ["controller", "eda", "hub", "lightspeed"]:
                    mcp_headers[mcp_server["name"]] = {jwt_header_name: token}
                # This functionality seems experimental for gateway and does not allow the user to
                # access wide range of api endpoints, we need to find a solution for gateway,
                # but for the moment comment this code.
                # elif mcp_server["type"] == "gateway":
                #     from ansible_base.resource_registry.resource_server import get_service_token
                #     user_ansible_id = str(user.ansible_id_for_filter)
                #     token = get_service_token(user_id=user_ansible_id, expiration=3600)
                #     mcp_headers[mcp_server["name"]] = {"X-ANSIBLE-SERVICE-AUTH": token}

        return mcp_headers


class Completions(APIView):
    """
    Returns inline code suggestions based on a given Ansible editor context.
    """

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


class Feedback(APIView):
    """
    Feedback API for the AI service
    """

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
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
        exception = None
        validated_data = {}
        try:
            request_serializer = FeedbackRequestSerializer(
                data=request.data, context={"request": request}
            )

            request_serializer.is_valid(raise_exception=True)
            validated_data = request_serializer.validated_data
            logger.info(f"feedback request payload from client: {validated_data}")
            return Response({"message": "Success"}, status=rest_framework_status.HTTP_200_OK)
        except serializers.ValidationError as exc:
            exception = exc
            raise FeedbackValidationException(str(exc))
        except Exception as exc:
            exception = exc
            logger.exception(f"An exception {exc.__class__} occurred in sending a feedback")
            raise FeedbackInternalServerException()
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
        suggestion_quality_data: SuggestionQualityFeedback = validated_data.get(
            "suggestionQualityFeedback"
        )
        sentiment_feedback_data: SentimentFeedback = validated_data.get("sentimentFeedback")
        issue_feedback_data: IssueFeedback = validated_data.get("issueFeedback")
        playbook_explanation_feedback_data: PlaybookExplanationFeedback = validated_data.get(
            "playbookExplanationFeedback"
        )
        playbook_generation_action_data: PlaybookGenerationAction = validated_data.get(
            "playbookGenerationAction"
        )
        role_generation_action_data: RoleGenerationAction = validated_data.get(
            "roleGenerationAction"
        )
        chatbot_feedback_data: ChatFeedback = validated_data.get("chatFeedback")

        ansible_extension_version = validated_data.get("metadata", {}).get(
            "ansibleExtensionVersion", None
        )
        model_name = ""
        try:
            org_id = getattr(user, "org_id", None)
            model_meta_data: MetaData = apps.get_app_config("ai").get_model_pipeline(MetaData)
            model_name = model_meta_data.get_model_id(user, str(validated_data.get("model", "")))
        except (WcaNoDefaultModelId, WcaModelIdNotFound, WcaSecretManagerError):
            logger.debug(
                f"Failed to retrieve Model Name for Feedback.\n "
                f"Org ID: {user.org_id}, "
                f"User has seat: {user.rh_user_has_seat}, "
                f"has subscription: {user.rh_org_has_subscription}.\n"
            )

        if inline_suggestion_data:
            event = {
                "userActionTime": inline_suggestion_data.get("userActionTime"),
                "action": inline_suggestion_data.get("action"),
                "suggestionId": str(inline_suggestion_data.get("suggestionId", "")),
                "modelName": model_name,
                "exception": exception is not None,
            }
            send_segment_event(event, "inlineSuggestionFeedback", user)
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
        if suggestion_quality_data:
            event = {
                "prompt": suggestion_quality_data.get("prompt"),
                "providedSuggestion": suggestion_quality_data.get("providedSuggestion"),
                "expectedSuggestion": suggestion_quality_data.get("expectedSuggestion"),
                "additionalComment": suggestion_quality_data.get("additionalComment"),
                "modelName": model_name,
                "exception": exception is not None,
            }
            send_segment_event(event, "suggestionQualityFeedback", user)
        if sentiment_feedback_data:
            event = {
                "value": sentiment_feedback_data.get("value"),
                "feedback": sentiment_feedback_data.get("feedback"),
                "modelName": model_name,
                "exception": exception is not None,
            }
            send_segment_event(event, "sentimentFeedback", user)
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
        if issue_feedback_data:
            event = {
                "type": issue_feedback_data.get("type"),
                "title": issue_feedback_data.get("title"),
                "description": issue_feedback_data.get("description"),
                "modelName": model_name,
                "exception": exception is not None,
            }
            send_segment_event(event, "issueFeedback", user)
        if playbook_explanation_feedback_data:
            event = {
                "action": playbook_explanation_feedback_data.get("action"),
                "explanation_id": str(playbook_explanation_feedback_data.get("explanationId", "")),
                "modelName": model_name,
            }
            send_segment_event(event, "playbookExplanationFeedback", user)
        if playbook_generation_action_data:
            action = int(playbook_generation_action_data.get("action"))
            from_page = playbook_generation_action_data.get("fromPage", 0)
            to_page = playbook_generation_action_data.get("toPage", 0)
            wizard_id = str(playbook_generation_action_data.get("wizardId", ""))
            event = {
                "action": action,
                "wizardId": wizard_id,
                "fromPage": from_page,
                "toPage": to_page,
                "modelName": model_name,
            }
            send_segment_event(event, "playbookGenerationAction", user)
            if from_page > 1 and action in [1, 3]:
                send_segment_analytics_event(
                    AnalyticsTelemetryEvents.PLAYBOOK_GENERATION_ACTION,
                    lambda: AnalyticsPlaybookGenerationWizard(
                        action=action,
                        model_name=model_name,
                        rh_user_org_id=org_id,
                        wizard_id=str(playbook_generation_action_data.get("wizardId", "")),
                    ),
                    user,
                    ansible_extension_version,
                )
        if role_generation_action_data:
            action = int(role_generation_action_data.get("action"))
            from_page = role_generation_action_data.get("fromPage", 0)
            to_page = role_generation_action_data.get("toPage", 0)
            wizard_id = str(role_generation_action_data.get("wizardId", ""))
            event = {
                "action": action,
                "wizardId": wizard_id,
                "fromPage": from_page,
                "toPage": to_page,
                "modelName": model_name,
            }
            send_segment_event(event, "roleGenerationAction", user)
            if from_page > 1 and action in [1, 3]:
                send_segment_analytics_event(
                    AnalyticsTelemetryEvents.ROLE_GENERATION_ACTION,
                    lambda: AnalyticsRoleGenerationWizard(
                        action=action,
                        model_name=model_name,
                        rh_user_org_id=org_id,
                        wizard_id=str(role_generation_action_data.get("wizardId", "")),
                    ),
                    user,
                    ansible_extension_version,
                )

        if chatbot_feedback_data:
            response_data = chatbot_feedback_data.get("response")
            chatbot_feedback_payload = ChatBotFeedbackEvent(
                chat_truncated=response_data["truncated"],
                chat_referenced_documents=[
                    ChatBotResponseDocsReferences(docs_url=rd["docs_url"], title=rd["title"])
                    for rd in response_data["referenced_documents"]
                ],
                conversation_id=response_data["conversation_id"],
                rh_user_org_id=getattr(user, "org_id", None),
                sentiment=chatbot_feedback_data.get("sentiment"),
            )
            send_schema1_event(chatbot_feedback_payload)

        feedback_events = [
            inline_suggestion_data,
            suggestion_quality_data,
            sentiment_feedback_data,
            issue_feedback_data,
            chatbot_feedback_data,
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
            elif "chatFeedback" in request_data:
                event_type = "chatFeedbackEvent"
            else:
                event_type = "unknown"

            event = {
                "data": ano_request_data,
                "exception": str(exception),
            }
            send_segment_event(event, event_type, user)


class ContentMatches(GenericAPIView):
    """
    Returns content matches that were the highest likelihood sources for a given code suggestion.
    """

    serializer_class = ContentMatchRequestSerializer

    permission_classes = (
        [
            permissions.IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
        ]
        if settings.DEPLOYMENT_MODE == "onprem"
        else [
            permissions.IsAuthenticated,
            IsAuthenticatedOrTokenHasScope,
            BlockUserWithoutSeat,
            BlockWCANotReadyButTrialAvailable,
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
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        request_data = request_serializer.validated_data
        suggestion_id = str(request_data.get("suggestionId", ""))
        model_id = str(request_data.get("model", ""))

        try:
            response_serializer = self.perform_content_matching(
                request, model_id, suggestion_id, request_data
            )
            return Response(response_serializer.data, status=rest_framework_status.HTTP_200_OK)
        except Exception:
            logger.exception("Error requesting content matches")
            raise

    def perform_content_matching(
        self,
        request,
        model_id: str,
        suggestion_id: str,
        request_data,
    ):
        model_mesh_client: ModelPipelineContentMatch = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineContentMatch
        )
        user_id = request.user.uuid
        content_match_data: ContentMatchPayloadData = {
            "suggestions": request_data.get("suggestions", []),
            "user_id": str(user_id) if user_id else None,
            "rh_user_has_seat": request.user.rh_user_has_seat,
            "organization_id": request.user.org_id,
            "suggestionId": suggestion_id,
        }
        logger.debug(
            f"input to content matches for suggestion id {suggestion_id}:\n{content_match_data}"
        )

        exception = None
        event = None
        event_name = None
        start_time = time.time()
        response_serializer = None
        metadata = []

        try:
            model_id, client_response = model_mesh_client.invoke(
                ContentMatchParameters.init(
                    request=request, model_input=content_match_data, model_id=model_id
                )
            )

            response_data = {"contentmatches": []}

            for response_item in client_response:
                content_match_dto = ContentMatchResponseDto(**response_item)
                response_data["contentmatches"].append(content_match_dto.content_matches)
                metadata.append(content_match_dto.meta)

                contentmatch_encoding_hist.observe(content_match_dto.encode_duration / 1000)
                contentmatch_search_hist.observe(content_match_dto.search_duration / 1000)

            try:
                response_serializer = ContentMatchResponseSerializer(data=response_data)
                response_serializer.is_valid(raise_exception=True)
            except Exception:
                process_error_count.labels(
                    stage="contentmatch-response_serialization_validation"
                ).inc()
                logger.exception(f"error serializing final response for suggestion {suggestion_id}")
                raise InternalServerError

        except ModelTimeoutError as e:
            exception = e
            logger.warn(
                f"model timed out after {model_mesh_client.config.timeout} seconds"
                f" for suggestion {suggestion_id}"
            )
            raise ModelTimeoutException(cause=e)

        except WcaBadRequest as e:
            exception = e
            logger.exception(f"bad request for content matching suggestion {suggestion_id}")
            raise WcaBadRequestException(cause=e)

        except WcaInvalidModelId as e:
            exception = e
            logger.exception(
                f"WCA Model ID is invalid for content matching suggestion {suggestion_id}"
            )
            raise WcaInvalidModelIdException(cause=e)

        except WcaKeyNotFound as e:
            exception = e
            logger.exception(
                f"A WCA Api Key was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaKeyNotFoundException(cause=e)

        except WcaModelIdNotFound as e:
            exception = e
            logger.exception(
                f"A WCA Model ID was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaModelIdNotFoundException(cause=e)

        except WcaNoDefaultModelId as e:
            exception = e
            logger.exception(
                "A default WCA Model ID was expected but not found for "
                f"content matching suggestion {suggestion_id}"
            )
            raise WcaNoDefaultModelIdException(cause=e)

        except WcaRequestIdCorrelationFailure as e:
            exception = e
            logger.exception(
                f"WCA Request/Response SuggestionId correlation failed "
                f"for suggestion {suggestion_id}"
            )
            raise WcaRequestIdCorrelationFailureException(cause=e)

        except WcaEmptyResponse as e:
            exception = e
            logger.exception(
                f"WCA returned an empty response for content matching suggestion {suggestion_id}"
            )
            raise WcaEmptyResponseException(cause=e)

        except WcaCloudflareRejection as e:
            exception = e
            logger.exception(f"Cloudflare rejected the request for {suggestion_id}")
            raise WcaCloudflareRejectionException(cause=e)

        except WcaUserTrialExpired as e:
            exception = e
            logger.exception(f"User trial expired, when requesting suggestion {suggestion_id}")
            event_name = "trialExpired"
            event = {
                "type": "contentmatch",
                "modelName": model_id,
                "suggestionId": str(suggestion_id),
            }
            raise WcaUserTrialExpiredException(cause=e)

        except WcaInstanceDeleted as e:
            exception = e
            logger.exception(
                f"WCA Instance has been deleted when requesting suggestion {suggestion_id} "
                f"for model {e.model_id}"
            )
            raise WcaInstanceDeletedException(cause=e)

        except Exception as e:
            exception = e
            logger.exception(f"Error requesting content matches for suggestion {suggestion_id}")
            raise ServiceUnavailable(cause=e)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            if exception:
                model_id_in_exception = BaseWisdomAPIException.get_model_id_from_exception(
                    exception
                )
                if model_id_in_exception:
                    model_id = model_id_in_exception
            if event:
                event["modelName"] = model_id
                send_segment_event(event, event_name, request.user)
            else:
                self.write_to_segment(
                    request_data,
                    duration,
                    exception,
                    metadata,
                    model_id,
                    response_serializer.data if response_serializer else {},
                    suggestion_id,
                    request.user,
                )

        return response_serializer

    def write_to_segment(
        self,
        request_data,
        duration,
        exception,
        metadata,
        model_id,
        response_data,
        suggestion_id,
        user,
    ):
        event = {
            "duration": duration,
            "exception": exception is not None,
            "modelName": model_id,
            "problem": None if exception is None else exception.__class__.__name__,
            "request": request_data,
            "response": response_data,
            "suggestionId": str(suggestion_id),
            "rh_user_has_seat": user.rh_user_has_seat,
            "rh_user_org_id": user.org_id,
            "metadata": metadata,
        }
        send_segment_event(event, "contentmatch", user)


class Explanation(AACSAPIView):
    """
    Returns a text that explains a playbook.
    """

    permission_classes = PERMISSIONS_MAP.get(settings.DEPLOYMENT_MODE)
    required_scopes = ["read", "write"]
    schema1_event = schema1.ExplainPlaybookEvent
    request_serializer_class = ExplanationRequestSerializer
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
        summary="Playbook explanation",
    )
    @extend_schema_if_available(
        extensions={"x-ai-description": "Create an explanation of a playbook"},
    )
    def post(self, request) -> Response:
        self.event.playbook_length = len(self.validated_data["content"])
        self.event.explanationId = self.validated_data["explanationId"]
        llm: ModelPipelinePlaybookExplanation = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelinePlaybookExplanation
        )
        explanation = llm.invoke(
            PlaybookExplanationParameters.init(
                request=request,
                content=self.validated_data["content"],
                custom_prompt=self.validated_data["customPrompt"],
                explanation_id=self.validated_data["explanationId"],
                model_id=self.validated_data["model"],
            )
        )

        # Anonymize response
        # Anonymized in the View to be consistent with where Completions are anonymized
        anonymized_explanation = anonymizer.anonymize_struct(
            explanation, value_template=Template("{{ _${variable_name}_ }}")
        )

        answer = {
            "content": anonymized_explanation,
            "format": "markdown",
            "explanationId": self.validated_data["explanationId"],
        }

        return Response(
            answer,
            status=rest_framework_status.HTTP_200_OK,
        )


class ExplanationRole(AACSAPIView):
    """
    Returns a text that explains a role.
    """

    permission_classes = PERMISSIONS_MAP.get(settings.DEPLOYMENT_MODE)
    required_scopes = ["read", "write"]
    schema1_event = schema1.ExplainRoleEvent
    request_serializer_class = ExplanationRoleRequestSerializer
    throttle_cache_key_suffix = "_explanation"

    @extend_schema(
        request=ExplanationRoleRequestSerializer,
        responses={
            200: ExplanationResponseSerializer,
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            429: OpenApiResponse(description="Request was throttled"),
            503: OpenApiResponse(description="Service Unavailable"),
        },
        summary="Role explanation",
    )
    @extend_schema_if_available(extensions={"x-ai-description": "Create an explanation of a role"})
    def post(self, request) -> Response:
        llm: ModelPipelineRoleExplanation = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineRoleExplanation
        )
        explanation = llm.invoke(
            RoleExplanationParameters.init(
                request=request,
                files=self.validated_data["files"],
                role_name=self.validated_data["roleName"],
                model_id=self.validated_data["model"],
                focus_on_file=self.validated_data["focusOnFile"],
                explanation_id=self.validated_data["explanationId"],
            )
        )

        # Anonymize response
        # Anonymized in the View to be consistent with where Completions are anonymized
        anonymized_explanation = anonymizer.anonymize_struct(
            explanation, value_template=Template("{{ _${variable_name}_ }}")
        )

        answer = {
            "content": anonymized_explanation,
            "format": "markdown",
        }

        return Response(
            answer,
            status=rest_framework_status.HTTP_200_OK,
        )


class GenerationPlaybook(AACSAPIView):
    """
    Returns a playbook based on a text input.
    """

    permission_classes = PERMISSIONS_MAP.get(settings.DEPLOYMENT_MODE)
    required_scopes = ["read", "write"]
    schema1_event = schema1.GenerationPlaybookEvent
    request_serializer_class = GenerationPlaybookRequestSerializer
    throttle_cache_key_suffix = "_generation_playbook"

    @extend_schema(
        request=GenerationPlaybookRequestSerializer,
        responses={
            200: GenerationPlaybookResponseSerializer,
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            429: OpenApiResponse(description="Request was throttled"),
            503: OpenApiResponse(description="Service Unavailable"),
        },
        summary="Playbook generation",
    )
    @extend_schema_if_available(
        extensions={"x-ai-description": "Generate a playbook based on a text input"}
    )
    def post(self, request) -> Response:
        self.event.create_outline = self.validated_data["createOutline"]
        self.event.generationId = self.validated_data["generationId"]
        self.event.wizardId = self.validated_data["wizardId"]

        llm: ModelPipelinePlaybookGeneration = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelinePlaybookGeneration
        )
        playbook, outline, warnings = llm.invoke(
            PlaybookGenerationParameters.init(
                request=request,
                text=self.validated_data["text"],
                custom_prompt=self.validated_data["customPrompt"],
                create_outline=self.validated_data["createOutline"],
                outline=self.validated_data["outline"],
                generation_id=self.validated_data["generationId"],
                model_id=self.req_model_id,
            )
        )
        # Anonymize responses
        # Anonymized in the View to be consistent with where Completions are anonymized
        anonymized_playbook = anonymizer.anonymize_struct(
            playbook, value_template=Template("{{ _${variable_name}_ }}")
        )
        anonymized_outline = anonymizer.anonymize_struct(
            outline, value_template=Template("{{ _${variable_name}_ }}")
        )
        self.event.playbook_length = len(anonymized_playbook)

        answer = {
            "playbook": anonymized_playbook,
            "outline": anonymized_outline,
            "warnings": warnings,
            "format": "plaintext",
            "generationId": self.validated_data["generationId"],
        }

        return Response(
            answer,
            status=rest_framework_status.HTTP_200_OK,
        )


class GenerationRole(AACSAPIView):
    """
    Returns a role based on a text input.
    """

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
    ]
    required_scopes = ["read", "write"]
    schema1_event = schema1.GenerationRoleEvent
    request_serializer_class = GenerationRoleRequestSerializer
    throttle_cache_key_suffix = "_generation_role"

    @extend_schema(
        request=GenerationRoleRequestSerializer,
        responses={
            200: GenerationRoleResponseSerializer,
            401: OpenApiResponse(description="Unauthorized"),
        },
        summary="Role generation",
    )
    @extend_schema_if_available(
        extensions={"x-ai-description": "Generate a role based on a text input"}
    )
    def post(self, request) -> Response:
        self.event.create_outline = self.validated_data["createOutline"]
        self.event.generationId = self.validated_data["generationId"]
        self.event.wizardId = self.validated_data["wizardId"]
        llm: ModelPipelineRoleGeneration = apps.get_app_config("ai").get_model_pipeline(
            ModelPipelineRoleGeneration
        )

        roles, files, outline, warnings = llm.invoke(
            RoleGenerationParameters.init(
                request=request,
                name=self.validated_data["name"],
                text=self.validated_data["text"],
                outline=self.validated_data["outline"],
                model_id=self.req_model_id,
                create_outline=self.validated_data["createOutline"],
                additional_context=self.validated_data.get("additionalContext", {}),
                file_types=self.validated_data["fileTypes"],
                generation_id=self.validated_data["generationId"],
            )
        )

        # Anonymize responses
        # Anonymized in the View to be consistent with where Completions are anonymized
        anonymized_role = anonymizer.anonymize_struct(
            roles, value_template=Template("{{ _${variable_name}_ }}")
        )
        anonymized_outline = anonymizer.anonymize_struct(
            outline, value_template=Template("{{ _${variable_name}_ }}")
        )
        anonymized_files = anonymizer.anonymize_struct(
            files, value_template=Template("{{ _${variable_name}_ }}")
        )

        answer = {
            "name": anonymized_role,
            "outline": anonymized_outline,
            "files": anonymized_files,
            "format": "plaintext",
            "generationId": self.validated_data["generationId"],
            "warnings": warnings,
        }

        return Response(
            answer,
            status=rest_framework_status.HTTP_200_OK,
        )


class Chat(AACSAPIView):
    """
    Send a message to the backend chatbot service and get a reply.
    """

    class ChatEndpointThrottle(EndpointRateThrottle):
        scope = "chat"

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsRHInternalUser | IsTestUser | IsAAPUser | IsOrganisationLightspeedSubscriber,
    ]
    required_scopes = ["read", "write"]
    schema1_event = schema1.ChatBotOperationalEvent
    request_serializer_class = ChatRequestSerializer
    throttle_classes = [ChatEndpointThrottle]

    llm: ModelPipelineChatBot

    def __init__(self):
        super().__init__()
        self.llm = apps.get_app_config("ai").get_model_pipeline(ModelPipelineChatBot)

        self.chatbot_enabled = (
            self.llm.config.inference_url
            and self.llm.config.model_id
            and settings.CHATBOT_DEFAULT_PROVIDER
        )
        if self.chatbot_enabled:
            logger.debug("Chatbot is enabled.")
        else:
            logger.debug("Chatbot is not enabled.")

    @extend_schema(
        request=ChatRequestSerializer,
        responses={
            200: ChatResponseSerializer,
            400: OpenApiResponse(description="Bad request"),
            403: OpenApiResponse(description="Forbidden"),
            413: OpenApiResponse(description="Prompt too long"),
            422: OpenApiResponse(description="Validation failed"),
            500: OpenApiResponse(description="Internal server error"),
            503: OpenApiResponse(description="Service unavailable"),
        },
        summary="Chat request",
    )
    def post(self, request) -> Response:
        headers = {"Content-Type": "application/json"}

        if not self.chatbot_enabled:
            raise ChatbotNotEnabledException()

        req_query = self.validated_data["query"]
        req_system_prompt = self.validated_data.get("system_prompt")
        req_provider = self.validated_data.get("provider", settings.CHATBOT_DEFAULT_PROVIDER)
        conversation_id = self.validated_data.get("conversation_id")
        no_tools = self.validated_data.get("no_tools", False)

        # Initialise Segment Event early, in case of exceptions
        self.event.chat_system_prompt = req_system_prompt
        self.event.provider_id = req_provider
        self.event.conversation_id = conversation_id
        self.event.modelName = self.req_model_id or self.llm.config.model_id
        self.event.no_tools = no_tools

        auth_header = self.get_auth_header()
        mcp_headers = self.get_mcp_headers(request, self.llm.config)

        data = self.llm.invoke(
            ChatBotParameters.init(
                query=req_query,
                system_prompt=req_system_prompt,
                model_id=self.req_model_id or self.llm.config.model_id,
                provider=req_provider,
                conversation_id=conversation_id,
                auth_header=auth_header,
                mcp_headers=mcp_headers,
                no_tools=no_tools,
            )
        )

        response_serializer = ChatResponseSerializer(data=data)

        if not response_serializer.is_valid():
            raise ChatbotInvalidResponseException()

        # Finalise Segment Event with response details
        self.event.chat_truncated = bool(data.get("truncated", False))
        self.event.chat_referenced_documents = [
            ChatBotResponseDocsReferences(docs_url=rd["docs_url"], title=rd["title"])
            for rd in data.get("referenced_documents", [])
        ]

        return Response(
            data,
            status=rest_framework_status.HTTP_200_OK,
            headers=headers,
        )


class StreamingChat(AACSAPIView):
    """
    Send a message to the backend chatbot service and get a streaming reply.
    """

    class StreamingChatEndpointThrottle(EndpointRateThrottle):
        scope = "chat"

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsRHInternalUser | IsTestUser | IsAAPUser | IsOrganisationLightspeedSubscriber,
    ]
    required_scopes = ["read", "write"]
    schema1_event = schema1.StreamingChatBotOperationalEvent
    request_serializer_class = StreamingChatRequestSerializer
    throttle_classes = [StreamingChatEndpointThrottle]

    llm: ModelPipelineStreamingChatBot

    def __init__(self):
        super().__init__()
        self.llm = apps.get_app_config("ai").get_model_pipeline(ModelPipelineStreamingChatBot)

        self.chatbot_enabled = (
            self.llm.config.inference_url
            and self.llm.config.model_id
            and settings.CHATBOT_DEFAULT_PROVIDER
        )
        if self.chatbot_enabled:
            logger.debug("Chatbot is enabled.")
        else:
            logger.debug("Chatbot is not enabled.")

    @extend_schema(
        request=StreamingChatRequestSerializer,
        responses={
            200: ChatResponseSerializer,  # TODO
            400: OpenApiResponse(description="Bad request"),
            403: OpenApiResponse(description="Forbidden"),
            413: OpenApiResponse(description="Prompt too long"),
            422: OpenApiResponse(description="Validation failed"),
            500: OpenApiResponse(description="Internal server error"),
            503: OpenApiResponse(description="Service unavailable"),
        },
        summary="Streaming chat request",
    )
    def post(self, request) -> StreamingHttpResponse:
        if not self.chatbot_enabled:
            raise ChatbotNotEnabledException()

        req_query = self.validated_data["query"]
        req_system_prompt = self.validated_data.get("system_prompt")
        req_provider = self.validated_data.get("provider", settings.CHATBOT_DEFAULT_PROVIDER)
        conversation_id = self.validated_data.get("conversation_id")
        media_type = self.validated_data.get("media_type")
        no_tools = self.validated_data.get("no_tools", False)

        # Initialise Segment Event early, in case of exceptions
        self.event.chat_system_prompt = req_system_prompt
        self.event.provider_id = req_provider
        self.event.conversation_id = conversation_id
        self.event.modelName = self.req_model_id or self.llm.config.model_id
        self.event.no_tools = no_tools

        auth_header = self.get_auth_header()
        mcp_headers = self.get_mcp_headers(request, self.llm.config)

        return self.llm.invoke(
            StreamingChatBotParameters.init(
                query=req_query,
                system_prompt=req_system_prompt,
                model_id=self.req_model_id or self.llm.config.model_id,
                provider=req_provider,
                conversation_id=conversation_id,
                media_type=media_type,
                event=copy.copy(self.event),
                auth_header=auth_header,
                mcp_headers=mcp_headers,
                no_tools=no_tools,
            )
        )
