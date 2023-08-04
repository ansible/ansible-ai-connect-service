import logging

import torch
from ansible_risk_insight.scanner import Config
from django.apps import AppConfig
from django.conf import settings
from users.authz_checker import (
    AMSCheck,
    CIAMCheck,
    MockAlwaysFalseCheck,
    MockAlwaysTrueCheck,
)

from ari import postprocessing

from .api.utils.jaeger import with_distributed_tracing

logger = logging.getLogger(__name__)

FAILED = False
UNINITIALIZED = None


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    model_mesh_client = None
    _ari_caller = UNINITIALIZED
    _seat_checker = UNINITIALIZED

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

    @with_distributed_tracing(
        name="Get Ari Caller",
        description='Initializes ARI object',
        file=__file__,
        method='get_ari_caller',
    )
    def get_ari_caller(self, span_ctx):
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
            "mock_true": MockAlwaysTrueCheck,
            "mock_false": MockAlwaysFalseCheck,
        }
        if not settings.AUTHZ_BACKEND_TYPE:
            self._seat_checker = UNINITIALIZED
            return None

        try:
            expected_backend = backends[settings.AUTHZ_BACKEND_TYPE]
        except KeyError:
            logger.error("Unexpected AUTHZ_BACKEND_TYPE value: '%s'", settings.AUTHZ_BACKEND_TYPE)
            return None

        if not isinstance(self._seat_checker, expected_backend):
            self._seat_checker = expected_backend(
                settings.AUTHZ_SSO_CLIENT_ID,
                settings.AUTHZ_SSO_CLIENT_SECRET,
                settings.AUTHZ_SSO_SERVER,
                settings.AUTHZ_API_SERVER,
            )

        return self._seat_checker
