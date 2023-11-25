import logging
import time

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes
from ai.api.model_client.exceptions import (
    WcaBadRequest,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
    WcaTokenFailure,
)
from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.serializers import WcaModelIdRequestSerializer
from ai.api.utils.segment import send_segment_event
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
from users.signals import user_set_wca_model_id

from ..views import ServiceUnavailable, WcaBadRequestException, WcaKeyNotFoundException

UNKNOWN_MODEL_ID = "Unknown"

logger = logging.getLogger(__name__)

PERMISSION_CLASSES = [
    IsAuthenticated,
    IsAuthenticatedOrTokenHasScope,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    AcceptedTermsPermission,
]


class WCAModelIdView(RetrieveAPIView, CreateAPIView):
    required_scopes = ['read', 'write']
    throttle_cache_key_suffix = '_wca_model_id'
    permission_classes = PERMISSION_CLASSES

    @extend_schema(
        responses={
            200: OpenApiResponse(description='OK'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            500: OpenApiResponse(description='Internal service error'),
        },
        summary="Get WCA Model Id for an Organisation",
        operation_id="wca_model_id_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("WCA Model Id:: GET handler")

        exception = None
        start_time = time.time()
        model_id = UNKNOWN_MODEL_ID
        try:
            # An OrgId must be present
            # See https://issues.redhat.com/browse/AAP-16009
            org_id = request._request.user.organization_id
            if not is_org_id_valid(org_id):
                return Response(status=HTTP_400_BAD_REQUEST)

            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            response = secret_manager.get_secret(org_id, Suffixes.MODEL_ID)
            if response is None:
                return Response(status=HTTP_200_OK)

            model_id = response['SecretString']
            return Response(
                status=HTTP_200_OK,
                data={'model_id': model_id, 'last_update': response['CreatedDate']},
            )

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
                "modelName": model_id,
            }
            send_segment_event(event, "modelIdGet", request.user)

    @extend_schema(
        request=WcaModelIdRequestSerializer,
        responses={
            204: OpenApiResponse(description='Empty response'),
            400: OpenApiResponse(description='Bad request'),
            401: OpenApiResponse(description='Unauthorized'),
            403: OpenApiResponse(description='Forbidden'),
            429: OpenApiResponse(description='Request was throttled'),
            500: OpenApiResponse(description='Internal service error'),
        },
        summary="Set the Model Id to be used for an Organisation",
        operation_id="wca_model_id_set",
    )
    def post(self, request, *args, **kwargs):
        logger.debug("WCA Model Id:: POST handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()

        def get_api_key(org_id):
            api_key = secret_manager.get_secret(org_id, Suffixes.API_KEY)
            return get_secret_value(api_key)

        def get_model_id(*_):
            model_id_serializer = WcaModelIdRequestSerializer(data=request.data)
            model_id_serializer.is_valid(raise_exception=True)
            return model_id_serializer.validated_data['model_id']

        def on_success(org_id, model_id):
            secret_name = secret_manager.save_secret(org_id, Suffixes.MODEL_ID, model_id)

            # Audit trail/logging
            user_set_wca_model_id.send(
                WCAModelIdView.__class__,
                user=request._request.user,
                org_id=org_id,
                model_id=model_id,
            )

            logger.info(f"Stored Secret '{secret_name}' for org_id '{org_id}'")
            return Response(status=HTTP_204_NO_CONTENT)

        return do_validated_operation(request, get_api_key, get_model_id, on_success, "modelIdSet")


class WCAModelIdValidatorView(RetrieveAPIView):
    required_scopes = ['read']
    throttle_cache_key_suffix = '_wca_model_id_validator'
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
        summary="Validate WCA Model Id for an Organisation",
        operation_id="wca_model_id_validator_get",
    )
    def get(self, request, *args, **kwargs):
        logger.debug("WCA Model Id Validator:: GET handler")
        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()

        def get_api_key(org_id):
            api_key = secret_manager.get_secret(org_id, Suffixes.API_KEY)
            return get_secret_value(api_key)

        def get_model_id(org_id):
            model_id = secret_manager.get_secret(org_id, Suffixes.MODEL_ID)
            return get_secret_value(model_id)

        def on_success(*_):
            return Response(status=HTTP_200_OK)

        return do_validated_operation(
            request, get_api_key, get_model_id, on_success, "modelIdValidate"
        )


def validate(api_key, model_id):
    if api_key is None:
        logger.error('No API key specified.')
        raise WcaKeyNotFound
    if model_id is None:
        logger.error('No Model Id key specified.')
        raise WcaModelIdNotFound

    # If no validation issues, let's infer (given an api_key and model_id)
    # and expect some prediction (result), otherwise an exception will be raised.
    model_mesh_client = apps.get_app_config("ai").get_wca_client()
    model_mesh_client.infer_from_parameters(
        api_key, model_id, "", "---\n- hosts: all\n  tasks:\n  - name: install ssh\n"
    )


def do_validated_operation(request, api_key_provider, model_id_provider, on_success, event_name):
    exception = None
    start_time = time.time()
    model_id = UNKNOWN_MODEL_ID
    try:
        # An OrgId must be present
        # See https://issues.redhat.com/browse/AAP-16009
        org_id = request._request.user.organization_id
        if not is_org_id_valid(org_id):
            return Response(status=HTTP_400_BAD_REQUEST)

        api_key = api_key_provider(org_id)
        model_id = model_id_provider(org_id)

        validate(api_key, model_id)

        return on_success(org_id, model_id)

    except (WcaInvalidModelId, WcaModelIdNotFound, WcaTokenFailure) as e:
        exception = e
        logger.info(e, exc_info=True)
        return Response(status=HTTP_400_BAD_REQUEST)

    except ValidationError as e:
        # Since a ValidationError contains the request data that might contain PII,
        # log the class name only here.
        exception = e
        logger.info(e.__class__.__name__)
        return Response(status=HTTP_400_BAD_REQUEST)

    except WcaKeyNotFound as e:
        exception = e
        logger.info(e, exc_info=True)
        raise WcaKeyNotFoundException(cause=e)

    except WcaBadRequest as e:
        exception = e
        logger.info(e, exc_info=True)
        raise WcaBadRequestException(cause=e)

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
            "modelName": model_id,
        }
        send_segment_event(event, event_name, request.user)


def get_secret_value(secret):
    if secret is None:
        return None
    return str(secret['SecretString']) if secret['SecretString'] else None
