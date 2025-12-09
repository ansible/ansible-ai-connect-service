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
from typing import Type, Union

from django.apps import AppConfig
from django.conf import settings

from ansible_ai_connect.ai.api.model_pipelines.factory import ModelPipelineFactory
from ansible_ai_connect.ai.api.model_pipelines.types import PIPELINE_TYPE
from ansible_ai_connect.ansible_lint import lintpostprocessing
from ansible_ai_connect.users.authz_checker import AMSCheck, DummyCheck
from ansible_ai_connect.users.reports.postman import (
    BasePostman,
    GoogleDrivePostman,
    NoopPostman,
    SlackWebApiPostman,
    SlackWebhookPostman,
    StdoutPostman,
)

from .api.aws.wca_secret_manager import AWSSecretManager, DummySecretManager

logger = logging.getLogger(__name__)

FAILED = False
UNINITIALIZED = None


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ansible_ai_connect.ai"
    _seat_checker = UNINITIALIZED
    _wca_secret_manager = UNINITIALIZED
    _ansible_lint_caller = UNINITIALIZED
    _reports_postman = UNINITIALIZED
    _pipeline_factory = UNINITIALIZED

    def ready(self) -> None:
        self._pipeline_factory = ModelPipelineFactory()
        return super().ready()

    def get_model_pipeline(self, feature: Type[PIPELINE_TYPE]) -> PIPELINE_TYPE:
        return self._pipeline_factory.get_pipeline(feature)

    def get_seat_checker(self):
        backends = {
            "ams": AMSCheck,
            "dummy": DummyCheck,
        }
        if not settings.AUTHZ_BACKEND_TYPE:
            self._seat_checker = UNINITIALIZED
            return None

        try:
            expected_backend = backends[settings.AUTHZ_BACKEND_TYPE]
        except KeyError:
            logger.error("Unexpected AUTHZ_BACKEND_TYPE value: '%s'", settings.AUTHZ_BACKEND_TYPE)
            return None

        if self._seat_checker is UNINITIALIZED:
            self._seat_checker = expected_backend(
                settings.AUTHZ_SSO_CLIENT_ID,
                settings.AUTHZ_SSO_CLIENT_SECRET,
                settings.AUTHZ_SSO_SERVER,
                settings.AUTHZ_API_SERVER,
            )

        return self._seat_checker

    def get_wca_secret_manager(self) -> Union[AWSSecretManager, DummySecretManager]:
        backends = {
            "aws_sm": AWSSecretManager,
            "dummy": DummySecretManager,
        }

        expected_backend = None
        try:
            expected_backend = backends[settings.WCA_SECRET_BACKEND_TYPE]
        except KeyError:
            logger.exception(
                "Unexpected WCA_SECRET_BACKEND_TYPE value: '%s'", settings.WCA_SECRET_BACKEND_TYPE
            )

        if self._wca_secret_manager is UNINITIALIZED:
            self._wca_secret_manager = expected_backend(
                settings.WCA_SECRET_MANAGER_ACCESS_KEY,
                settings.WCA_SECRET_MANAGER_SECRET_ACCESS_KEY,
                settings.WCA_SECRET_MANAGER_KMS_KEY_ID,
                settings.WCA_SECRET_MANAGER_PRIMARY_REGION,
                settings.WCA_SECRET_MANAGER_REPLICA_REGIONS,
            )

        return self._wca_secret_manager

    def get_ansible_lint_caller(self) -> lintpostprocessing.AnsibleLintCaller | None:
        if self._ansible_lint_caller:
            return self._ansible_lint_caller
        if not settings.ENABLE_ANSIBLE_LINT_POSTPROCESS:
            logger.info("Ansible Lint Postprocessing is disabled.")
            return None
        if self._ansible_lint_caller is FAILED:
            return None
        try:
            self._ansible_lint_caller = lintpostprocessing.AnsibleLintCaller()
            logger.info("Ansible Lint Postprocessing is enabled.")
        except Exception as ex:
            logger.exception(f"Failed to initialize Ansible Lint with exception: {ex}")
            self._ansible_lint_caller = FAILED
        return self._ansible_lint_caller

    def get_reports_postman(self) -> BasePostman:
        if self._reports_postman is UNINITIALIZED:
            postmen = {
                "none": NoopPostman,
                "stdout": StdoutPostman,
                "slack-webhook": SlackWebhookPostman,
                "slack-webapi": SlackWebApiPostman,
                "google-drive": GoogleDrivePostman,
            }

            try:
                expected_postman = postmen[settings.ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN]
            except KeyError:
                logger.exception(
                    "Unexpected ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN "
                    f"value: {settings.ANSIBLE_AI_ONE_CLICK_REPORTS_POSTMAN}"
                )
                raise

            self._reports_postman = expected_postman()

        return self._reports_postman
