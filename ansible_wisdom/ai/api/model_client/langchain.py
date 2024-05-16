#!/usr/bin/env python3

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

import re
from textwrap import dedent
from typing import Any, Dict

import requests
from langchain_core.messages import BaseMessage
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from .base import ModelMeshClient
from .exceptions import ModelTimeoutError

SYSTEM_MESSAGE_TEMPLATE = (
    "You are an Ansible expert. Return a single task that best completes the "
    "partial playbook. Return only the task as YAML. Do not return multiple tasks. "
    "Do not explain your response. Do not include the prompt in your response."
)
HUMAN_MESSAGE_TEMPLATE = "{prompt}"


def unwrap_playbook_answer(message: str | BaseMessage) -> tuple[str, str]:
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

    m = re.search(r".*?```(yaml|)\n+(.+)```(.*)", task, re.MULTILINE | re.DOTALL)
    if m:
        playbook = m.group(2).strip()
        outline = m.group(3).lstrip().strip()
        return playbook, outline
    else:
        return "", ""


def unwrap_task_answer(message: str | BaseMessage) -> str:
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

    m = re.search(r"```(yaml|)\n+(.+)```", task, re.MULTILINE | re.DOTALL)
    if m:
        task = m.group(2)
    return dedent(re.split(r'- name: .+\n', task)[-1]).rstrip()


class LangChainClient(ModelMeshClient):
    def get_chat_model(self, model_id):
        raise NotImplementedError

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
            response = {"predictions": [unwrap_task_answer(message)], "model_id": model_id}

            return response

        except requests.exceptions.Timeout:
            raise ModelTimeoutError

    def generate_playbook(
        self, text: str = "", create_outline: bool = False, outline: str = ""
    ) -> tuple[str, str]:
        SYSTEM_MESSAGE_TEMPLATE = """
        You are an Ansible expert.
        Your role is to help Ansible developers write playbooks.
        You answer with an Ansible playbook.
        """

        SYSTEM_MESSAGE_TEMPLATE_WITH_OUTLINE = """
        You are an Ansible expert.
        Your role is to help Ansible developers write playbooks.
        The first part of the answer is an Ansible playbook.
        the second part is a step by step explanation of this.
        Use a new line to explain each step.
        """

        HUMAN_MESSAGE_TEMPLATE = """
        This is what the playbook should do: {text}
        """

        HUMAN_MESSAGE_TEMPLATE_WITH_OUTLINE = """
        This is what the playbook should do: {text}
        This is a break down of the expected Playbook: {outline}
        """

        system_template = (
            SYSTEM_MESSAGE_TEMPLATE_WITH_OUTLINE if create_outline else SYSTEM_MESSAGE_TEMPLATE
        )
        human_template = HUMAN_MESSAGE_TEMPLATE_WITH_OUTLINE if outline else HUMAN_MESSAGE_TEMPLATE
        from ansible_ai_connect.ai.api.model_client.langchain import (
            unwrap_playbook_answer,
        )

        model_id = self.get_model_id(None, "")
        llm = self.get_chat_model(model_id)

        chat_template = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    dedent(system_template),
                    additional_kwargs={"role": "system"},
                ),
                HumanMessagePromptTemplate.from_template(
                    dedent(human_template), additional_kwargs={"role": "user"}
                ),
            ]
        )

        chain = chat_template | llm
        output = chain.invoke({"text": text, "outline": outline})
        playbook, outline = unwrap_playbook_answer(output)

        if not create_outline:
            outline = ""

        return playbook, outline

    def explain_playbook(self, content) -> str:
        SYSTEM_MESSAGE_TEMPLATE = """
        You're an Ansible expert.
        You format your output with Markdown.
        You only answer with text paragraphs.
        Write one paragraph per Ansible task.
        Markdown title starts with the '#' character.
        Write a title before every paragraph.
        Do not return any YAML or Ansible in the output.
        Give a lot of details regarding the parameters of each Ansible plugin.
        """

        HUMAN_MESSAGE_TEMPLATE = """Please explain the following Ansible playbook:

        {playbook}"
        """

        model_id = self.get_model_id(None, "")
        llm = self.get_chat_model(model_id)

        chat_template = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    dedent(SYSTEM_MESSAGE_TEMPLATE),
                    additional_kwargs={"role": "system"},
                ),
                HumanMessagePromptTemplate.from_template(
                    dedent(HUMAN_MESSAGE_TEMPLATE), additional_kwargs={"role": "user"}
                ),
            ]
        )

        chain = chat_template | llm
        explanation = chain.invoke({"playbook": content})
        return explanation
