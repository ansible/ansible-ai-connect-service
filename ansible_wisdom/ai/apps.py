import logging

from ansible_lint import lintpostprocessing
from ansible_risk_insight.scanner import Config
from django.apps import AppConfig
from django.conf import settings
from users.authz_checker import AMSCheck, CIAMCheck, DummyCheck

from ari import postprocessing

from .api.aws.wca_secret_manager import AWSSecretManager, DummySecretManager
from .api.model_client.dummy_client import DummyClient
from .api.model_client.wca_client import DummyWCAClient, WCAClient

logger = logging.getLogger(__name__)

FAILED = False
UNINITIALIZED = None


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    model_mesh_client = None
    _wca_client = UNINITIALIZED
    _ari_caller = UNINITIALIZED
    _seat_checker = UNINITIALIZED
    _wca_secret_manager = UNINITIALIZED
    _ansible_lint_caller = UNINITIALIZED

    def ready(self) -> None:
        if settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "grpc":
            from .api.model_client.grpc_client import GrpcClient

            self.model_mesh_client = GrpcClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "wca":
            self.model_mesh_client = self.get_wca_client()
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "http":
            from .api.model_client.http_client import HttpClient

            self.model_mesh_client = HttpClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "llamacpp":
            from .api.model_client.llamacpp_client import LlamaCPPClient

            self.model_mesh_client = LlamaCPPClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE in ["dummy", "mock"]:
            if settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "mock":
                logger.error(
                    'ANSIBLE_AI_MODEL_MESH_API_TYPE == "mock" is deprecated, use "dummy" instead'
                )
            self.model_mesh_client = DummyClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        else:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        return super().ready()

    def get_wca_client(self):
        backends = {
            "wcaclient": WCAClient,
            "dummy": DummyWCAClient,
        }
        if not settings.WCA_CLIENT_BACKEND_TYPE:
            self._wca_client = UNINITIALIZED
            return None

        try:
            expected_backend = backends[settings.WCA_CLIENT_BACKEND_TYPE]
        except KeyError:
            logger.error(
                "Unexpected WCA_CLIENT_BACKEND_TYPE value: '%s'", settings.WCA_CLIENT_BACKEND_TYPE
            )
            self._wca_client = UNINITIALIZED
            return None

        if self._wca_client:
            return self._wca_client

        self._wca_client = expected_backend(
            inference_url=settings.ANSIBLE_WCA_INFERENCE_URL,
        )
        return self._wca_client

    def get_ari_caller(self):
        if not settings.ENABLE_ARI_POSTPROCESS:
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

    def get_wca_secret_manager(self):
        backends = {
            "aws_sm": AWSSecretManager,
            "dummy": DummySecretManager,
        }

        try:
            expected_backend = backends[settings.WCA_SECRET_BACKEND_TYPE]
        except KeyError:
            logger.error(
                "Unexpected WCA_SECRET_BACKEND_TYPE value: '%s'", settings.WCA_SECRET_BACKEND_TYPE
            )
            return None

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
