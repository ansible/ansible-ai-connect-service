import logging

from ansible_risk_insight.scanner import Config
from django.apps import AppConfig
from django.conf import settings

from ari import postprocessing

logger = logging.getLogger(__name__)


class AiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    model_mesh_client = None
    ari_caller = None

    def ready(self) -> None:
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
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "aws":
            from .api.model_client.aws_client import AWSClient

            self.model_mesh_client = AWSClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            )
        else:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        # TODO may be we can parallelize ari and grpc client creation
        try:
            if settings.ENABLE_ARI_POSTPROCESS:
                self.ari_caller = postprocessing.ARICaller(
                    config=Config(
                        rules_dir=settings.ARI_RULES_DIR,
                        data_dir=settings.ARI_DATA_DIR,
                        rules=settings.ARI_RULES,
                    ),
                    silent=True,
                )
                logger.info("Postprocessing is enabled.")
            else:
                logger.info("Postprocessing is disabled.")
        except Exception:
            logger.exception("Failed to initialize ARI.")
            self.ari_caller = None

        return super().ready()
