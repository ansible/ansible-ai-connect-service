import logging

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes
from ai.api.serializers import WcaKeyRequestSerializer
from django.apps import apps
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

logger = logging.getLogger(__name__)


class WCAApiKeyView(RetrieveAPIView, CreateAPIView):
    from ai.api.permissions import (
        AcceptedTermsPermission,
        IsLightspeedSubscriber,
        IsOrganisationAdministrator,
        IsWCAKeyApiFeatureFlagOn,
    )
    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope

    permission_classes = [
        IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsOrganisationAdministrator,
        IsLightspeedSubscriber,
        AcceptedTermsPermission,
        IsWCAKeyApiFeatureFlagOn,
    ]
    required_scopes = ['read', 'write']
    throttle_cache_key_suffix = '_wca_api_key'

    @extend_schema(
        responses={
            200: OpenApiResponse(description='OK'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            404: OpenApiResponse(description='Not found'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Get WCA key for an Organisation",
        operation_id="wca_api_key_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("WCA API Key:: GET handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_id = kwargs.get("org_id")
        try:
            response = secret_manager.get_secret(org_id, Suffixes.API_KEY)
            if response is None:
                return Response(status=HTTP_404_NOT_FOUND)
            # Once written the Key value is never returned to the User,
            # instead we return when the secret was last updated.
            return Response(status=HTTP_200_OK, data={'LastUpdate': response['CreatedDate']})
        except WcaSecretManagerError as e:
            logger.error(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        request=WcaKeyRequestSerializer,
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Set the WCA key for an Organisation",
        operation_id="wca_api_key_set",
    )
    def post(self, request, *args, **kwargs):
        logger.debug("WCA API Key:: POST handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        key_serializer = WcaKeyRequestSerializer(data=request.data)
        org_id = kwargs.get("org_id")
        try:
            key_serializer.is_valid(raise_exception=True)
            wca_key = key_serializer.validated_data['key']
            secret_name = secret_manager.save_secret(org_id, Suffixes.API_KEY, wca_key)
            logger.info(f"Stored secret '${secret_name}' for org_id '{org_id}'")
        except WcaSecretManagerError as e:
            logger.error(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)
        except ValidationError as e:
            logger.error(e)
            return Response(status=HTTP_400_BAD_REQUEST)

        return Response(status=HTTP_204_NO_CONTENT)
