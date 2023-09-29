import logging

from ai.api.aws.exceptions import WcaSecretManagerError
from ai.api.aws.wca_secret_manager import Suffixes
from ai.api.permissions import (
    AcceptedTermsPermission,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
)
from ai.api.serializers import WcaModelIdRequestSerializer
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

from ..model_client.wca_client import (
    WcaBadRequest,
    WcaInvalidModelId,
    WcaKeyNotFound,
    WcaModelIdNotFound,
)
from ..views import ServiceUnavailable, WcaBadRequestException, WcaKeyNotFoundException

logger = logging.getLogger(__name__)

PERMISSION_CLASSES = [
    IsAuthenticated,
    IsAuthenticatedOrTokenHasScope,
    IsOrganisationAdministrator,
    IsOrganisationLightspeedSubscriber,
    AcceptedTermsPermission,
]


def validate(api_key, model_id):
    model_mesh_client = apps.get_app_config("ai").wca_client
    model_mesh_client.infer_from_parameters(
        api_key, model_id, "", "---\n- hosts: all\n  tasks:\n  - name: install ssh\n"
    )


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

        # An OrgId must be present
        # See https://issues.redhat.com/browse/AAP-16009
        org_id = request._request.user.organization_id
        if not is_org_id_valid(org_id):
            return Response(status=HTTP_400_BAD_REQUEST)

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        try:
            response = secret_manager.get_secret(org_id, Suffixes.MODEL_ID)
            if response is None:
                return Response(status=HTTP_200_OK)
            return Response(
                status=HTTP_200_OK,
                data={'model_id': response['SecretString'], 'last_update': response['CreatedDate']},
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
            500: OpenApiResponse(description='Internal service error'),
        },
        summary="Set the Model Id to be used for an Organisation",
        operation_id="wca_model_id_set",
    )
    def post(self, request, *args, **kwargs):
        logger.debug("WCA Model Id:: POST handler")

        # An OrgId must be present
        # See https://issues.redhat.com/browse/AAP-16009
        org_id = request._request.user.organization_id
        if not is_org_id_valid(org_id):
            return Response(status=HTTP_400_BAD_REQUEST)

        secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
        model_id_serializer = WcaModelIdRequestSerializer(data=request.data)
        try:
            model_id_serializer.is_valid(raise_exception=True)
            model_id = model_id_serializer.validated_data['model_id']
            api_key = secret_manager.get_secret(org_id, Suffixes.API_KEY)
            validate(api_key['SecretString'], model_id)
            secret_name = secret_manager.save_secret(org_id, Suffixes.MODEL_ID, model_id)
            logger.info(f"Stored Secret '${secret_name}' for org_id '{org_id}'")
        except WcaSecretManagerError as e:
            logger.error(e)
            return Response(status=HTTP_500_INTERNAL_SERVER_ERROR)
        except (WcaInvalidModelId, WcaModelIdNotFound, ValidationError) as e:
            logger.error(e)
            return Response(status=HTTP_400_BAD_REQUEST)

        return Response(status=HTTP_204_NO_CONTENT)


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

        # An OrgId must be present
        # See https://issues.redhat.com/browse/AAP-16009
        org_id = request._request.user.organization_id
        if not is_org_id_valid(org_id):
            return Response(status=HTTP_400_BAD_REQUEST)

        try:
            secret_manager = apps.get_app_config("ai").get_wca_secret_manager()
            api_key = secret_manager.get_secret(org_id, Suffixes.API_KEY)
            model_id = secret_manager.get_secret(org_id, Suffixes.MODEL_ID)
            validate(
                api_key['SecretString'],
                str(model_id['SecretString']) if model_id['SecretString'] else None,
            )
        except (WcaInvalidModelId, WcaModelIdNotFound, ValidationError) as e:
            logger.error(e)
            return Response(status=HTTP_400_BAD_REQUEST)
        except WcaKeyNotFound as e:
            logger.error(e)
            raise WcaKeyNotFoundException(cause=e)
        except WcaBadRequest as e:
            logger.error(e)
            raise WcaBadRequestException(cause=e)
        except Exception as e:
            logger.error(e)
            raise ServiceUnavailable(cause=e)
        return Response(status=HTTP_200_OK)
