import requests
from ai.api.aws.wca_secret_manager import Suffixes
from ai.api.model_client.wca_client import WcaInferenceFailure, WcaTokenFailure
from django.apps import apps
from django.conf import settings
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import ServiceUnavailable
from users.constants import FAUX_COMMERCIAL_USER_ORG_ID

ERROR_MESSAGE = "An error occurred"


class WcaTokenRequestException(ServiceUnavailable):
    """There was an error trying to get a WCA token."""


class WcaModelRequestException(ServiceUnavailable):
    """There was an error trying to invoke a WCA Model."""


class BaseLightspeedHealthCheck(BaseHealthCheckBackend):  # noqa
    def pretty_status(self):
        return str(super().pretty_status()) if self.errors else 'ok'


class ModelServerHealthCheck(BaseLightspeedHealthCheck):
    # If this is set to False, the status endpoints will respond with a 200
    # status code even if the check errors.
    critical_service = True

    def __init__(self):
        super().__init__()
        self.api_type = settings.ANSIBLE_AI_MODEL_MESH_API_TYPE
        if self.api_type == 'http':
            self.url = f'{settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL}/ping'
        elif self.api_type == 'grpc':
            self.url = (
                f'{settings.ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PROTOCOL}://'
                f'{settings.ANSIBLE_AI_MODEL_MESH_HOST}:'
                f'{settings.ANSIBLE_AI_MODEL_MESH_API_HEALTHCHECK_PORT}/oauth/healthz'
            )
        else:  # 'mock' & 'wca'
            self.url = None

    def check_status(self):
        try:
            if self.url:
                # As of today (2023-03-27) SSL Certificate Verification fails with
                # the gRPC model server in the Staging environment.  The verify
                # option in the following line is just TEMPORARY and will be removed
                # as soon as the certificate is replaced with a valid one.
                res = requests.get(self.url, verify=(self.api_type != 'grpc'))  # !!!!! TODO !!!!!
                if res.status_code != 200:
                    raise Exception()
            else:
                pass
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__  # Display name on the endpoint.


class AWSSecretManagerHealthCheck(BaseLightspeedHealthCheck):
    critical_service = True

    def check_status(self):
        try:
            apps.get_app_config("ai").get_wca_secret_manager().get_secret(
                FAUX_COMMERCIAL_USER_ORG_ID, Suffixes.API_KEY
            )
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__


class WCAHealthCheck(BaseLightspeedHealthCheck):
    critical_service = True

    def check_status(self):
        free_api_key = settings.ANSIBLE_WCA_FREE_API_KEY
        free_model_id = settings.ANSIBLE_WCA_FREE_MODEL_ID
        try:
            apps.get_app_config("ai").wca_client.infer_from_parameters(
                free_api_key,
                free_model_id,
                "",
                "- name: install ffmpeg on Red Hat Enterprise Linux",
            )
        except WcaTokenFailure as e:
            # If there's a Token failure we'll also not be able to execute Model inference.
            self.add_error(WcaTokenRequestException(ERROR_MESSAGE), e)
            self.add_error(WcaModelRequestException(ERROR_MESSAGE), e)
        except WcaInferenceFailure as e:
            self.add_error(WcaModelRequestException(ERROR_MESSAGE), e)

    def pretty_status(self):
        token_error = [item for item in self.errors if isinstance(item, WcaTokenRequestException)]
        model_error = [item for item in self.errors if isinstance(item, WcaModelRequestException)]
        return {
            "tokens": str(token_error[0]) if token_error else "ok",
            "models": str(model_error[0]) if model_error else "ok",
        }

    def identifier(self):
        return self.__class__.__name__


class AuthorizationHealthCheck(BaseLightspeedHealthCheck):
    critical_service = True

    def check_status(self):
        try:
            apps.get_app_config("ai").get_seat_checker().self_test()
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__
