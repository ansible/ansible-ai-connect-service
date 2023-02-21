import logging

from ari.postprocessing import ari
from django.apps import AppConfig
from django.conf import settings

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.DEBUG)
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
                management_url=settings.ANSIBLE_AI_MODEL_MESH_MANAGEMENT_URL,
            )
        elif settings.ANSIBLE_AI_MODEL_MESH_API_TYPE == "http":
            from .api.model_client.http_client import HttpClient

            self.model_mesh_client = HttpClient(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
                management_url=settings.ANSIBLE_AI_MODEL_MESH_MANAGEMENT_URL,
            )
        else:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        # TODO may be we can parallelize ari and grpc client creation
        try:
            if ari.is_enabled():
                self.ari_caller = ari.ARICaller(
                    config=ari.default_config(),
                    silent=True,
                )
                logger.info("Postprocessing is enabled.")
            else:
                logger.info("no ARI rules fonud. Postprocessing is disabled.")
        except Exception:
            logger.exception('failed to initialize ARI')
            self.ari_caller = None

        return super().ready()
