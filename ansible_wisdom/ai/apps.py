import logging

import torch
from ansible_risk_insight.scanner import Config
from django.apps import AppConfig
from django.conf import settings

from ari import postprocessing
from tools.jaeger import tracer

logger = logging.getLogger(__name__)


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    model_mesh_client = None
    _ari_caller = None

    def ready(self):
        # print("inside ready function")
        #
        # with tracer.start_as_current_span(__file__ + ' ready') as span:
        #     span.set_attribute('Class', __class__.__name__)
        #     span.set_attribute('file', __file__)
        #     span.set_attribute('Method', "ready")
        #     span.set_attribute(
        #         'Description',
        #         'initializes model mesh client based on backend server (HTTP, gRPC, mock)',
        #     )

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
        with tracer.start_span('get_ari_caller ') as span:
            span.set_attribute('Class', __class__.__name__)
            span.set_attribute('file', __file__)
            span.set_attribute('Method', "write_to_segment")
            span.set_attribute('Description', 'initializes ari object')
            FAILED = False
            UNINITIALIZED = None
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
