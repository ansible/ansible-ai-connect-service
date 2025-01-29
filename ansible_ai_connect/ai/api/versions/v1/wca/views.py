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
from ansible_ai_connect.ai.api.wca.api_key_views import (
    WCAApiKeyValidatorView as _BaseWCAApiKeyValidatorView,
)
from ansible_ai_connect.ai.api.wca.api_key_views import (
    WCAApiKeyView as _BaseWCAApiKeyView,
)
from ansible_ai_connect.ai.api.wca.model_id_views import (
    WCAModelIdValidatorView as _BaseWCAModelIdValidatorView,
)
from ansible_ai_connect.ai.api.wca.model_id_views import (
    WCAModelIdView as _BaseWCAModelIdView,
)

from . import serializers


class WCAApiKeyView(saas.APIViewSaasMixin, _BaseWCAApiKeyView):

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
        summary="Get WCA key for an Organisation",
        operation_id="wca_api_key_get",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=serializers.WcaKeyRequestSerializer,
        responses={
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
            501: OpenApiResponse(description="Not implemented"),
        },
        summary="Set the WCA key for an Organisation",
        operation_id="wca_api_key_set",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
            501: OpenApiResponse(description="Not implemented"),
        },
        summary="DELETE WCA key for an Organization",
        operation_id="wca_api_key_delete",
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class WCAApiKeyValidatorView(saas.APIViewSaasMixin, _BaseWCAApiKeyValidatorView):

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
        summary="Validate WCA key for an Organisation",
        operation_id="wca_api_key_validator_get",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class WCAModelIdView(saas.APIViewSaasMixin, _BaseWCAModelIdView):

    @extend_schema(
        responses={
            200: OpenApiResponse(description="OK"),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
            501: OpenApiResponse(description="Not implemented"),
        },
        summary="Get WCA Model Id for an Organisation",
        operation_id="wca_model_id_get",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=serializers.WcaModelIdRequestSerializer,
        responses={
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
            501: OpenApiResponse(description="Not implemented"),
        },
        summary="Set the Model Id to be used for an Organisation",
        operation_id="wca_model_id_set",
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class WCAModelIdValidatorView(saas.APIViewSaasMixin, _BaseWCAModelIdValidatorView):

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
        summary="Validate WCA Model Id for an Organisation",
        operation_id="wca_model_id_validator_get",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


__all__ = [
    "WCAApiKeyValidatorView",
    "WCAApiKeyView",
    "WCAModelIdValidatorView",
    "WCAModelIdView",
]
