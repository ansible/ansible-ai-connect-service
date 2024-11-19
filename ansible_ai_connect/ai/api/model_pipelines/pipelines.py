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
from typing import Any, Dict, Generic, Optional, TypeVar

from attrs import define
from django.conf import settings
from rest_framework.request import Request
from rest_framework.response import Response

from ansible_ai_connect.ai.api.model_pipelines.config_pipelines import (
    PIPELINE_CONFIGURATION,
)

logger = logging.getLogger(__name__)

PIPELINE_PARAMETERS = TypeVar("PIPELINE_PARAMETERS")
PIPELINE_RETURN = TypeVar("PIPELINE_RETURN")
PIPELINE_TYPE = TypeVar("PIPELINE_TYPE")


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
            text=text,
            file_types=file_types,
            additional_context=additional_context,
            create_outline=create_outline,
            outline=outline,
            generation_id=generation_id,
            model_id=model_id,
        )


RoleGenerationResponse = tuple[str, list, str]


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


class MetaData(Generic[PIPELINE_CONFIGURATION], metaclass=ABCMeta):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        self.config = config

    def get_model_id(
        self, user, organization_id: Optional[int] = None, requested_model_id: Optional[str] = None
    ) -> str:
        return requested_model_id or self.config.model_id

    def supports_ari_postprocessing(self):
        return settings.ENABLE_ARI_POSTPROCESS


class ModelPipeline(
    MetaData[PIPELINE_CONFIGURATION],
    Generic[PIPELINE_CONFIGURATION, PIPELINE_PARAMETERS, PIPELINE_RETURN],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @abstractmethod
    def invoke(self, params: PIPELINE_PARAMETERS) -> PIPELINE_RETURN:
        raise NotImplementedError

    @abstractmethod
    def self_test(self):
        raise NotImplementedError


class ModelPipelineCompletions(
    ModelPipeline[PIPELINE_CONFIGURATION, CompletionsParameters, CompletionsResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)

    @abstractmethod
    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


class ModelPipelineContentMatch(
    ModelPipeline[PIPELINE_CONFIGURATION, ContentMatchParameters, ContentMatchResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)


class ModelPipelinePlaybookGeneration(
    ModelPipeline[PIPELINE_CONFIGURATION, PlaybookGenerationParameters, PlaybookGenerationResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)


class ModelPipelineRoleGeneration(
    ModelPipeline[PIPELINE_CONFIGURATION, RoleGenerationParameters, RoleGenerationResponse],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)


class ModelPipelinePlaybookExplanation(
    ModelPipeline[
        PIPELINE_CONFIGURATION, PlaybookExplanationParameters, PlaybookExplanationResponse
    ],
    Generic[PIPELINE_CONFIGURATION],
    metaclass=ABCMeta,
):

    def __init__(self, config: PIPELINE_CONFIGURATION):
        super().__init__(config=config)
