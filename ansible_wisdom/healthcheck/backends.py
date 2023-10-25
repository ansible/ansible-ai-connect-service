import base64
import io

import ai.search
import numpy as np
import requests
from ai.api.aws.wca_secret_manager import Suffixes
from ai.api.model_client.wca_client import WcaInferenceFailure
from django.apps import apps
from django.conf import settings
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import ServiceUnavailable
from users.constants import FAUX_COMMERCIAL_USER_ORG_ID

ERROR_MESSAGE = "An error occurred"

PRE_DEFINED_SEARCH_STRING = 'aaa'

# See the TestSearchWithPreEncoded class in test_backends.py on how these lines were generated.
PRE_ENCODED_QUERY = '''\
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
bT47ORm8wK89Pamqubw='''


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
        except WcaInferenceFailure as e:
            self.add_error(WcaModelRequestException(ERROR_MESSAGE), e)
        except Exception as e:
            # For any other failure we assume the whole WCA service is unavailable.
            self.add_error(WcaTokenRequestException(ERROR_MESSAGE), e)
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


class AttributionCheck(BaseLightspeedHealthCheck):
    critical_service = False

    def __init__(self):
        decoded = base64.b64decode(PRE_ENCODED_QUERY)
        f = io.BytesIO(decoded)
        self.pre_encoded_query = np.load(f)

    def check_status(self):
        try:
            attributions = ai.search.search(
                PRE_DEFINED_SEARCH_STRING, index=None, pre_encoded=self.pre_encoded_query
            )["attributions"]
            assert len(attributions) > 0, "No attribution found"
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__
