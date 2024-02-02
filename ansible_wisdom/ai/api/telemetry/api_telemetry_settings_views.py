import logging
import time

from ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.serializers import TelemetrySettingsRequestSerializer
from ai.api.utils.segment import send_segment_event
from ai.api.views import InternalServerError, ServiceUnavailable
from drf_spectacular.utils import OpenApiResponse, extend_schema
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_200_OK, HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST
from users.signals import user_set_telemetry_settings

logger = logging.getLogger(__name__)

PERMISSION_CLASSES = [
    IsAuthenticated,
    IsAuthenticatedOrTokenHasScope,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
]


class TelemetrySettingsView(RetrieveAPIView, CreateAPIView):
    required_scopes = ['read', 'write']
    throttle_cache_key_suffix = '_telemetry_settings'
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
        summary="Get the telemetry settings for an Organisation",
        operation_id="telemetry_settings_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("Telemetry settings:: GET handler")

        exception = None
        organization = None
        start_time = time.time()
        try:
            # An OrgId must be present
            # See https://issues.redhat.com/browse/AAP-16009
            organization = request._request.user.organization
            if not organization:
                return Response(status=HTTP_400_BAD_REQUEST)

            if not organization.is_schema_2_telemetry_enabled:
                raise ServiceUnavailable()

            return Response(status=HTTP_200_OK, data={'optOut': organization.telemetry_opt_out})

        except ServiceUnavailable:
            raise

        except Exception as e:
            exception = e
            logger.exception(e)
            raise InternalServerError(e)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
                "opt_out": None if organization is None else organization.telemetry_opt_out,
            }
            send_segment_event(event, "telemetrySettingsGet", request.user)

    @extend_schema(
        request=TelemetrySettingsRequestSerializer,
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            500: OpenApiResponse(description='Internal service error'),
        },
        summary="Set the Telemetry settings for an Organisation",
        operation_id="telemetry_settings_set",
    )
    def post(self, request, *args, **kwargs):
        logger.debug("Telemetry settings:: POST handler")

        exception = None
        organization = None
        start_time = time.time()
        try:
            # An OrgId must be present
            # See https://issues.redhat.com/browse/AAP-16009
            organization = request._request.user.organization
            if not organization:
                return Response(status=HTTP_400_BAD_REQUEST)

            if not organization.is_schema_2_telemetry_enabled:
                raise ServiceUnavailable()

            # Extract Telemetry settings from request
            telemetry_settings_serializer = TelemetrySettingsRequestSerializer(data=request.data)
            telemetry_settings_serializer.is_valid(raise_exception=True)
            telemetry_settings = telemetry_settings_serializer.validated_data

            # Store the Opt-Out setting
            organization.telemetry_opt_out = telemetry_settings["optOut"]
            organization.save()

            # Audit trail/logging
            user_set_telemetry_settings.send(
                TelemetrySettingsView.__class__,
                user=request._request.user,
                org_id=organization.id,
                settings=telemetry_settings,
            )
            logger.info(f"Stored telemetry settings for org_id '{organization.id}'")

        except ValidationError as e:
            exception = e
            logger.info(e, exc_info=True)
            return Response(status=HTTP_400_BAD_REQUEST)

        except ServiceUnavailable:
            raise

        except Exception as e:
            exception = e
            logger.exception(e)
            raise InternalServerError(cause=e)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
                "opt_out": None if organization is None else organization.telemetry_opt_out,
            }
            send_segment_event(event, "telemetrySettingsSet", request.user)

        return Response(status=HTTP_204_NO_CONTENT)
