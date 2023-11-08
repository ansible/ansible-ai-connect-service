import logging
import time

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes
from ai.api.model_client.exceptions import WcaTokenFailure
from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.serializers import WcaKeyRequestSerializer
from ai.api.utils.segment import send_segment_event
from ai.api.views import ServiceUnavailable
from ai.api.wca.utils import is_org_id_valid
from django.apps import apps
from drf_spectacular.utils import OpenApiResponse, extend_schema
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)
from users.signals import user_set_wca_api_key

logger = logging.getLogger(__name__)

PERMISSION_CLASSES = [
    IsAuthenticated,
    IsAuthenticatedOrTokenHasScope,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    AcceptedTermsPermission,
]


class WCAApiKeyView(RetrieveAPIView, CreateAPIView):
    required_scopes = ['read', 'write']
    throttle_cache_key_suffix = '_wca_api_key'
    permission_classes = PERMISSION_CLASSES

    @extend_schema(
        responses={
            200: OpenApiResponse(description='OK'),
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            500: OpenApiResponse(description='Internal service error'),
        },
        summary="Get WCA key for an Organisation",
        operation_id="wca_api_key_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("WCA API Key:: GET handler")

        exception = None
        start_time = time.time()
        try:
            # An OrgId must be present
            # See https://issues.redhat.com/browse/AAP-16009
            org_id = request._request.user.organization_id
            if not is_org_id_valid(org_id):
                return Response(status=HTTP_400_BAD_REQUEST)

            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            wca_key = secret_manager.get_secret(org_id, Suffixes.API_KEY)
            if wca_key is None:
                return Response(status=HTTP_200_OK)
            # Once written the Key value is never returned to the User,
            # instead we return when the secret was last updated.
            return Response(status=HTTP_200_OK, data={'last_update': wca_key['CreatedDate']})

        except WcaSecretManagerError as e:
            exception = e
            logger.exception(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
            }
            send_segment_event(event, "modelApiKeyGet", request.user)

    @extend_schema(
        request=WcaKeyRequestSerializer,
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            500: OpenApiResponse(description='Internal service error'),
        },
        summary="Set the WCA key for an Organisation",
        operation_id="wca_api_key_set",
    )
    def post(self, request, *args, **kwargs):
        logger.debug("WCA API Key:: POST handler")

        org_id = None
        exception = None
        start_time = time.time()
        try:
            # An OrgId must be present
            # See https://issues.redhat.com/browse/AAP-16009
            org_id = request._request.user.organization_id
            if not is_org_id_valid(org_id):
                return Response(status=HTTP_400_BAD_REQUEST)

            # Extract API Key from request
            key_serializer = WcaKeyRequestSerializer(data=request.data)
            key_serializer.is_valid(raise_exception=True)
            wca_key = key_serializer.validated_data['key']

            # Validate API Key
            model_mesh_client = apps.get_app_config("ai").wca_client
            model_mesh_client.get_token(wca_key)

            # Store the validated API Key
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            secret_name = secret_manager.save_secret(org_id, Suffixes.API_KEY, wca_key)

            # Audit trail/logging
            user_set_wca_api_key.send(
                WCAApiKeyView.__class__, user=request._request.user, org_id=org_id, api_key=wca_key
            )
            logger.info(f"Stored secret '{secret_name}' for org_id '{org_id}'")

        except ValidationError as e:
            exception = e
            logger.info(e, exc_info=True)
            return Response(status=HTTP_400_BAD_REQUEST)

        except WcaTokenFailure as e:
            exception = e
            logger.info(
                f"An error occurred trying to retrieve a WCA Token for Organisation '{org_id}'.",
                exc_info=True,
            )
            return Response(status=HTTP_400_BAD_REQUEST)

        except WcaSecretManagerError as e:
            exception = e
            logger.exception(e)
            raise ServiceUnavailable

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
            }
            send_segment_event(event, "modelApiKeySet", request.user)

        return Response(status=HTTP_204_NO_CONTENT)


class WCAApiKeyValidatorView(RetrieveAPIView):
    required_scopes = ['read']
    throttle_cache_key_suffix = '_wca_api_key_validator'
    permission_classes = PERMISSION_CLASSES

    @extend_schema(
        responses={
            200: OpenApiResponse(description='OK'),
            400: OpenApiResponse(description='Bad Request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            500: OpenApiResponse(description='Internal service error'),
        },
        summary="Validate WCA key for an Organisation",
        operation_id="wca_api_key_validator_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("WCA API Key Validator:: GET handler")

        org_id = None
        exception = None
        start_time = time.time()
        try:
            # An OrgId must be present
            # See https://issues.redhat.com/browse/AAP-16009
            org_id = request._request.user.organization_id
            if not is_org_id_valid(org_id):
                return Response(status=HTTP_400_BAD_REQUEST)

            # Validate API Key
            model_mesh_client = apps.get_app_config("ai").wca_client
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            api_key = secret_manager.get_secret(org_id, Suffixes.API_KEY)
            token = model_mesh_client.get_token(api_key['SecretString'])
            if token is None:
                return Response(status=HTTP_400_BAD_REQUEST)

        except WcaSecretManagerError as e:
            exception = e
            logger.exception(e)
            raise ServiceUnavailable

        except WcaTokenFailure as e:
            exception = e
            logger.info(
                f"An error occurred trying to retrieve a WCA Token for Organisation '{org_id}'.",
                exc_info=True,
            )
            return Response(status=HTTP_400_BAD_REQUEST)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
            }
            send_segment_event(event, "modelApiKeyValidate", request.user)

        return Response(status=HTTP_200_OK)
