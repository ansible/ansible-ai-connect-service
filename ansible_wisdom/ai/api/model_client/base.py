from abc import abstractmethod

from django.conf import settings


class ModelMeshClient:
    def __init__(self, inference_url):
        self._inference_url = inference_url

    @abstractmethod
    def infer(self, model_input, model_name="wisdom"):
        pass
