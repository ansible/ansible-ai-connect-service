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
from typing import Generic, Optional, TypeVar

import requests
from langchain_core.messages import BaseMessage
from langchain_core.prompts.chat import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    SystemMessagePromptTemplate,
)

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.model_pipelines.langchain.configuration import (
    LangchainConfiguration,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PIPELINE_PARAMETERS,
    PIPELINE_RETURN,
    CompletionsParameters,
    CompletionsResponse,
    MetaData,
    ModelPipeline,
    ModelPipelineCompletions,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleGeneration,
    PlaybookExplanationParameters,
    PlaybookExplanationResponse,
    PlaybookGenerationParameters,
    PlaybookGenerationResponse,
    RoleGenerationParameters,
    RoleGenerationResponse,
)
from ansible_ai_connect.healthcheck.backends import HealthCheckSummary

logger = logging.getLogger(__name__)

LANGCHAIN_PIPELINE_CONFIGURATION = TypeVar(
    "LANGCHAIN_PIPELINE_CONFIGURATION", bound=LangchainConfiguration
)

SYSTEM_MESSAGE_TEMPLATE = (
    "You are an Ansible expert. Return a single task that best completes the "
    "partial playbook. Return only the task as YAML. Do not return multiple tasks. "
    "Do not explain your response. Do not include the prompt in your response."
)
HUMAN_MESSAGE_TEMPLATE = "{prompt}"


def message_to_string(message: str | BaseMessage) -> str:
    if isinstance(message, str):
        # Ollama currently answers with just a string
        return message

    if isinstance(message, BaseMessage):
        if (
            isinstance(message.content, list)
            and len(message.content)
            and isinstance(message.content[0], str)
        ):
            return message.content[0]
        elif isinstance(message.content, str):
            return message.content

    raise ValueError


def create_role_outline(yaml: str) -> str:
    outline = ""
    index = 1
    for line in yaml.split("\n"):
        line = line.strip()
        if line.find("- name: ") != -1:
            step = line[line.find("- name: ") + 8 :].strip()
            outline += f"{str(index)}. {step}\n"
            index += 1
    return outline


def unwrap_role_answer(message: str | BaseMessage, create_outline: bool) -> tuple[str, list, str]:
    text = message_to_string(message)
    role = text.strip().split("\n", 1)[0]
    role = "role_name" if (role.find(":") == -1) else role[role.find(":") + 1 :].strip()
    # Sometimes Granite 3b creates explanation string with : at the end
    role = "role_name" if not role else role

    if text.find("```") == -1:
        main_yml_content = text.strip().split("\n", 1)[1].strip()
    else:
        main_yml_content = unwrap_message_with_yaml_answer(text)

    outline = ""
    if create_outline:
        outline = create_role_outline(main_yml_content)

    tasks = {"path": "tasks/main.yml", "content": main_yml_content, "file_type": "tasks"}
    default = {
        "path": "defaults/main.yml",
        "content": "",
        "file_type": "defaults",
    }

    return role, [tasks, default], outline


def unwrap_message_with_yaml_answer(message: str | BaseMessage) -> str:
    task: str = message_to_string(message)

    m = re.search(r".*?```(yaml|yml|)\n+(.+)```", task, re.MULTILINE | re.DOTALL)
    return m.group(2).strip() if m else ""


def unwrap_playbook_answer(message: str | BaseMessage) -> tuple[str, str]:
    task: str = message_to_string(message)

    m = re.search(r".*?```(yaml|)\n+(.+)```(.*)", task, re.MULTILINE | re.DOTALL)
    if m:
        playbook = m.group(2).strip()
        outline = m.group(3).lstrip().strip()
        return playbook, outline
    else:
        return "", ""


def unwrap_task_answer(message: str | BaseMessage) -> str:
    task: str = message_to_string(message)

    m = re.search(r"```(yaml|)\n+(.+)```", task, re.MULTILINE | re.DOTALL)
    if m:
        task = m.group(2)
    return dedent(re.split(r"- name: .+\n", task)[-1]).rstrip()


class LangchainMetaData(
    MetaData[LANGCHAIN_PIPELINE_CONFIGURATION], Generic[LANGCHAIN_PIPELINE_CONFIGURATION]
):

    def __init__(self, config: LANGCHAIN_PIPELINE_CONFIGURATION):
        super().__init__(config=config)
        i = self.config.timeout
        self._timeout = int(i) if i is not None else None

    def timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None


class LangchainBase(
    LangchainMetaData,
    ModelPipeline[LANGCHAIN_PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    Generic[LANGCHAIN_PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    metaclass=ABCMeta,
):

    def __init__(self, config: LANGCHAIN_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def create_template(self, system, human):
        return ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    dedent(system),
                    additional_kwargs={"role": "system"},
                ),
                HumanMessagePromptTemplate.from_template(
                    dedent(human), additional_kwargs={"role": "user"}
                ),
            ]
        )


class LangchainCompletionsPipeline(
    LangchainBase[LANGCHAIN_PIPELINE_CONFIGURATION, CompletionsParameters, CompletionsResponse],
    ModelPipelineCompletions[LANGCHAIN_PIPELINE_CONFIGURATION],
    Generic[LANGCHAIN_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: LANGCHAIN_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

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

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError

    def get_chat_model(self, model_id):
        raise NotImplementedError

    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


class LangchainPlaybookGenerationPipeline(
    LangchainBase[
        LANGCHAIN_PIPELINE_CONFIGURATION, PlaybookGenerationParameters, PlaybookGenerationResponse
    ],
    ModelPipelinePlaybookGeneration[LANGCHAIN_PIPELINE_CONFIGURATION],
    Generic[LANGCHAIN_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: LANGCHAIN_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

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

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError

    def get_chat_model(self, model_id):
        raise NotImplementedError


class LangchainRoleGenerationPipeline(
    LangchainBase[
        LANGCHAIN_PIPELINE_CONFIGURATION, RoleGenerationParameters, RoleGenerationResponse
    ],
    ModelPipelineRoleGeneration[LANGCHAIN_PIPELINE_CONFIGURATION],
    Generic[LANGCHAIN_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: LANGCHAIN_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def invoke(self, params: RoleGenerationParameters) -> RoleGenerationResponse:
        request = params.request
        text = params.text
        create_outline = params.create_outline
        outline = params.outline
        model_id = params.model_id

        SYSTEM_MESSAGE_ROLE_REQUEST = """
        You are an ansible expert optimized to generate Ansible roles.
        First line the role name in a way: role_name.
        After that the answer is a plain tasks/main.yml file for the user's request.
        Prefix your comments with the hash character.
        """

        SYSTEM_MESSAGE_TEMPLATE_DEFAULTS = """
        You are an ansible expert optimized to generate Ansible roles.
        Prepare a plain defaults/main.yml file based on provided tasks/main.yml.
        New file is a list of variables name and value from provided tasks/main.yml.
        Do not provide any addition information or explanation.
        Prefix your comments with the hash character.
        """

        HUMAN_MESSAGE_TEMPLATE = """
        This is what the role should do: {text}
        """

        model_id = self.get_model_id(request.user, None, model_id)
        llm = self.get_chat_model(model_id)

        chat_template = self.create_template(SYSTEM_MESSAGE_ROLE_REQUEST, HUMAN_MESSAGE_TEMPLATE)
        chain = chat_template | llm
        output = chain.invoke({"text": text, "outline": outline})
        role, files, outline = unwrap_role_answer(output, create_outline)

        llm = self.get_chat_model(model_id)
        chat_template = self.create_template(
            SYSTEM_MESSAGE_TEMPLATE_DEFAULTS, HUMAN_MESSAGE_TEMPLATE
        )
        chain = chat_template | llm
        output = chain.invoke({"text": files[0]["content"], "outline": outline})
        content = message_to_string(output)
        if content.find("```") == -1:
            files[1]["content"] = content
        else:
            files[1]["content"] = unwrap_message_with_yaml_answer(content)

        return role, files, outline, []

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError

    def get_chat_model(self, model_id):
        raise NotImplementedError


class LangchainPlaybookExplanationPipeline(
    LangchainBase[
        LANGCHAIN_PIPELINE_CONFIGURATION, PlaybookExplanationParameters, PlaybookExplanationResponse
    ],
    ModelPipelinePlaybookExplanation[LANGCHAIN_PIPELINE_CONFIGURATION],
    Generic[LANGCHAIN_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: LANGCHAIN_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

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

    def self_test(self) -> Optional[HealthCheckSummary]:
        raise NotImplementedError

    def get_chat_model(self, model_id):
        raise NotImplementedError
