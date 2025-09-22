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

import logging
import time
from typing import cast

from django.apps import apps
from drf_spectacular.utils import OpenApiResponse, extend_schema
from oauth2_provider.contrib.rest_framework import IsAuthenticatedOrTokenHasScope
from rest_framework.exceptions import ValidationError
from rest_framework.generics import CreateAPIView, DestroyAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_500_INTERNAL_SERVER_ERROR,
)

from ansible_ai_connect.ai.api.aws.exceptions import WcaSecretManagerError
from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes
from ansible_ai_connect.ai.api.model_pipelines.exceptions import (
    WcaTokenFailureApiKeyError,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import MetaData
from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import WCASaaSMetaData
from ansible_ai_connect.ai.api.permissions import (
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCASaaSModelPipeline,
)
from ansible_ai_connect.ai.api.serializers import WcaKeyRequestSerializer
from ansible_ai_connect.ai.api.utils.segment import send_segment_event
from ansible_ai_connect.ai.api.views import ServiceUnavailable
from ansible_ai_connect.organizations.models import ExternalOrganization
from ansible_ai_connect.users.signals import (
    user_delete_wca_api_key,
    user_delete_wca_model_id,
    user_set_wca_api_key,
)

logger = logging.getLogger(__name__)

PERMISSION_CLASSES = [
    IsAuthenticated,
    IsAuthenticatedOrTokenHasScope,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    IsWCASaaSModelPipeline,
]


class WCAApiKeyView(RetrieveAPIView, CreateAPIView, DestroyAPIView):
    required_scopes = ["read", "write", "delete"]
    throttle_cache_key_suffix = "_wca_api_key"
    throttle_cache_multiplier = 2.0
    permission_classes = PERMISSION_CLASSES

    @extend_schema(
        responses={
            200: OpenApiResponse(description="OK"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
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
            organization = request._request.user.organization
            if not organization:
                return Response(status=HTTP_400_BAD_REQUEST)

            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            wca_key = secret_manager.get_secret(organization.id, Suffixes.API_KEY)
            if wca_key is None:
                return Response(status=HTTP_200_OK)
            # Once written the Key value is never returned to the User,
            # instead we return when the secret was last updated.
            return Response(status=HTTP_200_OK, data={"last_update": wca_key["CreatedDate"]})

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
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
        },
        summary="Set the WCA key for an Organisation",
        operation_id="wca_api_key_set",
    )
    def post(self, request, *args, **kwargs):
        logger.debug("WCA API Key:: POST handler")

        exception = None
        start_time = time.time()

        # An OrgId must be present
        # See https://issues.redhat.com/browse/AAP-16009
        if not request._request.user.organization:
            return Response(status=HTTP_400_BAD_REQUEST)
        organization: ExternalOrganization = request._request.user.organization

        try:
            # Extract API Key from request
            key_serializer = WcaKeyRequestSerializer(data=request.data)
            key_serializer.is_valid(raise_exception=True)
            wca_key = key_serializer.validated_data[
                "key"
            ]  # pyright: ignore [reportIndexIssue, reportOptionalSubscript]

            # Validate API Key
            _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
            model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
            model_meta_data.get_token(wca_key)

            # Store the validated API Key
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            secret_name = secret_manager.save_secret(organization.id, Suffixes.API_KEY, wca_key)

            # Audit trail/logging
            user_set_wca_api_key.send(
                WCAApiKeyView.__class__,
                user=request._request.user,
                org_id=organization.id,
                api_key=wca_key,
            )
            logger.info(f"Stored secret '{secret_name}' for org_id '{organization.id}'")

        except ValidationError as e:
            exception = e
            logger.info(e, exc_info=True)
            return Response(status=HTTP_400_BAD_REQUEST)

        except WcaTokenFailureApiKeyError as e:
            exception = e
            logger.info(
                f"An error occurred trying to retrieve a WCA Token for "
                f"Organisation '{organization.id}'.",
                exc_info=True,
            )
            return Response(status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            exception = e
            logger.exception(e)
            raise ServiceUnavailable(cause=e)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
            }
            send_segment_event(event, "modelApiKeySet", request.user)

        return Response(status=HTTP_204_NO_CONTENT)

    @extend_schema(
        responses={
            204: OpenApiResponse(description="Empty response"),
            400: OpenApiResponse(description="Bad request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
        },
        summary="DELETE WCA key for an Organization",
        operation_id="wca_api_key_delete",
    )
    def delete(self, request, *args, **kwargs):
        logger.debug("WCA API Key:: DELETE handler")

        organization = None
        exception = None
        start_time = time.time()
        try:
            organization = request._request.user.organization
            if not organization:
                return Response(status=HTTP_400_BAD_REQUEST)

            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()

            wca_key = secret_manager.get_secret(organization.id, Suffixes.API_KEY)
            if wca_key is None:
                return Response(status=HTTP_400_BAD_REQUEST)

            secret_manager.delete_secret(organization.id, Suffixes.API_KEY)

            # Audit trail/logging
            user_delete_wca_api_key.send(
                WCAApiKeyView.__class__,
                user=request._request.user,
                org_id=organization.id,
                api_key=wca_key,
            )
            logger.info(f"Deleted API key secret for org_id '{organization.id}'")

            # If model ID exists, delete it as well.
            model_id = secret_manager.get_secret(organization.id, Suffixes.MODEL_ID)
            if model_id is not None:
                secret_manager.delete_secret(organization.id, Suffixes.MODEL_ID)

                # Audit trail/logging
                user_delete_wca_model_id.send(
                    WCAApiKeyView.__class__,
                    user=request._request.user,
                    org_id=organization.id,
                    model_id=model_id,
                )
                logger.info(f"Deleted model ID secret for org_id '{organization.id}'")

        except Exception as e:
            exception = e
            logger.exception(e)
            raise ServiceUnavailable(cause=e)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
            }
            send_segment_event(event, "modelApiKeyDelete", request.user)

        return Response(status=HTTP_204_NO_CONTENT)


class WCAApiKeyValidatorView(RetrieveAPIView):
    required_scopes = ["read"]
    throttle_cache_key_suffix = "_wca_api_key_validator"
    permission_classes = PERMISSION_CLASSES

    @extend_schema(
        responses={
            200: OpenApiResponse(description="OK"),
            400: OpenApiResponse(description="Bad Request"),
            401: OpenApiResponse(description="Unauthorized"),
            403: OpenApiResponse(description="Forbidden"),
            429: OpenApiResponse(description="Request was throttled"),
            500: OpenApiResponse(description="Internal service error"),
        },
        summary="Validate WCA key for an Organisation",
        operation_id="wca_api_key_validator_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("WCA API Key Validator:: GET handler")
        exception = None
        start_time = time.time()

        # An OrgId must be present
        # See https://issues.redhat.com/browse/AAP-16009
        if not request._request.user.organization:
            return Response(status=HTTP_400_BAD_REQUEST)
        organization: ExternalOrganization = request._request.user.organization
        try:
            # Validate API Key
            _md = apps.get_app_config("ai").get_model_pipeline(MetaData)
            model_meta_data: WCASaaSMetaData = cast(WCASaaSMetaData, _md)
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            api_key = secret_manager.get_secret(organization.id, Suffixes.API_KEY)
            if api_key is None:
                return Response(status=HTTP_400_BAD_REQUEST)
            token = model_meta_data.get_token(api_key["SecretString"])
            if token is None:
                return Response(status=HTTP_400_BAD_REQUEST)

        except WcaTokenFailureApiKeyError as e:
            exception = e
            logger.info(
                f"An error occurred trying to retrieve a WCA Token for "
                f"Organisation '{organization.id}'.",
                exc_info=True,
            )
            return Response(status=HTTP_400_BAD_REQUEST)

        except Exception as e:
            exception = e
            logger.exception(e)
            raise ServiceUnavailable(cause=e)

        finally:
            duration = round((time.time() - start_time) * 1000, 2)
            event = {
                "duration": duration,
                "exception": exception is not None,
                "problem": None if exception is None else exception.__class__.__name__,
            }
            send_segment_event(event, "modelApiKeyValidate", request.user)

        return Response(status=HTTP_200_OK)
