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

import requests
from django.apps import apps
from django.conf import settings
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import ServiceUnavailable

import ansible_ai_connect.ai.search
from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes
from ansible_ai_connect.ai.api.model_client.wca_client import WcaInferenceFailure
from ansible_ai_connect.users.constants import FAUX_COMMERCIAL_USER_ORG_ID

ERROR_MESSAGE = "An error occurred"


class WcaTokenRequestException(ServiceUnavailable):
    """There was an error trying to get a WCA token."""


class WcaModelRequestException(ServiceUnavailable):
    """There was an error trying to invoke a WCA Model."""


class BaseLightspeedHealthCheck(BaseHealthCheckBackend):  # noqa
    enabled = True

    def pretty_status(self):
        if not self.enabled:
            return "disabled"
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
        self.enabled = settings.ENABLE_HEALTHCHECK_MODEL_MESH
        if not self.enabled:
            return

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
        self.enabled = settings.ENABLE_HEALTHCHECK_SECRET_MANAGER
        if not self.enabled:
            return

        try:
            apps.get_app_config("ai").get_wca_secret_manager().get_secret(
                FAUX_COMMERCIAL_USER_ORG_ID, Suffixes.API_KEY
            )
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__


class WCAHealthCheckBase(BaseLightspeedHealthCheck):
    critical_service = True
    enabled = False

    def check_status(self):
        if not self.is_enabled():
            return

        try:
            self.get_wca_client().infer_from_parameters(
                self.get_wca_api_key(),
                self.get_wca_model_id(),
                "",
                "- name: install ffmpeg on Red Hat Enterprise Linux",
            )
        except WcaInferenceFailure as e:
            self.add_error(WcaModelRequestException(ERROR_MESSAGE), e)
        except Exception as e:
            # For any other failure we assume the whole WCA service is unavailable.
            self.add_error(WcaTokenRequestException(ERROR_MESSAGE), e)
            self.add_error(WcaModelRequestException(ERROR_MESSAGE), e)

    def is_enabled(self) -> bool:
        return self.enabled

    def get_wca_api_key(self):
        return None

    def get_wca_model_id(self):
        return None

    def get_wca_client(self):
        return None

    def pretty_status(self):
        if not self.is_enabled():
            return {
                "tokens": "disabled",
                "models": "disabled",
            }

        token_error = [item for item in self.errors if isinstance(item, WcaTokenRequestException)]
        model_error = [item for item in self.errors if isinstance(item, WcaModelRequestException)]
        return {
            "tokens": str(token_error[0]) if token_error else "ok",
            "models": str(model_error[0]) if model_error else "ok",
        }

    def identifier(self):
        return self.__class__.__name__


class WCAHealthCheck(WCAHealthCheckBase):
    def is_enabled(self) -> bool:
        self.enabled = settings.ENABLE_HEALTHCHECK_WCA
        return self.enabled

    def get_wca_client(self):
        return apps.get_app_config("ai").get_wca_client()

    def get_wca_api_key(self):
        return settings.ANSIBLE_WCA_HEALTHCHECK_API_KEY

    def get_wca_model_id(self):
        return settings.ANSIBLE_WCA_HEALTHCHECK_MODEL_ID


class WCAOnPremHealthCheck(WCAHealthCheckBase):
    def is_enabled(self) -> bool:
        self.enabled = settings.ENABLE_HEALTHCHECK_WCA_ONPREM
        return self.enabled

    def get_wca_client(self):
        return apps.get_app_config("ai").get_wca_onprem_client()

    def get_wca_api_key(self):
        return settings.ANSIBLE_WCA_ONPREM_HEALTHCHECK_API_KEY

    def get_wca_model_id(self):
        return settings.ANSIBLE_WCA_ONPREM_HEALTHCHECK_MODEL_ID


class AuthorizationHealthCheck(BaseLightspeedHealthCheck):
    critical_service = True

    def check_status(self):
        self.enabled = settings.ENABLE_HEALTHCHECK_AUTHORIZATION
        if not self.enabled:
            return

        try:
            apps.get_app_config("ai").get_seat_checker().self_test()
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__


class AttributionCheck(BaseLightspeedHealthCheck):
    critical_service = False

    def check_status(self):
        self.enabled = settings.ENABLE_HEALTHCHECK_ATTRIBUTION
        if not self.enabled:
            return

        try:
            attributions = ansible_ai_connect.ai.search.search("aaa")["attributions"]
            assert len(attributions) > 0, "No attribution found"
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__
