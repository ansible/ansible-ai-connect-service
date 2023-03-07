import logging

from ansible_risk_insight.scanner import Config
from django.apps import AppConfig
from django.conf import settings

from ari import postprocessing

logger = logging.getLogger(__name__)


class AIConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "ai"
    ari_caller = None

    def retrieve_client(self, model_name):
        from .models import AIModel

        if model_name is None or model_name.strip() == "":
            model_name = "default"
        if model_name not in self.active_models:
            model_actual = AIModel.objects.filter(name=model_name).first()
            if model_actual:
                self.active_models[model_name] = self.initialize_connection(
                    model_actual.model_mesh_api_type,
                    model_actual.inference_url,
                    model_actual.management_url,
                )
            else:
                model_name = "default"
        return self.active_models[model_name]

    def initialize_connection(self, api_type, inference_url, management_url):
        from .models import ModelMeshType

        # May raise a ValueError; gets the client class annotated on the enum variant
        Client = ModelMeshType(api_type).client
        return Client(inference_url, management_url)

    def ready(self):
        # FIXME: Remove after this is moved out of settings
        model_mesh_client = self.initialize_connection(
            settings.ANSIBLE_AI_MODEL_MESH_API_TYPE,
            settings.ANSIBLE_AI_MODEL_MESH_INFERENCE_URL,
            settings.ANSIBLE_AI_MODEL_MESH_MANAGEMENT_URL,
        )
        self.active_models = {"default": model_mesh_client}

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
