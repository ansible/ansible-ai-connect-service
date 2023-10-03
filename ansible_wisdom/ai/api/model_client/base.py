from abc import abstractmethod

from django.conf import settings


class ModelMeshClient:
    def __init__(self, inference_url):
        self._inference_url = inference_url
        i = settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
        self._timeout = int(i) if i is not None else None

    @abstractmethod
    def infer(
        self, model_input, timeout=settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT, model_id="wisdom"
    ):  # pragma: no cover
        pass

    def prepare_prompt_and_context(self, prompt, context):
        return prompt, context

    def set_inference_url(self, inference_url):
        self._inference_url = inference_url

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None
