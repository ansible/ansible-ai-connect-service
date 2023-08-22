import codecs
import logging

from ai.api.aws.exceptions import WcaSecretManagerError
from django.apps import apps
from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ParseError
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.parsers import BaseParser
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_404_NOT_FOUND,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

logger = logging.getLogger(__name__)


class TextParser(BaseParser):
    """
    Parses Text-serialized data.
    """

    media_type = 'text/plain'

    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parses the incoming bytestream as Text and returns the resulting data.
        """
        parser_context = parser_context or {}
        encoding = parser_context.get('encoding', settings.DEFAULT_CHARSET)

        try:
            decoded_stream = codecs.getreader(encoding)(stream)
            decoded = decoded_stream.decode(stream.body)
            return str(decoded[0])
        except UnicodeDecodeError as exc:
            raise ParseError(detail=exc)


class WCAKeyView(RetrieveAPIView, CreateAPIView):
    from ai.api.permissions import AcceptedTermsPermission, IsAdministrator
    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsAdministrator,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read', 'write']
    throttle_cache_key_suffix = '_wca'
    parser_classes = [TextParser]

    @extend_schema(
        responses={
            200: OpenApiResponse(description='OK'),
            401: OpenApiResponse(description='Unauthorized'),
            404: OpenApiResponse(description='Not found'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Get WCA key for an Organisation",
        operation_id="wca_get",
    )
    def get(self, request, *args, **kwargs):
        logger.info("Get handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        org_id = kwargs.get("org_id")
        try:
            response = secret_manager.get_key(org_id)
            if response is None:
                return Response(status=HTTP_404_NOT_FOUND)
            # Once written the Key value is never returned to the User,
            # instead we return when the secret was last updated.
            return Response(status=HTTP_200_OK, data={'LastUpdate': response['CreatedDate']})
        except WcaSecretManagerError as e:
            logger.error(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)

    @extend_schema(
        request={'text/plain; charset=utf-8': OpenApiTypes.STR},
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Set a WCA key for an Organisation",
        operation_id="wca_set",
    )
    def post(self, request, *args, **kwargs):
        logger.info("Set handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()

        # The data has already been decoded by this point
        wca_key = request.data
        org_id = kwargs.get("org_id")
        try:
            secret_name = secret_manager.save_key(org_id, wca_key)
            logger.info(f"stored secret ${secret_name} for org_id {org_id}")
        except WcaSecretManagerError as e:
            logger.error(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(status=HTTP_204_NO_CONTENT)
