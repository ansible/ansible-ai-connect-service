import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Optional, TypeVar

from django.conf import settings

from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)

logger = logging.getLogger(__name__)


class MetaData(metaclass=ABCMeta):

    def __init__(self, inference_url):
        self._inference_url = inference_url

    def get_model_id(
        self, user, organization_id: Optional[int] = None, requested_model_id: str = ""
    ) -> str:
        return requested_model_id or settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID

    def supports_ari_postprocessing(self):
        return settings.ENABLE_ARI_POSTPROCESS


class ModelPipeline(MetaData, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    @abstractmethod
    def invoke(self):
        raise NotImplementedError

    def self_test(self):
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: settings.ANSIBLE_AI_MODEL_MESH_API_TYPE,
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


class ModelPipelineCompletions(ModelPipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    @abstractmethod
    def infer(self, request, model_input, model_id: str = "", suggestion_id=None) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


class ModelPipelineContentMatch(ModelPipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    @abstractmethod
    def codematch(self, request, model_input, model_id):
        raise NotImplementedError


class ModelPipelinePlaybookGeneration(ModelPipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    @abstractmethod
    def generate_playbook(
        self,
        request,
        text: str = "",
        custom_prompt: str = "",
        create_outline: bool = False,
        outline: str = "",
        generation_id: str = "",
        model_id: str = "",
    ) -> tuple[str, str, list]:
        raise NotImplementedError


class ModelPipelinePlaybookExplanation(ModelPipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    @abstractmethod
    def explain_playbook(
        self,
        request,
        content: str,
        custom_prompt: str = "",
        explanation_id: str = "",
        model_id: str = "",
    ) -> str:
        raise NotImplementedError


PIPELINE_TYPE = TypeVar("PIPELINE_TYPE")
