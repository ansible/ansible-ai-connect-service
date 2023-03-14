from abc import abstractmethod

from django.conf import settings


class ModelMeshClient:
    def __init__(self, inference_url):
        self._inference_url = inference_url
        i = settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
        self._timeout = int(i) if i is not None else None

    @abstractmethod
    def infer(self, model_input, model_name="wisdom"):  # pragma: no cover
        pass

    @property
    def timeout(self):
        return self._timeout
