import json
import logging
import time

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status as rest_framework_status
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers

from ai.api.pipelines.completion_stages.post_process import get_ansible_lint_caller

from .serializers import ContentScanRequestSerializer, ContentScanResponseSerializer
from .utils.lintable_dict import LintableDict

logger = logging.getLogger(__name__)


class ContentScan(APIView):
    """
    Returns scan run response for Ansible files.
    """

    serializer_class = ContentScanRequestSerializer

    # from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    # from rest_framework import permissions

    # permission_classes = [
    #     permissions.IsAuthenticated,
    #     IsAuthenticatedOrTokenHasScope,
    #     AcceptedTermsPermission,
    # ]
    # required_scopes = ['read', 'write']

    # throttle_cache_key_suffix = '_scan'

    @extend_schema(
        request=ContentScanRequestSerializer,
        responses={
            200: ContentScanResponseSerializer,
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Code suggestion attributions",
    )
    def post(self, request) -> Response:
        validated_data = {}
        run_result = {}
        exception = None
        transformed_content = ""
        try:
            request_serializer = ContentScanRequestSerializer(
                data=request.data, context={'request': request}
            )
            request_serializer.is_valid(raise_exception=True)
            validated_data = request_serializer.validated_data
            logger.info("Scan Content request payload from client: %s", validated_data)
            # todo: remove has seat override
            request.user.rh_user_has_seat = True
            ansible_lint_caller = get_ansible_lint_caller(request.user)
            if not validated_data['fileContent'].endswith('\n'):
                validated_data['fileContent'] += '\n'
            if ansible_lint_caller:
                start_time = time.time()
                try:
                    transformed_content, run_result = ansible_lint_caller.run_linter(
                        validated_data['fileContent'], auto_fix=validated_data['autoFix']
                    )
                except Exception as exc:
                    exception = exc
                    logger.exception(
                        f'Ansible lint content scanning resulted into exception: {exc}'
                    )
                    transformed_content = validated_data['inline_completion']
                finally:
                    logger.info("Scanning took %s seconds", time.time() - start_time)
                    if exception:
                        raise exception
            else:
                transformed_content = validated_data['fileContent']
                logger.warning(
                    "Ansible lint content scanning is not available for user: %s", request.user
                )
            diagnostics = [LintableDict(lintable) for lintable in run_result.matches]

            response_serializer = ContentScanResponseSerializer(
                data={
                    "fileContent": transformed_content,
                    "diagnostics": diagnostics,
                }
            )
            response_serializer.is_valid(raise_exception=True)
            return Response(
                response_serializer.validated_data, status=rest_framework_status.HTTP_200_OK
            )
        except serializers.ValidationError as exc:
            return Response({"message": str(exc)}, status=exc.status_code)
        except Exception as exc:
            logger.exception("An exception %s occurred in sending a feedback", exc.__class__)
            return Response(
                {"message": "Failed to send feedback"},
                status=rest_framework_status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        finally:
            pass
