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
from typing import Union

from ansible_risk_insight.scanner import Config
from django.apps import AppConfig
from django.conf import settings

from ansible_ai_connect.ansible_lint import lintpostprocessing
from ansible_ai_connect.ari import postprocessing
from ansible_ai_connect.users.authz_checker import AMSCheck, CIAMCheck, DummyCheck

from .api.aws.wca_secret_manager import AWSSecretManager, DummySecretManager
from .api.model_client.dummy_client import DummyClient
from .api.model_client.grpc_client import GrpcClient
from .api.model_client.http_client import HttpClient
from .api.model_client.llamacpp_client import LlamaCPPClient
from .api.model_client.wca_client import DummyWCAClient, WCAClient, WCAOnPremClient

logger = logging.getLogger(__name__)

FAILED = False
UNINITIALIZED = None


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ansible_ai_connect.ai"
    model_mesh_client = None
    _ari_caller = UNINITIALIZED
    _seat_checker = UNINITIALIZED
    _wca_secret_manager = UNINITIALIZED
    _ansible_lint_caller = UNINITIALIZED

    def ready(self) -> None:
        if settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "grpc":
            self.model_mesh_client = GrpcClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "wca":
            self.model_mesh_client = WCAClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "wca-onprem":
            self.model_mesh_client = WCAOnPremClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "wca-dummy":
            self.model_mesh_client = DummyWCAClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "http":
            self.model_mesh_client = HttpClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "llamacpp":
            self.model_mesh_client = LlamaCPPClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "dummy":
            self.model_mesh_client = DummyClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "bam":
            from .api.model_client.bam_client import BAMClient

            self.model_mesh_client = BAMClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "ollama":
            from .api.model_client.ollama_client import OllamaClient

            self.model_mesh_client = OllamaClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL,
            )
        else:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        return super().ready()

    def get_ari_caller(self):
        # Django calls apps.ready() when registering INSTALLED_APPS
        # We can therefore guarantee self.model_mesh_client is not None
        if not self.model_mesh_client.supports_ari_postprocessing():
            logger.info("Postprocessing is disabled.")
            self._ari_caller = UNINITIALIZED
            return None
        if self._ari_caller is FAILED:
            return None
        if self._ari_caller:
            return self._ari_caller
        try:
            self._ari_caller = postprocessing.ARICaller(
                config=Config(
                    rules_dir=settings.ARI_RULES_DIR,
                    data_dir=settings.ARI_DATA_DIR,
                    rules=settings.ARI_RULES,
                ),
                silent=True,
            )
            logger.info("Postprocessing is enabled.")
        except Exception:
            logger.exception("Failed to initialize ARI.")
            self._ari_caller = FAILED
        return self._ari_caller

    def get_seat_checker(self):
        backends = {
            "ams": AMSCheck,
            "ciam": CIAMCheck,
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

    def get_ansible_lint_caller(self):
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
