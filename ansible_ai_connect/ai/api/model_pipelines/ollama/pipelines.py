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
from typing import Generic, TypeVar

import requests

from ansible_ai_connect.ai.api.exceptions import ModelTimeoutError
from ansible_ai_connect.ai.api.model_pipelines.nop.configuration import NopConfiguration
from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import (
    NopRoleExplanationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.ollama.configuration import (
    OllamaConfiguration,
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
from ansible_ai_connect.ai.api.model_pipelines.registry import Register
from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
)

logger = logging.getLogger(__name__)

OLLAMA_PIPELINE_CONFIGURATION = TypeVar(
    "OLLAMA_PIPELINE_CONFIGURATION", bound=OllamaConfiguration
)

SYSTEM_MESSAGE_TEMPLATE = (
    "You are an Ansible expert. Return a single task that best completes the "
    "partial playbook. Return only the task as YAML. Do not return multiple tasks. "
    "Do not explain your response. Do not include the prompt in your response."
)
HUMAN_MESSAGE_TEMPLATE = "{prompt}"


class OllamaClient:
    """Simple Ollama API client."""

    def __init__(self, base_url: str, model: str, timeout: int = None):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.timeout = timeout

    def invoke(self, prompt: str) -> str:
        """Call Ollama's generate API endpoint."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        response = requests.post(url, json=payload, timeout=self.timeout)
        response.raise_for_status()

        result = response.json()
        return result.get("response", "")


def message_to_string(message: str) -> str:
    if isinstance(message, str):
        return message
    raise ValueError("Message must be a string")


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


def unwrap_role_answer(message: str, create_outline: bool) -> tuple[str, list, str]:
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


def unwrap_message_with_yaml_answer(message: str) -> str:
    task: str = message_to_string(message)

    m = re.search(r".*?```(yaml|yml|)\n+(.+)```", task, re.MULTILINE | re.DOTALL)
    return m.group(2).strip() if m else ""


def unwrap_playbook_answer(message: str) -> tuple[str, str]:
    task: str = message_to_string(message)

    m = re.search(r".*?```(yaml|)\n+(.+)```(.*)", task, re.MULTILINE | re.DOTALL)
    if m:
        playbook = m.group(2).strip()
        outline = m.group(3).lstrip().strip()
        return playbook, outline
    else:
        return "", ""


def unwrap_task_answer(message: str) -> str:
    task: str = message_to_string(message)

    m = re.search(r"```(yaml|)\n+(.+)```", task, re.MULTILINE | re.DOTALL)
    if m:
        task = m.group(2)
    return dedent(re.split(r"- name: .+\n", task)[-1]).rstrip()


class OllamaMetaDataMixin(
    MetaData[OLLAMA_PIPELINE_CONFIGURATION], Generic[OLLAMA_PIPELINE_CONFIGURATION]
):

    def __init__(self, config: OLLAMA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)
        i = self.config.timeout
        self._timeout = int(i) if i is not None else None

    def task_gen_timeout(self, task_count=1):
        return self._timeout * task_count if self._timeout else None


class OllamaBase(
    OllamaMetaDataMixin,
    ModelPipeline[OLLAMA_PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    Generic[OLLAMA_PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    metaclass=ABCMeta,
):

    def __init__(self, config: OLLAMA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def format_prompt(self, system: str, human: str, **kwargs) -> str:
        """Format system and human messages into a simple combined prompt."""
        system_formatted = dedent(system).format(**kwargs)
        human_formatted = dedent(human).format(**kwargs)
        return f"{system_formatted}\n\n{human_formatted}"

    def get_chat_model(self, model_id):
        return OllamaClient(
            base_url=self.config.inference_url,
            model=model_id,
            timeout=self._timeout,
        )


@Register(api_type="ollama")
class OllamaMetaData(OllamaMetaDataMixin[OllamaConfiguration]):

    def __init__(self, config: OllamaConfiguration):
        super().__init__(config=config)


@Register(api_type="ollama")
class OllamaCompletionsPipeline(
    OllamaBase[OLLAMA_PIPELINE_CONFIGURATION, CompletionsParameters, CompletionsResponse],
    ModelPipelineCompletions[OLLAMA_PIPELINE_CONFIGURATION],
    Generic[OLLAMA_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: OLLAMA_PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    def invoke(self, params: CompletionsParameters) -> CompletionsResponse:
        request = params.request
        model_id = params.model_id
        model_input = params.model_input
        model_id = self.get_model_id(request.user, model_id)

        prompt = model_input.get("instances", [{}])[0].get("prompt", "")
        context = model_input.get("instances", [{}])[0].get("context", "")

        full_prompt = f"{context}{prompt}\n"
        llm = self.get_chat_model(model_id)

        formatted_prompt = self.format_prompt(SYSTEM_MESSAGE_TEMPLATE, HUMAN_MESSAGE_TEMPLATE, prompt=full_prompt)

        try:
            message = llm.invoke(formatted_prompt)
            response = {"predictions": [unwrap_task_answer(message)], "model_id": model_id}

            return response

        except requests.exceptions.Timeout:
            raise ModelTimeoutError

    def infer_from_parameters(self, model_id, context, prompt, suggestion_id=None, headers=None):
        raise NotImplementedError

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "ollama",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="ollama")
class OllamaPlaybookGenerationPipeline(
    OllamaBase[
        OLLAMA_PIPELINE_CONFIGURATION, PlaybookGenerationParameters, PlaybookGenerationResponse
    ],
    ModelPipelinePlaybookGeneration[OLLAMA_PIPELINE_CONFIGURATION],
    Generic[OLLAMA_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: OLLAMA_PIPELINE_CONFIGURATION):
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

        model_id = self.get_model_id(request.user, model_id)
        llm = self.get_chat_model(model_id)

        formatted_prompt = self.format_prompt(system_template, human_template, text=text, outline=outline)
        output = llm.invoke(formatted_prompt)
        playbook, outline = unwrap_playbook_answer(output)

        if not create_outline:
            outline = ""

        return playbook, outline, []

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "ollama",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="ollama")
class OllamaRoleGenerationPipeline(
    OllamaBase[
        OLLAMA_PIPELINE_CONFIGURATION, RoleGenerationParameters, RoleGenerationResponse
    ],
    ModelPipelineRoleGeneration[OLLAMA_PIPELINE_CONFIGURATION],
    Generic[OLLAMA_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: OLLAMA_PIPELINE_CONFIGURATION):
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

        model_id = self.get_model_id(request.user, model_id)
        llm = self.get_chat_model(model_id)

        formatted_prompt = self.format_prompt(SYSTEM_MESSAGE_ROLE_REQUEST, HUMAN_MESSAGE_TEMPLATE, text=text, outline=outline)
        output = llm.invoke(formatted_prompt)
        role, files, outline = unwrap_role_answer(output, create_outline)

        llm = self.get_chat_model(model_id)
        formatted_prompt = self.format_prompt(SYSTEM_MESSAGE_TEMPLATE_DEFAULTS, HUMAN_MESSAGE_TEMPLATE, text=files[0]["content"], outline=outline)
        output = llm.invoke(formatted_prompt)
        content = message_to_string(output)
        if content.find("```") == -1:
            files[1]["content"] = content
        else:
            files[1]["content"] = unwrap_message_with_yaml_answer(content)

        return role, files, outline, []

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "ollama",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )


@Register(api_type="ollama")
class OllamaRoleExplanationPipeline(NopRoleExplanationPipeline):

    def __init__(self, config: NopConfiguration):
        super().__init__(config=config)

    def get_chat_model(self, model_id):
        return OllamaClient(
            base_url=self.config.inference_url,
            model=model_id,
            timeout=self._timeout,
        )


@Register(api_type="ollama")
class OllamaPlaybookExplanationPipeline(
    OllamaBase[
        OLLAMA_PIPELINE_CONFIGURATION, PlaybookExplanationParameters, PlaybookExplanationResponse
    ],
    ModelPipelinePlaybookExplanation[OLLAMA_PIPELINE_CONFIGURATION],
    Generic[OLLAMA_PIPELINE_CONFIGURATION],
):

    def __init__(self, config: OLLAMA_PIPELINE_CONFIGURATION):
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

        model_id = self.get_model_id(request.user, model_id)
        llm = self.get_chat_model(model_id)

        formatted_prompt = self.format_prompt(SYSTEM_MESSAGE_TEMPLATE, HUMAN_MESSAGE_TEMPLATE, playbook=content)
        explanation = llm.invoke(formatted_prompt)
        return explanation

    def self_test(self) -> HealthCheckSummary:
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: "ollama",
                MODEL_MESH_HEALTH_CHECK_MODELS: "skipped",
            }
        )
