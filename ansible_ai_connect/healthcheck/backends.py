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
from typing import Optional, Type

from django.apps import apps
from django.conf import settings
from health_check.backends import BaseHealthCheckBackend
from health_check.exceptions import HealthCheckException, ServiceUnavailable

from ansible_ai_connect.ai.api.aws.wca_secret_manager import Suffixes
from ansible_ai_connect.ai.api.model_pipelines.types import PIPELINE_TYPE

ERROR_MESSAGE = "An error occurred"
MODEL_MESH_HEALTH_CHECK_MODELS = "models"
MODEL_MESH_HEALTH_CHECK_PROVIDER = "provider"
MODEL_MESH_HEALTH_CHECK_INDEX = "index"


class HealthCheckSummaryException:
    exception: HealthCheckException
    cause: Exception

    def __init__(self, exception: HealthCheckException, cause: Exception | None = None) -> None:
        self.exception = exception
        self.cause = cause


class HealthCheckSummary:

    items: dict[str, HealthCheckSummaryException | str]

    def __init__(self, initial_items: dict[str, HealthCheckSummaryException | str]) -> None:
        self.items = initial_items

    def add_exception(self, key: str, exception: HealthCheckSummaryException):
        self.items.update({key: exception})

    def add_message(self, key: str, message: str):
        self.items.update({key: message})


class BaseLightspeedHealthCheck(BaseHealthCheckBackend):  # noqa
    enabled = True

    summary: HealthCheckSummary = HealthCheckSummary({})

    def pretty_status(self):
        if not self.enabled:
            return "disabled"
        if len(self.errors) == 0 and len(self.summary.items) == 0:
            return "ok"

        if len(self.summary.items) > 0:
            response = {}
            for key in self.summary.items:
                value = self.summary.items[key]
                if isinstance(value, str):
                    response[key] = value
                elif isinstance(value, HealthCheckSummaryException):
                    response[key] = str(value.exception)

            return response

        return str(super().pretty_status())


class AWSSecretManagerHealthCheck(BaseLightspeedHealthCheck):
    critical_service = True

    def check_status(self):
        self.enabled = settings.ENABLE_HEALTHCHECK_SECRET_MANAGER
        if not self.enabled:
            return

        FAUX_ORG_ID = "9999999999"
        try:
            apps.get_app_config("ai").get_wca_secret_manager().get_secret(
                FAUX_ORG_ID, Suffixes.API_KEY
            )
        except Exception as e:
            self.add_error(ServiceUnavailable(ERROR_MESSAGE), e)

    def identifier(self):
        return self.__class__.__name__


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


class ModelPipelineHealthCheck(BaseLightspeedHealthCheck):
    # If this is set to False, the status endpoints will respond with a 200
    # status code even if the check errors.
    critical_service = True

    def __init__(self, pipeline_type: Type[PIPELINE_TYPE]):
        super().__init__()
        pipeline_config: PIPELINE_TYPE = apps.get_app_config("ai").get_model_pipeline(pipeline_type)
        self.pipeline_type = pipeline_type
        self.enabled = pipeline_config.config.enable_health_check

    def check_status(self):
        if not self.enabled:
            return

        try:
            model_pipeline = apps.get_app_config("ai").get_model_pipeline(self.pipeline_type)
            summary: Optional[HealthCheckSummary] = model_pipeline.self_test()
        except NotImplementedError:
            return

        if summary is None:
            return

        self.summary = summary
        for key in self.summary.items:
            value = self.summary.items[key]
            if isinstance(value, HealthCheckSummaryException):
                self.add_error(value.exception, value.cause)

    def identifier(self):
        return self.pipeline_type.__name__
