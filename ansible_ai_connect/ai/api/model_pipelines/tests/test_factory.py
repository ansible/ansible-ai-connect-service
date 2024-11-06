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

from typing import Type

from django.conf import settings
from django.test import override_settings

from ansible_ai_connect.ai.api.model_pipelines.factory import ModelPipelineFactory
from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import (
    NopContentMatchPipeline,
    NopPlaybookExplanationPipeline,
    NopPlaybookGenerationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PIPELINE_TYPE,
    MetaData,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
)
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestModelPipelineFactory(WisdomServiceAPITestCaseBaseOIDC):

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE=None)
    def test_model_mesh_type_undefined(self):
        factory = ModelPipelineFactory()
        with self.assertRaises(ValueError):
            factory.get_pipeline(MetaData)

    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="dummy")
    def test_caching(self):
        factory = ModelPipelineFactory()
        pipeline = factory.get_pipeline(MetaData)
        self.assertIsNotNone(pipeline)

        cached = factory.get_pipeline(MetaData)
        self.assertEqual(pipeline, cached)

    # 'grpc' does not have a Content Match pipeline
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    def test_default_fallback_content_match(self):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelineContentMatch)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopContentMatchPipeline)
            self.assertInLog(
                "Pipeline for 'grpc', 'ModelPipelineContentMatch' not found. "
                "Defaulting to NOP implementation.",
                log,
            )

    # 'grpc' does not have a Playbook Generation pipeline
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    def test_default_fallback_playbook_generation(self):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelinePlaybookGeneration)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopPlaybookGenerationPipeline)
            self.assertInLog(
                "Pipeline for 'grpc', 'ModelPipelinePlaybookGeneration' not found. "
                "Defaulting to NOP implementation.",
                log,
            )

    # 'grpc' does not have a Playbook Explanation pipeline
    @override_settings(ANSIBLE_AI_MODEL_MESH_API_TYPE="grpc")
    def test_default_fallback_playbook_explanation(self):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelinePlaybookExplanation)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopPlaybookExplanationPipeline)
            self.assertInLog(
                "Pipeline for 'grpc', 'ModelPipelinePlaybookExplanation' not found. "
                "Defaulting to NOP implementation.",
                log,
            )


class TestModelPipelineFactoryImplementations(WisdomServiceAPITestCaseBaseOIDC):
    def assert_concrete_implementation(self, pipeline_type: Type[PIPELINE_TYPE], expected_cls):
        factory = ModelPipelineFactory()

        pipeline = factory.get_pipeline(pipeline_type)
        self.assertIsNotNone(pipeline)
        self.assertIsInstance(pipeline, expected_cls)

    def assert_default_implementation(
        self, pipeline_type: Type[PIPELINE_TYPE], expected_default_cls
    ):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(pipeline_type)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, expected_default_cls)
            self.assertInLog(
                f"Pipeline for '{settings.ANSIBLE_AI_MODEL_MESH_API_TYPE}', "
                f"'{pipeline_type.__name__}' not found. "
                "Defaulting to NOP implementation.",
                log,
            )
            with self.assertRaises(NotImplementedError):
                pipeline.invoke(None)
