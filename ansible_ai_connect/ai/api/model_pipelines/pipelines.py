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

from ansible_ai_connect.healthcheck.backends import (
    MODEL_MESH_HEALTH_CHECK_MODELS,
    MODEL_MESH_HEALTH_CHECK_PROVIDER,
    HealthCheckSummary,
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


class MetaData(metaclass=ABCMeta):

    def __init__(self, inference_url):
        self._inference_url = inference_url

    def get_model_id(
        self, user, organization_id: Optional[int] = None, requested_model_id: Optional[str] = None
    ) -> str:
        return requested_model_id or settings.ANSIBLE_AI_MODEL_MESH_MODEL_ID

    def supports_ari_postprocessing(self):
        return settings.ENABLE_ARI_POSTPROCESS


class ModelPipeline(Generic[PIPELINE_PARAMETERS, PIPELINE_RETURN], MetaData, metaclass=ABCMeta):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    @abstractmethod
    def invoke(self, params: PIPELINE_PARAMETERS) -> PIPELINE_RETURN:
        raise NotImplementedError

    def self_test(self):
        return HealthCheckSummary(
            {
                MODEL_MESH_HEALTH_CHECK_PROVIDER: settings.ANSIBLE_AI_MODEL_MESH_API_TYPE,
                MODEL_MESH_HEALTH_CHECK_MODELS: "ok",
            }
        )


class ModelPipelineCompletions(
    ModelPipeline[CompletionsParameters, CompletionsResponse], metaclass=ABCMeta
):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)

    @abstractmethod
    def infer_from_parameters(self, api_key, model_id, context, prompt, suggestion_id=None):
        raise NotImplementedError


class ModelPipelineContentMatch(
    ModelPipeline[ContentMatchParameters, ContentMatchResponse],
    metaclass=ABCMeta,
):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)


class ModelPipelinePlaybookGeneration(
    ModelPipeline[PlaybookGenerationParameters, PlaybookGenerationResponse],
    metaclass=ABCMeta,
):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)


class ModelPipelinePlaybookExplanation(
    ModelPipeline[PlaybookExplanationParameters, PlaybookExplanationResponse],
    metaclass=ABCMeta,
):

    def __init__(self, inference_url):
        super().__init__(inference_url=inference_url)