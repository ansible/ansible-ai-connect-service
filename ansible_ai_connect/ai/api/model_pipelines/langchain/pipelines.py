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

import logging
import re
from abc import ABCMeta
from textwrap import dedent

import requests
from django.conf import settings
from langchain_core.messages import BaseMessage
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    CompletionsParameters,
    CompletionsResponse,
    ContentMatchParameters,
    ContentMatchResponse,
    MetaData,
    ModelPipeline,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
)

logger = logging.getLogger(__name__)

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
    return dedent(re.split(r"- name: .+\n", task)[-1]).rstrip()


class LangchainMetaData(MetaData):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)
        i = settings.ANSIBLE_AI_MODEL_MESH_API_TIMEOUT
        self._timeout = int(i) if i is not None else None

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None


class LangchainBase(LangchainMetaData, ModelPipeline, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)


class LangchainCompletionsPipeline(LangchainBase, ModelPipelineCompletions):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        request = params.request
        model_id = params.model_id
        model_input = params.model_input
        model_id = self.get_model_id(request.user, None, model_id)

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

    def get_chat_model(self, model_id):
        raise NotImplementedError

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


class LangchainContentMatchPipeline(LangchainBase, ModelPipelineContentMatch):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: ContentMatchParameters) -> ContentMatchResponse:
        raise NotImplementedError

    def get_chat_model(self, model_id):
        raise NotImplementedError


class LangchainPlaybookGenerationPipeline(LangchainBase, ModelPipelinePlaybookGeneration):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookGenerationParameters) -> PlaybookGenerationResponse:
        request = params.request
        text = params.text
        custom_prompt = params.custom_prompt
        create_outline = params.create_outline
        outline = params.outline
        model_id = params.model_id

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

        if custom_prompt:
            logger.info("custom_prompt is not supported for generate_playbook and will be ignored.")

        system_template = (
            SYSTEM_MESSAGE_TEMPLATE_WITH_OUTLINE if create_outline else SYSTEM_MESSAGE_TEMPLATE
        )
        human_template = HUMAN_MESSAGE_TEMPLATE_WITH_OUTLINE if outline else HUMAN_MESSAGE_TEMPLATE

        model_id = self.get_model_id(request.user, None, model_id)
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

        return playbook, outline, []

    def get_chat_model(self, model_id):
        raise NotImplementedError


class LangchainPlaybookExplanationPipeline(LangchainBase, ModelPipelinePlaybookExplanation):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    def invoke(self, params: PlaybookExplanationParameters) -> PlaybookExplanationResponse:
        request = params.request
        content = params.content
        custom_prompt = params.custom_prompt
        model_id = params.model_id

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

        if custom_prompt:
            logger.info("custom_prompt is not supported for explain_playbook and will be ignored.")

        model_id = self.get_model_id(request.user, None, model_id)
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

    def get_chat_model(self, model_id):
        raise NotImplementedError
