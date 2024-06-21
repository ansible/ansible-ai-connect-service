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
from http import HTTPStatus

from django.apps import apps
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework import permissions
from rest_framework import status as rest_framework_status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response

from ansible_ai_connect.ai.api.api_wrapper import call
from ansible_ai_connect.ai.api.exceptions import (
    BaseWisdomAPIException,
    InternalServerError,
    WcaUserTrialExpiredException,
    process_error_count,
)
from ansible_ai_connect.users.models import User

from .. import search as ai_search
from .data.data_model import (
    AttributionsResponseDto,
    ContentMatchPayloadData,
    ContentMatchResponseDto,
)
from .permissions import AcceptedTermsPermission, BlockUserWithoutSeat, IsAAPLicensed
from .serializers import ContentMatchRequestSerializer, ContentMatchResponseSerializer
from .utils.segment import send_segment_event
from .views import contentmatch_encoding_hist, contentmatch_search_hist

logger = logging.getLogger(__name__)


class ContentMatches(GenericAPIView):
    """
    Returns content matches that were the highest likelihood sources for a given code suggestion.
    """

    serializer_class = ContentMatchRequestSerializer

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
        request_serializer = self.get_serializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)

        request_data = request_serializer.validated_data
        suggestion_id = str(request_data.get("suggestionId", ""))
        model_id = str(request_data.get("model", ""))

        try:
            if request.user.rh_user_has_seat:
                response_serializer = self.perform_content_matching(
                    model_id, suggestion_id, request.user, request_data
                )
            else:
                response_serializer = self.perform_search(request_data, request.user)
            return Response(response_serializer.data, status=rest_framework_status.HTTP_200_OK)
        except Exception:
            logger.exception("Error requesting content matches")
            raise

    def perform_content_matching(
        self,
        model_id: str,
        suggestion_id: str,
        user: User,
        request_data,
    ):
        _model_id = model_id

        @call("suggestions", suggestion_id)
        def get_content_matches() -> ContentMatchResponseSerializer:
            __model_id = _model_id
            model_mesh_client = apps.get_app_config("ai").model_mesh_client
            user_id = user.uuid
            content_match_data: ContentMatchPayloadData = {
                "suggestions": request_data.get("suggestions", []),
                "user_id": str(user_id) if user_id else None,
                "rh_user_has_seat": user.rh_user_has_seat,
                "organization_id": user.org_id,
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
                __model_id, client_response = model_mesh_client.codematch(
                    content_match_data, __model_id
                )

                response_data = {"contentmatches": []}

                for response_item in client_response:
                    content_match_dto = ContentMatchResponseDto(**response_item)
                    response_data["contentmatches"].append(content_match_dto.content_matches)
                    metadata.append(content_match_dto.meta)

                    contentmatch_encoding_hist.observe(content_match_dto.encode_duration / 1000)
                    contentmatch_search_hist.observe(content_match_dto.search_duration / 1000)

                response_serializer = ContentMatchResponseSerializer(data=response_data)
                response_serializer.is_valid(raise_exception=True)

            except ValidationError:
                process_error_count.labels(
                    stage="contentmatch-response_serialization_validation"
                ).inc()
                logger.exception(f"error serializing final response for suggestion {suggestion_id}")
                raise InternalServerError

            except WcaUserTrialExpiredException as e:
                exception = e
                event = {
                    "type": "prediction",
                    "modelName": __model_id,
                    "suggestionId": str(suggestion_id),
                }
                event_name = "trialExpired"
                raise

            except Exception as e:
                exception = e
                raise

            finally:
                duration = round((time.time() - start_time) * 1000, 2)
                if exception:
                    model_id_in_exception = BaseWisdomAPIException.get_model_id_from_exception(
                        exception
                    )
                    if model_id_in_exception:
                        __model_id = model_id_in_exception
                if event:
                    event["modelName"] = __model_id
                    send_segment_event(event, event_name, user)
                else:
                    self.write_to_segment(
                        request_data,
                        duration,
                        exception,
                        metadata,
                        __model_id,
                        response_serializer.data if response_serializer else {},
                        suggestion_id,
                        user,
                    )

            return response_serializer

        return get_content_matches()

    def perform_search(self, request_data, user: User):
        suggestion_id = str(request_data.get("suggestionId", ""))
        response_serializer = None

        exception = None
        start_time = time.time()
        metadata = []
        model_name = ""

        try:
            suggestion = request_data["suggestions"][0]
            response_item = ai_search.search(suggestion)

            attributions_dto = AttributionsResponseDto(**response_item)
            response_data = {"contentmatches": []}
            response_data["contentmatches"].append(attributions_dto.content_matches)
            metadata.append(attributions_dto.meta)

            try:
                response_serializer = ContentMatchResponseSerializer(data=response_data)
                response_serializer.is_valid(raise_exception=True)
            except Exception:
                process_error_count.labels(stage="attr-response_serialization_validation").inc()
                logger.exception(f"Error serializing final response for suggestion {suggestion_id}")
                raise InternalServerError

        except Exception as e:
            exception = e
            logger.exception("Failed to search for attributions for content matching")
            return Response(
                {"message": "Unable to complete the request"}, status=HTTPStatus.SERVICE_UNAVAILABLE
            )
        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            self.write_to_segment(
                request_data,
                duration,
                exception,
                metadata,
                model_name,
                response_serializer.data if response_serializer else {},
                suggestion_id,
                user,
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
