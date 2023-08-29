import logging

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes
from ai.api.serializers import WcaModelIdRequestSerializer
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


class WCAModelIdView(RetrieveAPIView, CreateAPIView):
    from ai.api.permissions import (
        AcceptedTermsPermission,
        IsLightspeedSubscriber,
        IsOrganisationAdministrator,
        IsWCAModelIdApiFeatureFlagOn,
    )
    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope

    permission_classes = [
        IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsOrganisationAdministrator,
        IsLightspeedSubscriber,
        AcceptedTermsPermission,
        IsWCAModelIdApiFeatureFlagOn,
    ]
    required_scopes = ['read', 'write']
    throttle_cache_key_suffix = '_wca_model_id'

    @extend_schema(
        responses={
            200: OpenApiResponse(description='OK'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            404: OpenApiResponse(description='Not found'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Get WCA Model Id for an Organisation",
        operation_id="wca_model_id_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("WCA Model Id:: GET handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_id = kwargs.get("org_id")
        try:
            response = secret_manager.get_secret(org_id, Suffixes.MODEL_ID)
            if response is None:
                return Response(status=HTTP_404_NOT_FOUND)
            return Response(
                status=HTTP_200_OK,
                data={'model_id': response['SecretString'], 'LastUpdate': response['CreatedDate']},
            )
        except WcaSecretManagerError as e:
            logger.error(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        request=WcaModelIdRequestSerializer,
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Set the Model Id to be used for an Organisation",
        operation_id="wca_model_id_set",
    )
    def post(self, request, *args, **kwargs):
        logger.debug("WCA Model Id:: POST handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        model_id_serializer = WcaModelIdRequestSerializer(data=request.data)
        org_id = kwargs.get("org_id")
        try:
            model_id_serializer.is_valid(raise_exception=True)
            model_id = model_id_serializer.validated_data['model_id']
            secret_name = secret_manager.save_secret(org_id, Suffixes.MODEL_ID, model_id)
            logger.info(f"Stored Secret '${secret_name}' for org_id '{org_id}'")
        except WcaSecretManagerError as e:
            logger.error(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)
        except ValidationError as e:
            logger.error(e)
            return Response(status=HTTP_400_BAD_REQUEST)

        return Response(status=HTTP_204_NO_CONTENT)
