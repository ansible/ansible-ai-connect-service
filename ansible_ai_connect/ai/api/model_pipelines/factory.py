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
from typing import Optional, Type

from django.conf import settings

from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PIPELINE_TYPE,
    MetaData,
    ModelPipelineCompletions,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
)

logger = logging.getLogger(__name__)


class ModelPipelineFactory:

    _metadata: Optional[MetaData] = None
    _completions_pipeline: Optional[ModelPipelineCompletions] = None
    _content_match_pipeline: Optional[ModelPipelineContentMatch] = None
    _playbook_generation_pipeline: Optional[ModelPipelinePlaybookGeneration] = None
    _playbook_explanation_pipeline: Optional[ModelPipelinePlaybookExplanation] = None

    def get_pipeline(self, feature: Type[PIPELINE_TYPE]) -> PIPELINE_TYPE:
        if feature is MetaData:
            return self._get_metadata()
        if feature is ModelPipelineCompletions:
            return self._get_completions_pipeline()
        elif feature is ModelPipelineContentMatch:
            return self._get_content_match_pipeline()
        elif feature is ModelPipelinePlaybookGeneration:
            return self._get_playbook_generation_pipeline()
        elif feature is ModelPipelinePlaybookExplanation:
            return self._get_playbook_explanation_pipeline()
        else:
            raise ValueError(f"Invalid ModelFeature type: {feature}")

    def _get_metadata(self) -> MetaData:
        if self._metadata:
            return self._metadata

        from ansible_ai_connect.ai.api.model_pipelines.bam.pipelines import BAMMetaData
        from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
            DummyMetaData,
        )
        from ansible_ai_connect.ai.api.model_pipelines.grpc.pipelines import (
            GrpcMetaData,
        )
        from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
            HttpMetaData,
        )
        from ansible_ai_connect.ai.api.model_pipelines.llamacpp.pipelines import (
            LlamaCppMetaData,
        )
        from ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines import (
            OllamaMetaData,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy import (
            WCADummyMetaData,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
            WCAOnPremMetaData,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
            WCASaaSMetaData,
        )

        pipelines = {
            "grpc": GrpcMetaData,
            "wca": WCASaaSMetaData,
            "wca-onprem": WCAOnPremMetaData,
            "wca-dummy": WCADummyMetaData,
            "http": HttpMetaData,
            "llamacpp": LlamaCppMetaData,
            "dummy": DummyMetaData,
            "bam": BAMMetaData,
            "ollama": OllamaMetaData,
        }
        if not settings.ANSIBLE_AI_MODEL_MESH_API_TYPE:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        try:
            expected_pipeline = pipelines[settings.ANSIBLE_AI_MODEL_MESH_API_TYPE]
        except KeyError:
            logger.error(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )
            raise ValueError(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )

        if self._metadata is None:
            self._metadata = expected_pipeline(inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL)

        return self._metadata

    def _get_completions_pipeline(self) -> ModelPipelineCompletions:
        if self._completions_pipeline:
            return self._completions_pipeline

        from ansible_ai_connect.ai.api.model_pipelines.bam.pipelines import (
            BAMCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
            DummyCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.grpc.pipelines import (
            GrpcCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
            HttpCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.llamacpp.pipelines import (
            LlamaCppCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines import (
            OllamaCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy import (
            WCADummyCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
            WCAOnPremCompletionsPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
            WCASaaSCompletionsPipeline,
        )

        pipelines = {
            "grpc": GrpcCompletionsPipeline,
            "wca": WCASaaSCompletionsPipeline,
            "wca-onprem": WCAOnPremCompletionsPipeline,
            "wca-dummy": WCADummyCompletionsPipeline,
            "http": HttpCompletionsPipeline,
            "llamacpp": LlamaCppCompletionsPipeline,
            "dummy": DummyCompletionsPipeline,
            "bam": BAMCompletionsPipeline,
            "ollama": OllamaCompletionsPipeline,
        }
        if not settings.ANSIBLE_AI_MODEL_MESH_API_TYPE:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        try:
            expected_pipeline = pipelines[settings.ANSIBLE_AI_MODEL_MESH_API_TYPE]
        except KeyError:
            logger.error(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )
            raise ValueError(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )

        if self._completions_pipeline is None:
            self._completions_pipeline = expected_pipeline(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL
            )

        return self._completions_pipeline

    def _get_content_match_pipeline(self) -> ModelPipelineContentMatch:
        if self._content_match_pipeline:
            return self._content_match_pipeline

        from ansible_ai_connect.ai.api.model_pipelines.bam.pipelines import (
            BAMContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
            DummyContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.grpc.pipelines import (
            GrpcContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
            HttpContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.llamacpp.pipelines import (
            LlamaCppContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines import (
            OllamaContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy import (
            WCADummyContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
            WCAOnPremContentMatchPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
            WCASaaSContentMatchPipeline,
        )

        pipelines = {
            "grpc": GrpcContentMatchPipeline,
            "wca": WCASaaSContentMatchPipeline,
            "wca-onprem": WCAOnPremContentMatchPipeline,
            "wca-dummy": WCADummyContentMatchPipeline,
            "http": HttpContentMatchPipeline,
            "llamacpp": LlamaCppContentMatchPipeline,
            "dummy": DummyContentMatchPipeline,
            "bam": BAMContentMatchPipeline,
            "ollama": OllamaContentMatchPipeline,
        }
        if not settings.ANSIBLE_AI_MODEL_MESH_API_TYPE:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        try:
            expected_pipeline = pipelines[settings.ANSIBLE_AI_MODEL_MESH_API_TYPE]
        except KeyError:
            logger.error(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )
            raise ValueError(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )

        if self._content_match_pipeline is None:
            self._content_match_pipeline = expected_pipeline(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL
            )

        return self._content_match_pipeline

    def _get_playbook_generation_pipeline(self) -> ModelPipelinePlaybookGeneration:
        if self._playbook_generation_pipeline:
            return self._playbook_generation_pipeline

        from ansible_ai_connect.ai.api.model_pipelines.bam.pipelines import (
            BAMPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
            DummyPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.grpc.pipelines import (
            GrpcPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
            HttpPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.llamacpp.pipelines import (
            LlamaCppPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines import (
            OllamaPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy import (
            WCADummyPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
            WCAOnPremPlaybookGenerationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
            WCASaaSPlaybookGenerationPipeline,
        )

        pipelines = {
            "grpc": GrpcPlaybookGenerationPipeline,
            "wca": WCASaaSPlaybookGenerationPipeline,
            "wca-onprem": WCAOnPremPlaybookGenerationPipeline,
            "wca-dummy": WCADummyPlaybookGenerationPipeline,
            "http": HttpPlaybookGenerationPipeline,
            "llamacpp": LlamaCppPlaybookGenerationPipeline,
            "dummy": DummyPlaybookGenerationPipeline,
            "bam": BAMPlaybookGenerationPipeline,
            "ollama": OllamaPlaybookGenerationPipeline,
        }
        if not settings.ANSIBLE_AI_MODEL_MESH_API_TYPE:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        try:
            expected_pipeline = pipelines[settings.ANSIBLE_AI_MODEL_MESH_API_TYPE]
        except KeyError:
            logger.error(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )
            raise ValueError(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )

        if self._playbook_generation_pipeline is None:
            self._playbook_generation_pipeline = expected_pipeline(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL
            )

        return self._playbook_generation_pipeline

    def _get_playbook_explanation_pipeline(self) -> ModelPipelinePlaybookExplanation:
        if self._playbook_explanation_pipeline:
            return self._playbook_explanation_pipeline

        from ansible_ai_connect.ai.api.model_pipelines.bam.pipelines import (
            BAMPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.dummy.pipelines import (
            DummyPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.grpc.pipelines import (
            GrpcPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.http.pipelines import (
            HttpPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.llamacpp.pipelines import (
            LlamaCppPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.ollama.pipelines import (
            OllamaPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_dummy import (
            WCADummyPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_onprem import (
            WCAOnPremPlaybookExplanationPipeline,
        )
        from ansible_ai_connect.ai.api.model_pipelines.wca.pipelines_saas import (
            WCASaaSPlaybookExplanationPipeline,
        )

        pipelines = {
            "grpc": GrpcPlaybookExplanationPipeline,
            "wca": WCASaaSPlaybookExplanationPipeline,
            "wca-onprem": WCAOnPremPlaybookExplanationPipeline,
            "wca-dummy": WCADummyPlaybookExplanationPipeline,
            "http": HttpPlaybookExplanationPipeline,
            "llamacpp": LlamaCppPlaybookExplanationPipeline,
            "dummy": DummyPlaybookExplanationPipeline,
            "bam": BAMPlaybookExplanationPipeline,
            "ollama": OllamaPlaybookExplanationPipeline,
        }
        if not settings.ANSIBLE_AI_MODEL_MESH_API_TYPE:
            raise ValueError(
                f"Invalid model mesh client type: {settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}"
            )

        try:
            expected_pipeline = pipelines[settings.ANSIBLE_AI_MODEL_MESH_API_TYPE]
        except KeyError:
            logger.error(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )
            raise ValueError(
                "Unexpected ANSIBLE_AI_MODEL_MESH_API_TYPE value: "
                f"'{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}'"
            )

        if self._playbook_explanation_pipeline is None:
            self._playbook_explanation_pipeline = expected_pipeline(
                inference_url=settings.ANSIBLE_AI_MODEL_MESH_API_URL
            )

        return self._playbook_explanation_pipeline
