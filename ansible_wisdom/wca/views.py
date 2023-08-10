import codecs
import logging

from django.conf import settings
from django.http import HttpResponseNotFound
from django.utils.encoding import DjangoUnicodeDecodeError, smart_str
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.exceptions import ParseError
from rest_framework.generics import (
    CreateAPIView,
    DestroyAPIView,
    RetrieveAPIView,
    UpdateAPIView,
)
from rest_framework.parsers import BaseParser
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST

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


class WCAKeyView(RetrieveAPIView, CreateAPIView, DestroyAPIView):
    from ai.api.permissions import AcceptedTermsPermission, IsAdministrator
    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    # Temporary storage until AWS-SM is integrated
    __storage__: dict[str, str] = {}

    def __get_wca_key__(self, org_id: str) -> str:
        # This is temporary until we have the AWS-SM service
        return self.__storage__.get(org_id)

    def __set_wca_key__(self, wca_key: any, org_id: str):
        # This is temporary until we have the AWS-SM service
        self.__storage__[org_id] = wca_key

    def __delete_wca_key__(self, org_id: str):
        del self.__storage__[org_id]

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

        org_id = kwargs.get("org_id")
        if org_id not in self.__storage__:
            return HttpResponseNotFound()

        # Once written the Key value is never returned to the User
        return Response(status=HTTP_200_OK)

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

        # The data has already been decoded by this point
        wca_key = request.data
        org_id = kwargs.get("org_id")
        self.__set_wca_key__(wca_key, org_id)

        return Response(status=HTTP_204_NO_CONTENT)

    @extend_schema(
        responses={
            204: OpenApiResponse(description='Empty response'),
            404: OpenApiResponse(description='Not found'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Delete the WCA key for an Organisation",
        operation_id="wca_delete",
    )
    def delete(self, request, *args, **kwargs):
        logger.info("Delete handler")

        org_id = kwargs.get("org_id")
        if org_id not in self.__storage__:
            return HttpResponseNotFound()

        self.__delete_wca_key__(org_id)

        return Response(status=HTTP_204_NO_CONTENT)
