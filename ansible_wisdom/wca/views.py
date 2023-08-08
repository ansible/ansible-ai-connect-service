import logging

from django.http import HttpResponseBadRequest, HttpResponseNotFound
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import (
    CreateAPIView,
    DestroyAPIView,
    ListAPIView,
    RetrieveAPIView,
)
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_409_CONFLICT,
    HTTP_503_SERVICE_UNAVAILABLE,
)
from wca.serializers import WCAKeySerializer, WCAKeysSerializer

logger = logging.getLogger(__name__)

# Temporary storage until AWS-SM is integrated
storage: dict[str, list] = {'1': [{'key': 'key-1', 'description': 'desc-1'}]}


def is_wca_key_in_org(wca_key: str, org_id: str) -> bool:
    org_wca_keys = get_wca_keys_for_org_id(org_id)
    return len(list(filter(lambda wk: wk.get('key') == wca_key, org_wca_keys))) > 0


def get_wca_keys_for_org_id(org_id: str) -> list[any]:
    # This is temporary until we have the AWS-SM service
    return storage.get(org_id)


def add_wca_key_for_org_id(wca_key: any, org_id: str):
    # This is temporary until we have the AWS-SM service
    storage.get(org_id).append(wca_key)


def delete_wca_key_from_org_id(wca_key_pk: str, org_id: str):
    # This is temporary until we have the AWS-SM service
    org_wca_keys = get_wca_keys_for_org_id(org_id)
    wca_keys = list(filter(lambda wk: wk.get('key') == wca_key_pk, org_wca_keys))
    if len(wca_keys) > 0:
        wca_key = wca_keys[0]
        storage.get(org_id).remove(wca_key)


class WCAKeyListOrCreateView(RetrieveAPIView, CreateAPIView):
    from ai.api.permissions import AcceptedTermsPermission, IsAdministrator
    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsAdministrator,
        AcceptedTermsPermission,
    ]
    required_scopes = ['read']
    throttle_cache_key_suffix = '_wca'

    @extend_schema(
        responses={
            200: WCAKeysSerializer,
            401: OpenApiResponse(description='Unauthorized'),
            404: OpenApiResponse(description='Not found'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="List WCA keys for an Organisation",
    )
    def get(self, request, *args, **kwargs):
        logger.info("GET handler")

        org_id = kwargs.get("org_id")
        if org_id not in storage:
            return HttpResponseNotFound()

        try:
            wca_keys = get_wca_keys_for_org_id(org_id)
            serializer = WCAKeysSerializer(data={'keys': wca_keys})
            if not serializer.is_valid():
                logging.error(serializer.errors)
                return Response(serializer.errors, HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as exc:
            logger.error(f"Failed to search for WCA keys\nException:\n{exc}")
            return Response(
                {'message': "Unable to complete the request"}, status=HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response(serializer.data, status=HTTP_200_OK)

    @extend_schema(
        request=WCAKeySerializer,
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            409: OpenApiResponse(description='Conflict'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Create a WCA key for an Organisation",
    )
    def post(self, request, *args, **kwargs):
        logger.info("POST handler")

        org_id = kwargs.get("org_id")
        if org_id not in storage:
            return HttpResponseNotFound()

        serializer = WCAKeySerializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as exc:
            logger.error(f'Failed to validate request:\nException:\n{exc}')
            return HttpResponseBadRequest(serializer.errors, status=HTTP_503_SERVICE_UNAVAILABLE)

        wca_key = serializer.validated_data
        wca_key_str = wca_key.get('key')
        if is_wca_key_in_org(wca_key_str, org_id):
            message = f"Key '{wca_key_str}' for Organisation '{org_id}' already exists."
            logger.info(message)
            return Response(message, HTTP_409_CONFLICT)

        add_wca_key_for_org_id(wca_key, org_id)

        return Response(status=HTTP_204_NO_CONTENT)


class WCAKeyDeleteView(DestroyAPIView):
    from ai.api.permissions import AcceptedTermsPermission, IsAdministrator
    from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
    from rest_framework import permissions

    permission_classes = [
        permissions.IsAuthenticated,
        IsAuthenticatedOrTokenHasScope,
        IsAdministrator,
        AcceptedTermsPermission,
    ]
    required_scopes = ['write']
    throttle_cache_key_suffix = '_wca'

    @extend_schema(
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            429: OpenApiResponse(description='Request was throttled'),
            503: OpenApiResponse(description='Service Unavailable'),
        },
        summary="Delete a WCA key from an Organisation",
    )
    def delete(self, request, *args, **kwargs):
        logger.info("DELETE handler")

        org_id = kwargs.get("org_id")
        if org_id not in storage:
            return HttpResponseNotFound()

        wca_key = kwargs.get("wca_key")
        if wca_key is None:
            return HttpResponseBadRequest()

        if is_wca_key_in_org(wca_key, org_id):
            delete_wca_key_from_org_id(wca_key, org_id)
        else:
            return HttpResponseNotFound()

        return Response(status=HTTP_204_NO_CONTENT)
