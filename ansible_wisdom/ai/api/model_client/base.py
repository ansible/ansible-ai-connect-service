from abc import abstractmethod
from typing import Optional

from django.conf import settings


class ModelMeshClient:
    def __init__(self, inference_url):
        self._inference_url = inference_url
        i = settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
        self._timeout = int(i) if i is not None else None

    @abstractmethod
    def infer(self, model_input, model_id="wisdom", suggestion_id=None):  # pragma: no cover
        pass

    def codematch(self, model_input, model_id):
        raise NotImplementedError

    def set_inference_url(self, inference_url):
        self._inference_url = inference_url

    def get_model_id(
        self,
        organization_id: Optional[int] = None,
        requested_model_id: str = '',
    ) -> str:
        return requested_model_id or settings.ANSIBLE_AI_MODEL_NAME

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None

    def get_chat_model(self, model_id):
        raise NotImplementedError
