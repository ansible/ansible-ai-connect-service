import logging

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
            #num_predict=400,
            #stop=[],
            #repeat_last_n=256,
            #repeat_penalty=1.18,
            #top_k=40,
            #top_p=0.5,
            #tfs_z=1,
            #mirostat=0,
            #mirostat_tau=5,
            #mirostat_eta=0.1,
            #cache=False,
        )

        #full_context = "- name: Deploy infrastructure\n  hosts: all\n  tasks:\n    - name: Create Openshift Cluster \"1\""
        full_context = f"""{context}{prompt}"""
        try:
            prompt = PromptTemplate.from_template("{prompt}")
            chain = prompt | llm
            task = chain.invoke({
                "prompt": full_context,
            })

            logger.info(f"response: {task}")

            # TODO(rg): remove when we have a better tune/prompt

            task = task.split("- name:")[0]
            task = task.split("```")[0]

            logger.info(f"task: {task}")
            logger.info(f"model: {model_id}")
            response = {"predictions": [task], "model_id": model_id}

            return response
        except requests.exceptions.Timeout:
            raise ModelTimeoutError
