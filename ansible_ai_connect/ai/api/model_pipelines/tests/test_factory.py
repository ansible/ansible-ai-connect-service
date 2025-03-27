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
from ansible_ai_connect.ai.api.model_pipelines.nop.pipelines import NopMetaData
from ansible_ai_connect.ai.api.model_pipelines.pipelines import PIPELINE_TYPE, MetaData
from ansible_ai_connect.ai.api.model_pipelines.tests import mock_config
from ansible_ai_connect.test_utils import WisdomServiceAPITestCaseBaseOIDC


class TestModelPipelineFactory(WisdomServiceAPITestCaseBaseOIDC):

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=None)
    def test_config_undefined(self):
        factory = ModelPipelineFactory()
        pipeline = factory.get_pipeline(MetaData)
        self.assertIsNotNone(pipeline)
        self.assertIsInstance(pipeline, NopMetaData)

    @override_settings(ANSIBLE_AI_MODEL_MESH_CONFIG=mock_config("dummy"))
    def test_caching(self):
        factory = ModelPipelineFactory()
        pipeline = factory.get_pipeline(MetaData)
        self.assertIsNotNone(pipeline)

        cached = factory.get_pipeline(MetaData)
        self.assertEqual(pipeline, cached)


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
