from abc import abstractmethod


class ModelMeshClient:
    def __init__(self, inference_url, management_url):
        self._inference_url = inference_url
        self._management_url = management_url

    @abstractmethod
    def infer(self, model_input, model_name="wisdom"):
        pass
