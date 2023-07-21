import logging

import torch
from ansible_risk_insight.scanner import Config
from django.apps import AppConfig
from django.conf import settings
from users.authz_checker import AMSCheck, CIAMCheck

from ari import postprocessing

logger = logging.getLogger(__name__)

FAILED = False
UNINITIALIZED = None


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    model_mesh_client = None
    _ari_caller = UNINITIALIZED
    _ciam_checker = UNINITIALIZED
    _ams_checker = UNINITIALIZED

    def ready(self) -> None:
        if torch.cuda.is_available():
            logger.info('GPU is available')
        else:
            logger.error('GPU is not available')
        if settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "grpc":
            from .api.model_client.grpc_client import GrpcClient

            self.model_mesh_client = GrpcClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "http":
            from .api.model_client.http_client import HttpClient

            self.model_mesh_client = HttpClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "mock":
            from .api.model_client.mock_client import MockClient

            self.model_mesh_client = MockClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        else:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        return super().ready()

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

    def get_ciam_checker(self):
        if self._ciam_checker is UNINITIALIZED:
            self._ciam_checker = CIAMCheck(
                settings.AUTHZ_SSO_CLIENT_ID,
                settings.AUTHZ_SSO_CLIENT_SECRET,
                settings.AUTHZ_SSO_SERVER,
                settings.AUTHZ_END_POINT,
            )

        return self._ciam_checker

    def get_ams_checker(self):
        if self._ams_checker is UNINITIALIZED:
            self._ams_checker = AMSCheck(
                settings.AUTHZ_SSO_CLIENT_ID,
                settings.AUTHZ_SSO_CLIENT_SECRET,
                settings.AUTHZ_SSO_SERVER,
                settings.AUTHZ_END_POINT,
            )

        return self._ams_checker
