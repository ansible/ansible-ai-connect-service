import json
import logging
import re

import requests
from django.conf import settings

from ansible_wisdom.ai.api.formatter import get_task_names_from_prompt

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class BAMClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.ANSIBLE_AI_MODEL_MESH_API_KEY}"
        }

    def infer(self, model_input, model_id=None, suggestion_id=None):
        model_id = model_id or settings.ANSIBLE_AI_MODEL_NAME
        #self._prediction_url = f"{self._inference_url}/v2/text/generation?version=2024-01-10"
        self._prediction_url = f"{self._inference_url}/v2/text/chat?version=2024-01-10"

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        logger.info(f"prompt: '{prompt}'")
        logger.info(f"context: '{context}'")

        full_prompt = f"{context}{prompt}\n"
        logger.info(f"full prompt: {full_prompt}")

        params = {
            "model_id": model_id,
            "messages": [{
                "role": "system",
                "content": "You are an Ansible expert. Return a single task that best completes the partial playbook. Return only the task as YAML. Do not return multiple tasks. Do not explain your response. Do not include the prompt in your response."
            },{
                "role": "user",
                "content": full_prompt,
            }],
            "parameters": {
                "temperature": 0.1,
                "decoding_method": "greedy",
                "repetition_penalty": 1.05,
                "min_new_tokens": 1,
                "max_new_tokens": 2048
            }
        }

        logger.info(f"request: {params}")

        try:
            # TODO(rg): implement multitask here with a loop
            task_count = len(get_task_names_from_prompt(prompt))
            result = self.session.post(
                self._prediction_url,
                headers=self.headers,
                json=params,
                timeout=self.timeout(task_count),
            )
            result.raise_for_status()
            body = json.loads(result.text)
            logger.info(f"response: {body}")
            task = body.get("results", [{}])[0].get("generated_text", "")
            # TODO(rg): fragile and not always correct; remove when we've created a better tune
            task = task.split("```yaml")[-1]
            task = re.split(r'- name: .+\n', task)[-1]
            task = task.split("```")[0]
            response = {"predictions": [task], "model_id": body["model_id"]}

            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError
