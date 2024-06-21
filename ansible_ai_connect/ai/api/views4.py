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
from drf_spectacular.utils import OpenApiResponse, extend_schema
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework import permissions
from rest_framework import status as rest_framework_status
from rest_framework.response import Response
from rest_framework.views import APIView

from ansible_ai_connect.ai.api.api_wrapper import call
from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.model_client.exceptions import (
    WcaModelIdNotFound,
    WcaNoDefaultModelId,
)

from .permissions import (
    AcceptedTermsPermission,
    BlockUserWithoutSeat,
    BlockUserWithoutSeatAndWCAReadyOrg,
    BlockUserWithSeatButWCANotReady,
)
from .serializers import ExplanationRequestSerializer, ExplanationResponseSerializer
from .utils.segment import send_segment_event

logger = logging.getLogger(__name__)


class Explanation(APIView):
    """
    Returns a text that explains a playbook.
    """

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

        # This isn't ideal... but I need explanation_id for logging in the decorator
        def explanation_id_provider():
            request_serializer = ExplanationRequestSerializer(data=request.data)
            request_serializer.is_valid(raise_exception=False)
            return str(request_serializer.data.get("explanationId", ""))

        @call("explanation", explanation_id_provider)
        def get_explanation() -> Response:
            duration = None
            exception = None
            explanation_id = None
            playbook = ""
            request_serializer = ExplanationRequestSerializer(data=request.data)

            try:
                request_serializer.is_valid(raise_exception=True)
                explanation_id = explanation_id_provider()
                playbook = request_serializer.validated_data.get("content")

                llm = apps.get_app_config("ai").model_mesh_client
                start_time = time.time()
                explanation = llm.explain_playbook(request, playbook)
                duration = round((time.time() - start_time) * 1000, 2)

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

            except Exception as exc:
                exception = exc
                raise

            finally:
                self.write_to_segment(
                    request.user,
                    explanation_id,
                    exception,
                    duration,
                    playbook_length=len(playbook),
                )

            return Response(
                answer,
                status=rest_framework_status.HTTP_200_OK,
            )

        return get_explanation()

    def write_to_segment(self, user, explanation_id, exception, duration, playbook_length):
        model_name = ""
        try:
            model_mesh_client = apps.get_app_config("ai").model_mesh_client
            model_name = model_mesh_client.get_model_id(user.org_id, "")
        except (WcaNoDefaultModelId, WcaModelIdNotFound, WcaSecretManagerError):
            pass

        event = {
            "duration": duration,
            "exception": exception is not None,
            "explanationId": explanation_id,
            "modelName": model_name,
            "playbook_length": playbook_length,
            "rh_user_org_id": user.org_id,
        }
        if exception:
            event["response"] = (
                {
                    "exception": str(exception),
                },
            )
        send_segment_event(event, "explainPlaybook", user)
