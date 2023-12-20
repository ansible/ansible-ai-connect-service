import json
import logging

import requests
from ai.api.formatter import get_task_names_from_prompt
from django.conf import settings

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class LlamaCPPClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_id=None, suggestion_id=None):
        model_id = model_id or settings.ANSIBLE_AI_MODEL_NAME
        self._prediction_url = f"{self._inference_url}/completion"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        logger.info(f"prompt: '{prompt}'")
        logger.info(f"context: '{context}'")

        full_prompt = f"{context}{prompt}\n"
        logger.info(f"full prompt: {full_prompt}")

        data = {
            "prompt": full_prompt,
            "n_predict": 400,
            "temperature": 0.1,
            "stop": [],
            "repeat_last_n": 256,
            "repeat_penalty": 1.18,
            "top_k": 40,
            "top_p": 0.5,
            "tfs_z": 1,
            "typical_p": 1,
            "presence_penalty": 0,
            "frequency_penalty": 0,
            "mirostat": 0,
            "mirostat_tau": 5,
            "mirostat_eta": 0.1,
            "grammar": "",
            "n_probs": 0,
            "image_data": [],
            "cache_prompt": False,
            "stream": False,
            "seed": 0,
        }

        logger.info(f"request: {data}")

        try:
            task_count = len(get_task_names_from_prompt(prompt))
            result = self.session.post(
                self._prediction_url,
                headers=self.headers,
                json=data,
                timeout=self.timeout(task_count),
            )
            result.raise_for_status()
            body = json.loads(result.text)
            logger.info(f"response: {body}")
            task = body["content"]
            # TODO(rg): remove this when we've created a better tune
            task = task.split("\n    - name")[0]
            response = {"predictions": [task], "model_id": body["model"]}

            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError
