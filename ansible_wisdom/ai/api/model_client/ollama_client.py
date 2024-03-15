import logging
import re

import requests
from django.conf import settings
from langchain_community.llms import Ollama
from langchain_core.prompts import PromptTemplate

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)


class OllamaClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self.session = requests.Session()
        self.headers = {"Content-Type": "application/json"}

    def infer(self, model_input, model_id=None, suggestion_id=None):
        model_id = model_id or settings.ANSIBLE_AI_MODEL_NAME

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        logger.info(f"prompt: '{prompt}'")
        logger.info(f"context: '{context}'")

        llm = Ollama(
            base_url=self._inference_url,
            model=model_id,
            temperature=0.1,
            # num_predict=400,
            # stop=[],
            # repeat_last_n=256,
            # repeat_penalty=1.18,
            # top_k=40,
            # top_p=0.5,
            # tfs_z=1,
            # mirostat=0,
            # mirostat_tau=5,
            # mirostat_eta=0.1,
            # cache=False,
        )

        template = PromptTemplate.from_template(
            """You're an Ansible expert.
Return a single task that best completes the following partial playbook:
{context}{prompt}
Return only the task as YAML.
Do not return multiple tasks.
Do not explain your response.
"""
        )

        # Only return the portion of the task that comes after the '- name: this is the name'.
        try:
            chain = template | llm
            task = chain.invoke({"context": context, "prompt": prompt})

            logger.info(f"response: {task}")

            # TODO(rg): remove when we have a better tune/prompt

            task = task.split("```yaml")[-1]
            task = re.split(r"- name:.+\n", task)[-1]
            task = task.split("```")[0]

            logger.info(f"task: {task}")
            logger.info(f"model: {model_id}")
            response = {"predictions": [task], "model_id": model_id}

            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError
