#  Copyright Red Hat
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import json
import logging
import re
from textwrap import dedent
from typing import Any, Callable, Dict, List, Optional, Union

import requests
from django.conf import settings
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import SimpleChatModel
from langchain_core.messages import BaseMessage
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

logger = logging.getLogger(__name__)

SYSTEM_MESSAGE_TEMPLATE = (
    "You are an Ansible expert. Return a single task that best completes the "
    "partial playbook. Return only the task as YAML. Do not return multiple tasks. "
    "Do not explain your response. Do not include the prompt in your response."
)
HUMAN_MESSAGE_TEMPLATE = "{prompt}"


class ChatBAM(SimpleChatModel):
    api_key: str
    model_id: str
    prediction_url: str
    timeout: Callable[[int], Union[int, None]]

    @property
    def _llm_type(self) -> str:
        return "BAM"

    def _call(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
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

        result = session.post(
            self.prediction_url,
            headers=headers,
            json=params,
            timeout=self.timeout(1),
        )
        result.raise_for_status()
        body = json.loads(result.text)
        logger.info(f"response: {body}")
        response = body.get("results", [{}])[0].get("generated_text", "")
        return response


def unwrap_answer(message: Union[str, BaseMessage]) -> str:
    task: str = ""
    if isinstance(message, BaseMessage):
        if (
            isinstance(message.content, list)
            and len(message.content)
            and isinstance(message.content[0], str)
        ):
            task = message.content[0]
        elif isinstance(message.content, str):
            task = message.content
    elif isinstance(message, str):
        # Ollama currently answers with just a string
        task = message
    if not task:
        raise ValueError

    m = re.search(r"```yaml\n+(.+)```", task, re.MULTILINE | re.DOTALL)
    if m:
        task = m.group(1)
    return dedent(re.split(r'- name: .+\n', task)[-1]).rstrip()


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

    def infer(self, model_input, model_id="", suggestion_id=None) -> Dict[str, Any]:
        model_id = self.get_model_id(None, model_id)

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        full_prompt = f"{context}{prompt}\n"
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
            chain = chat_template | llm
            message = chain.invoke({"prompt": full_prompt})
            response = {"predictions": [unwrap_answer(message)], "model_id": model_id}

            return response

        except requests.exceptions.Timeout:
            raise ModelTimeoutError
