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
from .serializers import GenerationRequestSerializer, GenerationResponseSerializer
from .utils.segment import send_segment_event

logger = logging.getLogger(__name__)


class Generation(APIView):
    """
    Returns a playbook based on a text input.
    """

    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

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

        # This isn't ideal... but I need generation_id for loggin in the decorator
        def generation_id_provider():
            request_serializer = GenerationRequestSerializer(data=request.data)
            request_serializer.is_valid(raise_exception=False)
            return str(request_serializer.data.get("generationId", ""))

        @call("generation", generation_id_provider)
        def get_generation() -> Response:
            exception = None
            wizard_id = None
            duration = None
            create_outline = None
            anonymized_playbook = ""
            request_serializer = GenerationRequestSerializer(data=request.data)

            try:
                generation_id = generation_id_provider()
                request_serializer.is_valid(raise_exception=True)
                create_outline = request_serializer.validated_data["createOutline"]
                outline = str(request_serializer.validated_data.get("outline", ""))
                text = request_serializer.validated_data["text"]
                wizard_id = str(request_serializer.validated_data.get("wizardId", ""))

                llm = apps.get_app_config("ai").model_mesh_client
                start_time = time.time()
                playbook, outline = llm.generate_playbook(request, text, create_outline, outline)
                duration = round((time.time() - start_time) * 1000, 2)

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

            finally:
                self.write_to_segment(
                    request.user,
                    generation_id,
                    wizard_id,
                    exception,
                    duration,
                    create_outline,
                    playbook_length=len(anonymized_playbook),
                )

            return Response(
                answer,
                status=rest_framework_status.HTTP_200_OK,
            )

        return get_generation()

    def write_to_segment(
        self, user, generation_id, wizard_id, exception, duration, create_outline, playbook_length
    ):
        model_name = ""
        try:
            model_mesh_client = apps.get_app_config("ai").model_mesh_client
            model_name = model_mesh_client.get_model_id(user.org_id, "")
        except (WcaNoDefaultModelId, WcaModelIdNotFound, WcaSecretManagerError):
            pass
        event = {
            "create_outline": create_outline,
            "duration": duration,
            "exception": exception is not None,
            "generationId": generation_id,
            "modelName": model_name,
            "playbook_length": playbook_length,
            "wizardId": wizard_id,
        }
        if exception:
            event["response"] = (
                {
                    "exception": str(exception),
                },
            )
        send_segment_event(event, "codegenPlaybook", user)
