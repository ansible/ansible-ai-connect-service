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

from drf_spectacular.utils import OpenApiResponse, extend_schema

from ansible_ai_connect.ai.api.base import saas
from ansible_ai_connect.ai.api.telemetry.api_telemetry_settings_views import (
    TelemetrySettingsView as _BaseTelemetrySettingsView,
)

from . import serializers as serializers


class TelemetrySettingsView(saas.APIViewSaasMixin, _BaseTelemetrySettingsView):

    @extend_schema(
        responses={
            200: OpenApiResponse(description="OK"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
            501: OpenApiResponse(description="Not implemented"),
        },
        summary="Get the telemetry settings for an Organisation",
        operation_id="telemetry_settings_get",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=serializers.TelemetrySettingsRequestSerializer,
        responses={
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
            501: OpenApiResponse(description="Not implemented"),
        },
        summary="Set the Telemetry settings for an Organisation",
        operation_id="telemetry_settings_set",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


__all__ = ["TelemetrySettingsView"]
