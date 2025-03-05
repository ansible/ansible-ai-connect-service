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

from django.test import override_settings

from ansible_ai_connect.ai.api.exceptions import FeatureNotAvailable
from ansible_ai_connect.ai.api.model_pipelines.factory import ModelPipelineFactory
from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import (
    NopContentMatchPipeline,
    NopPlaybookExplanationPipeline,
    NopPlaybookGenerationPipeline,
    NopRoleExplanationPipeline,
)
from ansible_ai_connect.ai.api.model_pipelines.pipelines import (
    PIPELINE_TYPE,
    MetaData,
    ModelPipelineContentMatch,
    ModelPipelinePlaybookExplanation,
    ModelPipelinePlaybookGeneration,
    ModelPipelineRoleExplanation,
)
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestModelPipelineFactory(WisdomServiceAPITestCaseBaseOIDC):

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=None)
    def test_config_undefined(self):
        with self.assertRaises(TypeError):
            ModelPipelineFactory()

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
    def test_caching(self):
        factory = ModelPipelineFactory()
        pipeline = factory.get_pipeline(MetaData)
        self.assertIsNotNone(pipeline)

        cached = factory.get_pipeline(MetaData)
        self.assertEqual(pipeline, cached)

    # 'grpc' does not have a Content Match pipeline
    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("grpc"))
    def test_default_fallback_content_match(self):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelineContentMatch)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopContentMatchPipeline)
            self.assertInLog(
                "Using NOP implementation for 'ModelPipelineContentMatch'.",
                log,
            )

    # 'grpc' does not have a Playbook Generation pipeline
    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("grpc"))
    def test_default_fallback_playbook_generation(self):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelinePlaybookGeneration)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopPlaybookGenerationPipeline)
            self.assertInLog(
                "Using NOP implementation for 'ModelPipelinePlaybookGeneration'.",
                log,
            )

    # 'grpc' does not have a Playbook Explanation pipeline
    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("grpc"))
    def test_default_fallback_playbook_explanation(self):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelinePlaybookExplanation)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopPlaybookExplanationPipeline)
            self.assertInLog(
                "Using NOP implementation for 'ModelPipelinePlaybookExplanation'.",
                log,
            )

    # 'grpc' does not have a Role Explanation pipeline
    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("grpc"))
    def test_default_fallback_role_explanation(self):
        factory = ModelPipelineFactory()

        with self.assertLogs(logger="root", level="INFO") as log:
            pipeline = factory.get_pipeline(ModelPipelineRoleExplanation)
            self.assertIsNotNone(pipeline)
            self.assertIsInstance(pipeline, NopRoleExplanationPipeline)
            self.assertInLog(
                "Using NOP implementation for 'ModelPipelineRoleExplanation'.",
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
                f"Using NOP implementation for '{pipeline_type.__name__}'.",
                log,
            )
            with self.assertRaises(FeatureNotAvailable):
                pipeline.invoke(None)
