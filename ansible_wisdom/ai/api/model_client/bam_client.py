import json
import logging
import re
from typing import Any, Callable, List, Optional

import requests
from django.conf import settings
from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.messages.chat import ChatMessage
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE_TEMPLATE = "You are an Ansible expert. Return a single task that best completes the partial playbook. Return only the task as YAML. Do not return multiple tasks. Do not explain your response. Do not include the prompt in your response."
HUMAN_MESSAGE_TEMPLATE = "{prompt}"


class ChatBAM(SimpleChatModel):
    api_key: str
    model_id: str
    prediction_url: str
    timeout: Callable[[int], int]

    @property
    def _llm_type(self) -> str:
        return "BAM"

    def _call(
        self,
        messages: List[ChatMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> str:
        if stop is not None:
            raise ValueError("stop kwargs are not permitted.")

        bam_messages = list(
            map(lambda x: {"role": x.additional_kwargs['role'], "content": x.content}, messages)
        )
        session = requests.Session()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        params = {
            "model_id": self.model_id,
            "messages": bam_messages,
            "parameters": {
                "temperature": 0.1,
                "decoding_method": "greedy",
                "repetition_penalty": 1.05,
                "min_new_tokens": 1,
                "max_new_tokens": 2048,
            },
        }

        logger.info(f"request: {params}")

        # TODO(rg): implement multitask
        # task_count = len(get_task_names_from_prompt(prompt))
        result = session.post(
            self.prediction_url,
            headers=headers,
            json=params,
            # timeout=self.timeout(task_count),
            timeout=self.timeout(1),
        )
        result.raise_for_status()
        body = json.loads(result.text)
        logger.info(f"response: {body}")
        response = body.get("results", [{}])[0].get("generated_text", "")
        return response


class BAMClient(ModelMeshClient):
    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        self._prediction_url = f"{self._inference_url}/v2/text/chat?version=2024-01-10"

    def get_chat_model(self, model_id):
        return ChatBAM(
            api_key=settings.ANSIBLE_AI_MODEL_MESH_API_KEY,
            model_id=model_id,
            prediction_url=self._prediction_url,
            timeout=self.timeout,
        )

    def infer(self, model_input, model_id=None, suggestion_id=None):
        model_id = model_id or settings.ANSIBLE_AI_MODEL_NAME

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        logger.info(f"prompt: '{prompt}'")
        logger.info(f"context: '{context}'")

        full_prompt = f"{context}{prompt}\n"
        logger.info(f"full prompt: {full_prompt}")

        llm = self.get_chat_model(model_id)

        chat_template = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    SYSTEM_MESSAGE_TEMPLATE, additional_kwargs={"role": "system"}
                ),
                HumanMessagePromptTemplate.from_template(
                    HUMAN_MESSAGE_TEMPLATE, additional_kwargs={"role": "user"}
                ),
            ]
        )

        try:
            # messages = chat_template.format_messages(prompt=full_prompt)
            chain = chat_template | llm
            message = chain.invoke({"prompt": full_prompt})

            task = message.content

            # TODO(rg): fragile and not always correct; remove when we've created a better tune
            task = task.split("```yaml")[-1]
            task = re.split(r'- name: .+\n', task)[-1]
            task = task.split("```")[0]
            response = {"predictions": [task], "model_id": model_id}

            return response

        except requests.exceptions.Timeout:
            raise ModelTimeoutError
