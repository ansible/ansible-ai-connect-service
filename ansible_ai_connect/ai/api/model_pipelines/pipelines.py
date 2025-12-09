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
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Generic, Optional

from attrs import define, field
from django.http import StreamingHttpResponse
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    PIPELINE_CONFIGURATION,
)
from ansible_ai_connect.ai.api.model_pipelines.types import (
    PIPELINE_PARAMETERS,
    PIPELINE_RETURN,
)
from ansible_ai_connect.ai.api.serializers import GenerationRoleResponseSerializer
from ansible_ai_connect.healthcheck.backends import HealthCheckSummary

RoleGenerationResponse = tuple[
    str, serializers.ListField(child=GenerationRoleResponseSerializer()), str, list[str]
]


logger = logging.getLogger(__name__)


@define
class CompletionsParameters:
    request: Request
    model_input: dict[str, Any]
    model_id: str = ""
    suggestion_id: Optional[str] = None

    @classmethod
    def init(
        cls,
        request: Request,
        model_input: dict[str, Any],
        model_id: Optional[str] = None,
        suggestion_id: Optional[str] = None,
    ):
        return cls(
            request=request,
            model_input=model_input,
            model_id=model_id,
            suggestion_id=suggestion_id,
        )


CompletionsResponse = Dict[str, Any]


@define
class ContentMatchParameters:
    request: Request
    model_input: dict[str, Any]
    model_id: str = ""

    @classmethod
    def init(
        cls,
        request: Request,
        model_input: dict[str, Any],
        model_id: Optional[str] = None,
    ):
        return cls(
            request=request,
            model_input=model_input,
            model_id=model_id,
        )


ContentMatchResponse = tuple[str, Response]


@define
class PlaybookGenerationParameters:
    request: Request
    text: str
    custom_prompt: str
    create_outline: bool
    outline: str
    generation_id: str
    model_id: str

    @classmethod
    def init(
        cls,
        request,
        text: str = "",
        custom_prompt: str = "",
        create_outline: bool = False,
        outline: str = "",
        generation_id: str = "",
        model_id: str = "",
    ):
        return cls(
            request=request,
            text=text,
            custom_prompt=custom_prompt,
            create_outline=create_outline,
            outline=outline,
            generation_id=generation_id,
            model_id=model_id,
        )


PlaybookGenerationResponse = tuple[str, str, list]


@define
class RoleGenerationParameters:
    request: Request
    name: str | None
    text: str
    additional_context: dict
    create_outline: bool
    outline: str
    generation_id: str
    model_id: str
    file_types: list

    @classmethod
    def init(
        cls,
        request,
        name: Optional[str] = None,
        text: str = "",
        create_outline: bool = False,
        file_types: list = [],
        additional_context: dict = {},
        outline: str = "",
        generation_id: str = "",
        model_id: str = "",
    ):
        return cls(
            request=request,
            name=name,
            text=text,
            file_types=file_types,
            additional_context=additional_context,
            create_outline=create_outline,
            outline=outline,
            generation_id=generation_id,
            model_id=model_id,
        )


@define
class PlaybookExplanationParameters:
    request: Request
    content: str
    custom_prompt: str
    explanation_id: str
    model_id: str

    @classmethod
    def init(
        cls,
        request,
        content: str,
        custom_prompt: str = "",
        explanation_id: str = "",
        model_id: str = "",
    ):
        return cls(
            request=request,
            content=content,
            custom_prompt=custom_prompt,
            explanation_id=explanation_id,
            model_id=model_id,
        )


PlaybookExplanationResponse = str


@define
class RoleExplanationParameters:
    request: Request
    files: list
    role_name: str
    model_id: str
    focus_on_file: str
    explanation_id: str

    @classmethod
    def init(
        cls,
        request,
        files: list = [],
        role_name: str = "",
        model_id: str = "",
        focus_on_file: str = "",
        explanation_id: str = "",
    ):
        return cls(
            request=request,
            files=files,
            role_name=role_name,
            model_id=model_id,
            focus_on_file=focus_on_file,
            explanation_id=explanation_id,
        )


RoleExplanationResponse = str


@define
class ChatBotParameters:
    query: str
    provider: str
    model_id: str
    conversation_id: Optional[str]
    system_prompt: str
    auth_header: Optional[str] = field(kw_only=True, default=None)
    mcp_headers: Optional[dict[str, dict[str, str]]] = field(kw_only=True, default=None)
    no_tools: bool

    @classmethod
    def init(
        cls,
        query: str,
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        auth_header: Optional[str] = None,
        mcp_headers: Optional[dict[str, dict[str, str]]] = None,
        no_tools: Optional[bool] = False,
    ):
        return cls(
            query=query,
            provider=provider,
            model_id=model_id,
            conversation_id=conversation_id,
            system_prompt=system_prompt,
            auth_header=auth_header,
            mcp_headers=mcp_headers,
            no_tools=no_tools,
        )


ChatBotResponse = Any


@define
class StreamingChatBotParameters(ChatBotParameters):
    media_type: str
    event: Any

    @classmethod
    def init(
        cls,
        query: str,
        provider: Optional[str] = None,
        model_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        system_prompt: Optional[str] = None,
        media_type: Optional[str] = None,
        event: Optional[Any] = None,
        auth_header: Optional[str] = None,
        mcp_headers: Optional[dict[str, dict[str, str]]] = None,
        no_tools: Optional[bool] = False,
    ):
        return cls(
            query=query,
            provider=provider,
            model_id=model_id,
            conversation_id=conversation_id,
            system_prompt=system_prompt,
            media_type=media_type,
            event=event,
            auth_header=auth_header,
            mcp_headers=mcp_headers,
            no_tools=no_tools,
        )


StreamingChatBotResponse = StreamingHttpResponse


class MetaData(Generic[PIPELINE_CONFIGURATION], metaclass=ABCMeta):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        self.config = config

    def get_model_id(self, user, requested_model_id: Optional[str] = None) -> str:
        return requested_model_id or self.config.model_id


class ModelPipeline(
    MetaData[PIPELINE_CONFIGURATION],
    Generic[PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    @abstractmethod
    def alias() -> str:
        raise NotImplementedError

    @abstractmethod
    def invoke(self, params: PIPELINE_PARAMETERS) -> PIPELINE_RETURN:
        raise NotImplementedError

    @abstractmethod
    def self_test(self) -> HealthCheckSummary:
        raise NotImplementedError


class ModelPipelineCompletions(
    ModelPipeline[PIPELINE_CONFIGURATION, CompletionsParameters, CompletionsResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "model-server"

    @abstractmethod
    def infer_from_parameters(self, model_id, context, prompt, suggestion_id=None, headers=None):
        raise NotImplementedError


class ModelPipelineContentMatch(
    ModelPipeline[PIPELINE_CONFIGURATION, ContentMatchParameters, ContentMatchResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "content-match"


class ModelPipelinePlaybookGeneration(
    ModelPipeline[PIPELINE_CONFIGURATION, PlaybookGenerationParameters, PlaybookGenerationResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "playbook-generation"


class ModelPipelineRoleGeneration(
    ModelPipeline[PIPELINE_CONFIGURATION, RoleGenerationParameters, RoleGenerationResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "role-generation"


class ModelPipelinePlaybookExplanation(
    ModelPipeline[
        PIPELINE_CONFIGURATION, PlaybookExplanationParameters, PlaybookExplanationResponse
    ],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "playbook-explanation"


class ModelPipelineRoleExplanation(
    ModelPipeline[PIPELINE_CONFIGURATION, RoleExplanationParameters, RoleExplanationResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "role-explanation"


class ModelPipelineChatBot(
    ModelPipeline[PIPELINE_CONFIGURATION, ChatBotParameters, ChatBotResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "chatbot-service"


class ModelPipelineStreamingChatBot(
    ModelPipeline[PIPELINE_CONFIGURATION, StreamingChatBotParameters, StreamingChatBotResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @staticmethod
    def alias():
        return "streaming-chatbot-service"


DUMMY_PLAYBOOK = """---
- hosts: rhel9
  become: yes
  tasks:
    - name: Install EPEL repository
      ansible.builtin.dnf:
        name: epel-release
        state: present

    - name: Update package list
      ansible.builtin.dnf:
        update_cache: yes

    - name: Install nginx
      ansible.builtin.dnf:
        name: nginx
        state: present

    - name: Start and enable nginx service
      ansible.builtin.systemd:
        name: nginx
        state: started
        enabled: yes
"""

DUMMY_ROLE_FILES = [
    {
        "path": "tasks/main.yml",
        "file_type": "task",
        "content": "- name: Install the Nginx packages\n"
        "  package:\n"
        '    name: "{{ install_nginx_packages }}"\n'
        "    state: present\n"
        "  become: true\n"
        "- name: Start the service\n"
        "  service:\n"
        "    name: nginx\n"
        "    enabled: true\n"
        "    state: started\n"
        "    become: true",
    },
    {
        "path": "defaults/main.yml",
        "file_type": "default",
        "content": "install_nginx_packages:\n  - nginx",
    },
]

DUMMY_ROLE_OUTLINE = """
1. Install the Nginx packages
2. Start the service
"""

DUMMY_PLAYBOOK_OUTLINE = """
1. First, ensure that your RHEL 9 system is up-to-date.
2. Next, you install the Nginx package using the package manager.
3. After installation, start the ginx service.
4. Ensure that Nginx starts automatically.
5. Check if Nginx is running successfully.
6. Visit your system's IP address followed by the default Nginx port number (80 or 443).
"""

DUMMY_EXPLANATION = """# Information
This playbook installs the Nginx web server on all hosts
that are running Red Hat Enterprise Linux (RHEL) 9.
"""

DUMMY_ROLE_EXPLANATION = """# Information
This role installs the Nginx web server on all hosts
that are running Red Hat Enterprise Linux (RHEL) 9.
"""
